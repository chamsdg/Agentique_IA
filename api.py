import os
import json
import hmac
import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

ACCOUNT = (os.getenv("SNOWFLAKE_ACCOUNT") or "").strip()
PAT = (os.getenv("SNOWFLAKE_PAT") or "").strip()
DB = (os.getenv("SNOWFLAKE_DB") or "").strip()
SCHEMA = (os.getenv("SNOWFLAKE_SCHEMA") or "").strip()
API_KEY = (os.getenv("API_KEY") or "").strip()

ALLOWED_AGENTS = {"AGENT_VENTES", "AGENT_OPPORTUNITE"}

if not all([ACCOUNT, PAT, DB, SCHEMA]):
    raise RuntimeError("Missing .env vars for Snowflake (ACCOUNT, PAT, DB, SCHEMA).")

HEADERS_BASE = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
}

# ✅ Keep-alive
SESSION = requests.Session()
SESSION.headers.update(HEADERS_BASE)

app = FastAPI(title="Sales Agent API", version="1.4")


class ChatRequest(BaseModel):
    agent: str
    messages: list[dict]
    debug_reasoning: bool = False


def to_sf_messages(history: list[dict]) -> list[dict]:
    msgs = []
    for m in history:
        role = m.get("role")
        content = m.get("content", "")
        if role not in ("user", "assistant"):
            continue
        msgs.append({"role": role, "content": [{"type": "text", "text": str(content)}]})
    return msgs


def extract_text_chunk(data: dict) -> str:
    # On tente plusieurs champs possibles
    candidates = [
        data.get("text"),
        data.get("delta"),
        data.get("content"),
        data.get("message"),
        data.get("output_text"),
    ]
    for chunk in candidates:
        if isinstance(chunk, str) and chunk.strip():
            return chunk
        if isinstance(chunk, list):
            parts = []
            for item in chunk:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item.get("content"), str):
                        parts.append(item["content"])
            s = "".join(parts)
            if s.strip():
                return s
        if isinstance(chunk, dict):
            if isinstance(chunk.get("text"), str) and chunk["text"].strip():
                return chunk["text"]
            if isinstance(chunk.get("content"), str) and chunk["content"].strip():
                return chunk["content"]
    return ""


def normalize(s: str) -> str:
    # Normalisation légère pour mieux comparer (espaces/retours lignes)
    return " ".join((s or "").split())


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, x_api_key: str | None = Header(default=None)):
    if API_KEY:
        if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
            raise HTTPException(status_code=401, detail="Unauthorized")

    if req.agent not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {req.agent}")

    sf_url = (
        f"https://{ACCOUNT}.snowflakecomputing.com"
        f"/api/v2/databases/{DB}/schemas/{SCHEMA}/agents/{req.agent}:run"
    )

    system_prompt = {
        "role": "system",
        "content": [{
            "type": "text",
            "text": (
                "Français uniquement. "
                "Texte simple, pas de Markdown (# interdit). "
                "Réponse concise et orientée business. "
                "Ne produis AUCUN texte d'étapes, de statut ou de raisonnement "
                "(pas de thinking, pas de status). "
                "Réponds directement par le résultat final."
            )
        }]
    }

    sf_payload = {"messages": [system_prompt] + to_sf_messages(req.messages)[-5:]}

    def event_generator():
        try:
            with SESSION.post(sf_url, json=sf_payload, stream=True, timeout=(10, 180)) as r:
                if r.status_code >= 400:
                    yield (
                        "event: error\n"
                        f"data: {json.dumps({'status': r.status_code, 'body': r.text[:2000]})}\n\n"
                    )
                    return

                r.encoding = "utf-8"
                current_event = ""

                # ✅ Accumulateur + hash de normalisation pour ne jamais renvoyer 2x la même chose
                sent = ""             # texte déjà envoyé au client (exact)
                sent_norm = ""        # version normalisée
                last_norm_chunk = ""  # pour ignorer doublons exacts

                for raw_line in r.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue

                    if raw_line == "":
                        current_event = ""
                        continue

                    line = raw_line.strip()

                    if line.startswith("event:"):
                        current_event = line.split("event:", 1)[1].strip().lower()
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line.split("data:", 1)[1].strip()
                    try:
                        data = json.loads(data_str) if data_str else {}
                    except Exception:
                        continue

                    # ✅ Ignorer thinking/status tout le temps (sauf debug)
                    if current_event and ("thinking" in current_event or "status" in current_event):
                        if req.debug_reasoning:
                            t = extract_text_chunk(data)
                            if t:
                                yield f"event: reasoning\ndata: {json.dumps({'text': t})}\n\n"
                        continue

                    # ✅ Liste blanche : on ne traite le texte que sur certains events + fallback
                    allowed = ("delta", "message", "final", "response", "")
                    if current_event and current_event not in allowed:
                        continue

                    text = extract_text_chunk(data)
                    if not text:
                        continue

                    norm = normalize(text)
                    if not norm:
                        continue

                    # (1) si chunk identique au chunk précédent -> ignore
                    if norm == last_norm_chunk:
                        continue
                    last_norm_chunk = norm

                    # (2) Si Snowflake renvoie un snapshot complet : il contient souvent déjà "sent"
                    # On compare avec la version normalisée pour être robuste aux espaces
                    if sent_norm and norm.startswith(sent_norm):
                        # envoyer seulement la "diff" mais en exact, on calcule diff sur l'exact quand possible
                        # fallback: si impossible, on remplace (front gère)
                        # On tente diff exact:
                        if text.startswith(sent):
                            diff = text[len(sent):]
                            if diff:
                                yield f"event: delta\ndata: {json.dumps({'text': diff})}\n\n"
                            sent = text
                            sent_norm = norm
                        else:
                            # on envoie le snapshot complet comme delta (le front remplace)
                            yield f"event: delta\ndata: {json.dumps({'text': text})}\n\n"
                            sent = text
                            sent_norm = norm
                        continue

                    # (3) vieux snapshot plus court -> ignore
                    if norm and sent_norm and sent_norm.startswith(norm):
                        continue

                    # (4) vrai delta
                    yield f"event: delta\ndata: {json.dumps({'text': text})}\n\n"
                    sent += text
                    sent_norm = normalize(sent)

            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'exception': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"ok": True, "db": DB, "schema": SCHEMA, "allowed_agents": sorted(list(ALLOWED_AGENTS))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
