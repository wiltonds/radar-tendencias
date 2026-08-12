import streamlit as st
import requests, json

st.set_page_config(page_title="Radar de Tendências", page_icon="📡", layout="centered")

# As 5 perspectivas do ecossistema (fonte por tipo)
PERSPECTIVAS = [
    ("Acadêmica",            ["arxiv.org", "nature.com", "ieee.org", "sciencedirect.com"]),
    ("Consultoria",          ["gartner.com", "mckinsey.com", "deloitte.com"]),
    ("Órgão internacional",  ["weforum.org", "oecd.org"]),
    ("Notícia",              ["technologyreview.com", "wired.com", "zdnet.com"]),
    ("Corporativa",          ["blogs.nvidia.com", "research.ibm.com", "research.google"]),
]

# ---------- 1. COLETA (Tavily) ----------
def coletar(tema):
    evidencias = []
    for tipo, dominios in PERSPECTIVAS:
        try:
            r = requests.post("https://api.tavily.com/search", json={
                "api_key": st.secrets["TAVILY_API_KEY"],
                "query": tema,
                "search_depth": "advanced",
                "max_results": 3,
                "include_domains": dominios,
            }, timeout=30)
            for res in r.json().get("results", []):
                evidencias.append({
                    "titulo": res.get("title", ""),
                    "url": res.get("url", ""),
                    "tipo": tipo,
                    "data": res.get("published_date", ""),
                    "trecho": (res.get("content", "") or "")[:400],
                })
        except Exception as e:
            st.warning(f"Falha na coleta ({tipo}): {e}")
    return evidencias

# ---------- 2. SÍNTESE (LLM via OpenRouter) ----------
PROMPT = """Você é um analista de inteligência tecnológica. Recebe um TEMA e uma lista de EVIDÊNCIAS já coletadas (titulo, url, tipo, data, trecho). NÃO invente fatos nem fontes; use só as evidências fornecidas.
Consolide as evidências, elimine redundâncias, identifique padrões e produza um painel executivo. Calibre a confiança pela QUANTIDADE, pela DIVERSIDADE de perspectivas (campo "tipo") e pela AUTORIDADE/RECÊNCIA. Poucas fontes ou de uma só perspectiva = confiança baixa; diga isso.
Responda com APENAS um objeto JSON válido (sem markdown), em PORTUGUÊS, neste schema:
{"tema":str,"definicao":str,"maturidade":{"estagio":"Emergente|Em ascensão|Em consolidação|Madura","posicao":0-100,"justificativa":str},"aplicacoes":[str],"setores":[str],"players":[str],"investimentos":str,"sinais_adocao":str,"oportunidades":[str],"riscos":[str],"perspectivas":str,"confianca_global":{"score":0-100,"nivel":"Alta|Média|Baixa"},"fontes":[{"titulo":str,"tipo":str,"url":str}]}"""

def sintetizar(tema, evidencias):
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}"},
        json={
            "model": "deepseek/deepseek-chat",
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": f"TEMA: {tema}\n\nEVIDÊNCIAS:\n{json.dumps(evidencias, ensure_ascii=False)}"},
            ],
        }, timeout=90)
    txt = r.json()["choices"][0]["message"]["content"]
    return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])

# ---------- 3. PAINEL ----------
st.title("📡 Radar de Tendências Tecnológicas")
st.caption("Painel executivo fundamentado em evidências")
tema = st.text_input("Tema", placeholder="Ex.: Edge AI")

if st.button("Gerar painel") and tema:
    with st.spinner("Coletando evidências em múltiplas perspectivas…"):
        ev = coletar(tema)
    if not ev:
        st.error("Nenhuma evidência coletada. Verifique a chave do Tavily.")
        st.stop()
    with st.spinner("Sintetizando com IA…"):
        p = sintetizar(tema, ev)

    # cobertura de perspectivas (calculada no código, não pelo LLM)
    tipos = {f["tipo"] for f in p.get("fontes", [])}
    st.markdown(f"### {p['tema']}")
    c1, c2 = st.columns(2)
    c1.metric("Confiança", f"{p['confianca_global']['score']}/100", p['confianca_global']['nivel'])
    c2.metric("Perspectivas cobertas", f"{len(tipos)} de 5")

    st.subheader("Definição");        st.write(p["definicao"])
    m = p["maturidade"]
    st.subheader("Maturidade");       st.write(f"**{m['estagio']}** — {m['justificativa']}")
    st.subheader("Aplicações");       st.write(", ".join(p["aplicacoes"]))
    st.subheader("Setores");          st.write(", ".join(p["setores"]))
    st.subheader("Players");          st.write(", ".join(p["players"]))
    st.subheader("Investimentos");    st.write(p["investimentos"])
    st.subheader("Sinais de adoção"); st.write(p["sinais_adocao"])
    st.subheader("Oportunidades");    st.write("\n".join(f"- {x}" for x in p["oportunidades"]))
    st.subheader("Riscos");           st.write("\n".join(f"- {x}" for x in p["riscos"]))
    st.subheader("Perspectivas");     st.write(p["perspectivas"])
    st.subheader("Fontes verificáveis")
    for f in p["fontes"]:
        st.markdown(f"`{f['tipo']}` [{f['titulo']}]({f['url']})")
