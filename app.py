import os
import json
import requests
import streamlit as st
from dotenv import load_dotenv

# -------------------------
# Config
# -------------------------
load_dotenv()
API_KEY = (os.getenv("API_KEY") or "").strip()
# BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/chat/stream")
BACKEND_URL = "https://agentique-ia.onrender.com/chat/stream"


LOGO_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSTSgfw9M41EkrtiC-5aV_4x3RNVOheebqUrg&s"

AGENTS = [
    {"ui_key": "Agent Analytic Vente", "ui_name": "Agent Analytic Vente", "sf_agent": "AGENT_VENTES", "icon": "💼", "theme": "blue"},
    {"ui_key": "Agent Analytic OLGA", "ui_name": "Agent Analytic OLGA", "sf_agent": "AGENT_OPPORTUNITE", "icon": "🎯", "theme": "pink"},
    {"ui_key": "Agent Analytic STOCK", "ui_name": "Agent Analytic STOCK", "sf_agent": "AGENT_STOCK", "icon": "📦", "theme": "green"},
]

UI_KEYS = [a["ui_key"] for a in AGENTS]
UI_TO_SF = {a["ui_key"]: a["sf_agent"] for a in AGENTS}
UI_NAME = {a["ui_key"]: a["ui_name"] for a in AGENTS}
UI_ICON = {a["ui_key"]: a["icon"] for a in AGENTS}
UI_THEME = {a["ui_key"]: a.get("theme", "blue") for a in AGENTS}

# -------------------------
# State init (robuste)
# -------------------------
if "active_ui_agent" not in st.session_state:
    st.session_state.active_ui_agent = UI_KEYS[0]

# Si l'agent a été renommé/supprimé, on retombe sur le premier
if st.session_state.active_ui_agent not in UI_KEYS:
    st.session_state.active_ui_agent = UI_KEYS[0]

if "messages_by_agent" not in st.session_state:
    st.session_state.messages_by_agent = {k: [] for k in UI_KEYS}
else:
    for k in UI_KEYS:
        st.session_state.messages_by_agent.setdefault(k, [])

# -------------------------
# CSS (fond blanc, jaune/noir)
# -------------------------
st.markdown(
"""
<style>
:root{
  --yellow:#fec900;
  --black:#1d1d1b;
  --white:#ffffff;

  --bg: var(--white);
  --surface: var(--white);
  --surface-soft: rgba(29,29,27,.02);

  --text: var(--black);
  --border: rgba(29,29,27,.12);
  --border-soft: rgba(29,29,27,.08);
}

.stApp{
  background: var(--bg);
  color: var(--text);
}

.block-container{
  padding-top: 1.2rem;
  padding-bottom: 2rem;
  max-width: 1200px;
}

section[data-testid="stSidebar"]{
  background: var(--white);
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container{
  padding-top: 1.2rem;
}

div[data-testid="stChatMessage"]{
  padding:.35rem 0;
}
div[data-testid="stChatMessage"] p{
  margin-bottom:.5rem;
  line-height:1.55;
  color: var(--text);
}

div[data-testid="stChatInput"] textarea{
  border-radius:14px !important;
  border: 1px solid var(--border) !important;
  background: var(--white) !important;
  color: var(--text) !important;
}
div[data-testid="stChatInput"] textarea:focus{
  outline: none !important;
  border-color: var(--yellow) !important;
  box-shadow: 0 0 0 3px rgba(254,201,0,.28) !important;
}

.stButton>button{
  border-radius:12px;
  padding:.62rem .95rem;
  font-weight:900;
  border: 1px solid var(--yellow);
  background: var(--yellow);
  color: var(--black);
}
.stButton>button:hover{
  filter: brightness(.97);
  box-shadow: 0 10px 24px rgba(254,201,0,.18);
}
.stButton > button:disabled{
  background: rgba(29,29,27,.05) !important;
  color: rgba(29,29,27,.55) !important;
  border-color: var(--border) !important;
}

hr{
  margin:1rem 0;
  border:none;
  border-top:1px solid var(--border-soft);
}

.topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:14px 16px;
  border-radius:18px;
  border:1px solid var(--border);
  background: var(--white);
  box-shadow: 0 10px 28px rgba(29,29,27,.08);
  margin-bottom:12px;
}

.brand{
  display:flex;
  align-items:center;
  gap:12px;
}
.brand img{
  width:40px;
  height:40px;
  border-radius:12px;
}
.brand .t{
  font-size:1.12rem;
  font-weight:900;
  margin:0;
}
.brand .s{
  font-size:.92rem;
  color: rgba(29,29,27,.65);
  margin-top:2px;
}

.agent-pill{
  display:inline-flex;
  align-items:center;
  gap:.55rem;
  padding:.42rem .85rem;
  border-radius:999px;
  font-weight:900;
  border:1px solid var(--yellow);
  background: rgba(254,201,0,.22);
  color: var(--black);
}

.bi-card{
  border-radius:18px;
  overflow:hidden;
  border:1px solid var(--border-soft);
  background: var(--white);
  box-shadow: 0 8px 26px rgba(29,29,27,.06);
}
.bi-card.active{
  box-shadow: 0 0 0 3px rgba(254,201,0,.25) inset,
              0 16px 42px rgba(29,29,27,.12);
  border-color: var(--yellow);
}
.bi-top{
  padding:16px 16px 12px 16px;
  background: linear-gradient(135deg,
    rgba(254,201,0,.25),
    rgba(254,201,0,.08)
  );
  display:flex;
  align-items:center;
  justify-content:space-between;
}
.bi-h3{
  margin:0;
  font-size:1.35rem;
  font-weight:900;
}
.bi-mini{
  margin-top:4px;
  font-size:.95rem;
  color: rgba(29,29,27,.65);
}
.bi-ico{
  width:54px;
  height:54px;
  border-radius:14px;
  background: rgba(254,201,0,.25);
  border:1px solid rgba(254,201,0,.45);
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:1.55rem;
}

.bi-body{
  padding:14px 16px 16px 16px;
  background: var(--white);
  border-top:1px solid var(--border-soft);
}
.bi-bullets{
  margin:0;
  padding-left:18px;
  line-height:1.6;
  font-size:.98rem;
}

.cta button{
  width: 100% !important;
  border-radius: 12px !important;
  padding: .72rem 1rem !important;
  font-weight: 900 !important;
}
</style>
""",
unsafe_allow_html=True
)

# -------------------------
# Helper: streaming (anti-répétition)
# -------------------------
def run_stream(ui_key: str, prompt: str):
    sf_agent = UI_TO_SF[ui_key]
    messages = st.session_state.messages_by_agent[ui_key]

    # Add user message
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)

    payload = {
        "agent": sf_agent,
        "messages": messages[-20:],
        "debug_reasoning": False,
    }
    #headers = {"X-API-Key": API_KEY} if API_KEY else {}
    headers = {
    "x-api-key": st.secrets["API_KEY"]
}


    with st.chat_message("assistant", avatar=UI_ICON[ui_key]):
        placeholder = st.empty()
        placeholder.markdown("⏳ Analyse en cours…")

        current_event = ""
        full_text = ""
        last_chunk = ""

        with requests.post(BACKEND_URL, json=payload, headers=headers, stream=True, timeout=180) as r:
            if r.status_code >= 400:
                st.error(f"Erreur backend: {r.status_code}\n{r.text[:2000]}")
                st.stop()

            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue

                line = raw.strip()

                if line.startswith(":"):  # keep-alive SSE
                    continue

                if line.startswith("event:"):
                    current_event = line.split("event:", 1)[1].strip().lower()
                    # done peut arriver sans data
                    if current_event == "done":
                        break
                    continue

                if not line.startswith("data:"):
                    continue

                data_str = line.split("data:", 1)[1].strip()
                try:
                    data = json.loads(data_str) if data_str else {}
                except Exception:
                    continue

                if current_event == "error":
                    st.error(f"Erreur: {data}")
                    st.stop()

                # Ignore final
                if current_event == "final":
                    continue

                if current_event == "delta":
                    txt = (data.get("text") or "")
                    if not txt:
                        continue

                    # Dédup
                    if txt == last_chunk:
                        continue
                    last_chunk = txt

                    # Snapshot complet
                    if txt.startswith(full_text):
                        full_text = txt
                    # Vieux snapshot
                    elif full_text.startswith(txt):
                        continue
                    else:
                        full_text += txt

                    placeholder.markdown(full_text)

        if not full_text.strip():
            full_text = "_Aucune réponse._"
            placeholder.markdown(full_text)

        # Add assistant message (une fois)
        messages.append({"role": "assistant", "content": full_text})

# -------------------------
# Header
# -------------------------
active = st.session_state.active_ui_agent

st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="topbar">
      <div class="brand">
        <img src="{LOGO_URL}" />
        <div>
          <p class="t">PLATEFORME IA AGENTIQUE</p>
          <p class="s">Assistant commercial intelligent</p>
        </div>
      </div>
      <div class="agent-pill">
        {UI_ICON[active]} Agent actif : {UI_NAME[active]}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Cards agents (auto depuis AGENTS)
# -------------------------
cols = st.columns(len(AGENTS), gap="large")

def agent_card(col, ui_key: str):
    is_active = (st.session_state.active_ui_agent == ui_key)
    card_cls = "bi-card active" if is_active else "bi-card"

    with col:
        st.markdown(
            f"""
            <div class="{card_cls}">
              <div class="bi-top">
                <div>
                  <div class="bi-h3">{UI_ICON[ui_key]} {UI_NAME[ui_key]}</div>
                  <div class="bi-mini">Agent intelligent</div>
                </div>
                <div class="bi-ico">{UI_ICON[ui_key]}</div>
              </div>
              <div class="bi-body">
                <ul class="bi-bullets">
                  <li>Performance commerciale</li>
                  <li>Portefeuille clients</li>
                  <li>Actions recommandées</li>
                </ul>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cta">', unsafe_allow_html=True)
        if is_active:
            st.button("✅ Actif", use_container_width=True, disabled=True, key=f"start_{ui_key}")
        else:
            if st.button("Lancer la discussion", use_container_width=True, key=f"start_{ui_key}"):
                st.session_state.active_ui_agent = ui_key
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

for col, agent in zip(cols, AGENTS):
    agent_card(col, agent["ui_key"])

st.markdown("<hr/>", unsafe_allow_html=True)

# -------------------------
# Chat history (agent actif)
# -------------------------
active = st.session_state.active_ui_agent
messages = st.session_state.messages_by_agent[active]

for m in messages:
    avatar = "🧑‍💼" if m["role"] == "user" else UI_ICON[active]
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])

prompt = st.chat_input(f"Écrire à {UI_NAME[active]}… (Entrée pour envoyer)")
if prompt:
    run_stream(active, prompt)


