import streamlit as st
import requests, json
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Radar de Tendências", page_icon="📡", layout="wide")

PERSPECTIVAS = [
    ("Acadêmica",           ["arxiv.org", "nature.com", "ieee.org", "sciencedirect.com"]),
    ("Consultoria",         ["gartner.com", "mckinsey.com", "deloitte.com"]),
    ("Órgão internacional", ["weforum.org", "oecd.org"]),
    ("Notícia",             ["technologyreview.com", "wired.com", "zdnet.com"]),
    ("Corporativa",         ["blogs.nvidia.com", "research.ibm.com", "research.google"]),
]
CANON = [("Acadêmica", "#4FD1E0"), ("Consultoria", "#F5A623"),
         ("Órgão internacional", "#34D399"), ("Notícia", "#B794F6"), ("Corporativa", "#7DD3FC")]

# ---------- ESTILO ----------
CSS = """
<style>
.block-container{max-width:960px;padding-top:2rem}
.stApp{background:#0B1220}
.rcard{background:#121C2E;border:1px solid #26324B;border-radius:12px;padding:16px;margin-top:12px}
.eyebrow{font-size:11px;color:#5C6C8C;letter-spacing:.6px;font-family:ui-monospace,monospace;margin-bottom:8px}
.rtitle{font-size:26px;font-weight:800;letter-spacing:-.5px;color:#E7ECF6}
.body{font-size:15px;line-height:1.55;color:#E7ECF6;margin:0}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.pill{background:#1A2740;border:1px solid #26324B;border-radius:999px;padding:5px 12px;font-size:13px;display:inline-block;margin:3px 4px 0 0;color:#E7ECF6}
ul.rl{margin:0;padding:0;list-style:none}
ul.rl li{font-size:13.5px;line-height:1.45;margin-bottom:7px;color:#E7ECF6;padding-left:14px;position:relative}
ul.rl li:before{content:"";position:absolute;left:0;top:7px;width:5px;height:5px;border-radius:99px;background:var(--d)}
.conf{text-align:right}
.conf .k{font-size:11px;color:#5C6C8C;font-family:ui-monospace,monospace}
.conf .v{font-size:22px;font-weight:800}
.conf .n{font-size:12px;color:#8A99B5}
.covgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}
.cov{text-align:center;padding:10px 4px;border-radius:9px}
.cov .cd{width:8px;height:8px;border-radius:99px;margin:0 auto 7px}
.cov .cl{font-size:11px;line-height:1.2}
.cov .cn{font-size:15px;font-weight:800;margin-top:3px}
.covnote{font-size:11.5px;color:#5C6C8C;margin-top:10px;line-height:1.45}
.mtrack{position:relative;height:8px;background:#1A2740;border-radius:999px;margin-top:6px}
.mfill{position:absolute;left:0;top:0;bottom:0;border-radius:999px;background:linear-gradient(90deg,#4FD1E0,#F5A623)}
.mknob{position:absolute;top:-3px;width:14px;height:14px;border-radius:999px;background:#E7ECF6;border:2px solid #0B1220}
.mscale{display:flex;justify-content:space-between;font-size:10.5px;color:#5C6C8C;margin-top:6px;font-family:ui-monospace,monospace}
.src{display:flex;align-items:center;gap:12px;padding:8px 0;border-top:1px solid #26324B;text-decoration:none}
.src:first-child{border-top:none}
.tag{font-size:10.5px;font-weight:700;border:1px solid #26324B;border-radius:6px;padding:2px 7px;white-space:nowrap}
.sti{font-size:13px;color:#E7ECF6;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.synth{background:#121C2E;border:1px solid #26324B;border-radius:12px;padding:16px;margin-top:12px}
.rec{background:#161D2E;border:1px solid #26324B;border-left:4px solid #F5A623;border-radius:12px;padding:16px;margin-top:12px}
</style>
"""

def esc(x):
    return (str(x) if x is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def cor(s):
    return "#34D399" if s >= 67 else "#F5A623" if s >= 34 else "#F87171"

# ---------- 0. PLANEJAR BUSCAS (inglês + português) ----------
@st.cache_data(show_spinner=False)
def planejar_queries(tema):
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}"},
        json={"model": "deepseek/deepseek-chat", "temperature": 0.3,
              "messages": [{"role": "user", "content":
                f'O tema é: "{tema}". Gere consultas de busca curtas e específicas para esse tema '
                f'no contexto tecnológico/industrial: 3 em INGLÊS e 2 em PORTUGUÊS. '
                f'Responda APENAS um array JSON de strings, sem rótulos de idioma.'}]},
        timeout=60)
    txt = r.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(txt[txt.index("["): txt.rindex("]") + 1])
    except Exception:
        return [tema]

# ---------- 1. COLETA (paralela) ----------
def _uma_busca(tipo, dominios, q):
    try:
        r = requests.post("https://api.tavily.com/search", json={
            "api_key": st.secrets["TAVILY_API_KEY"], "query": q,
            "search_depth": "advanced", "max_results": 1, "include_domains": dominios}, timeout=30)
        return [{"titulo": res.get("title", ""), "url": res.get("url", ""), "tipo": tipo,
                 "data": res.get("published_date", ""), "trecho": (res.get("content", "") or "")[:400]}
                for res in r.json().get("results", [])]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def coletar(tema):
    queries = planejar_queries(tema)
    tarefas = [(tipo, dominios, q) for tipo, dominios in PERSPECTIVAS for q in queries]
    evidencias = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for resultado in executor.map(lambda t: _uma_busca(*t), tarefas):
            evidencias.extend(resultado)
    vistas, unicas = set(), []
    for e in evidencias:
        if e["url"] and e["url"] not in vistas:
            vistas.add(e["url"]); unicas.append(e)
    return unicas

# ---------- 2. SÍNTESE ----------
PROMPT = """Você é um analista de inteligência tecnológica. Recebe um TEMA e uma lista de EVIDÊNCIAS (titulo, url, tipo, data, trecho). NÃO invente fatos nem fontes; use só as evidências fornecidas.
Consolide, elimine redundâncias, identifique padrões e produza um painel executivo orientado à decisão. Calibre a confiança pela QUANTIDADE, pela DIVERSIDADE de perspectivas (campo "tipo") e pela AUTORIDADE/RECÊNCIA. Poucas fontes ou de uma só perspectiva = confiança baixa; diga isso. A IA apoia a decisão; não a substitui.
Responda com APENAS um JSON válido (sem markdown), em PORTUGUÊS, neste schema:
{"tema":str,"sintese":str,"recomendacao":str,"proximos_passos":[str],"definicao":str,"maturidade":{"estagio":"Emergente|Em ascensão|Em consolidação|Madura","posicao":0-100,"justificativa":str},"aplicacoes":[str],"setores":[str],"players":[str],"investimentos":str,"sinais_adocao":str,"oportunidades":[str],"riscos":[str],"perspectivas":str,"confianca_global":{"score":0-100,"nivel":"Alta|Média|Baixa"},"fontes":[{"titulo":str,"tipo":str,"url":str}]}
Em "sintese", dê o panorama em UMA frase (o quadro geral do tema). Em "recomendacao", NÃO resuma o tema: dê uma decisão acionável para a diretoria, começando com um verbo de ação (ex.: "Iniciar prova de conceito em uma linha piloto", "Monitorar — evidências ainda incipientes", "Priorizar investimento"), coerente com o nível de confiança. Em "proximos_passos", liste de 2 a 3 ações concretas. Em "players", liste empresas e instituições que DESENVOLVEM ou APLICAM a tecnologia (evite consultorias que apenas a analisam). Em "fontes", liste as 10 evidências mais relevantes (reuse as recebidas, mantendo o "tipo" original)."""

@st.cache_data(show_spinner=False)
def sintetizar(tema, ev):
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}"},
        json={"model": "deepseek/deepseek-chat", "temperature": 0.2,
              "messages": [{"role": "system", "content": PROMPT},
                           {"role": "user", "content": f"TEMA: {tema}\n\nEVIDÊNCIAS:\n{json.dumps(ev, ensure_ascii=False)}"}]},
        timeout=90)
    txt = r.json()["choices"][0]["message"]["content"]
    return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])

# ---------- 3. RENDER ----------
def bloco_lista(titulo, itens, dot):
    if not itens: return ""
    lis = "".join(f'<li style="--d:{dot}">{esc(i)}</li>' for i in itens)
    return f'<div class="rcard"><div class="eyebrow">{titulo}</div><ul class="rl">{lis}</ul></div>'

def bloco_texto(titulo, corpo):
    if not corpo: return ""
    return f'<div class="rcard"><div class="eyebrow">{titulo}</div><p class="body" style="font-size:13.5px">{esc(corpo)}</p></div>'

def cobertura(fontes):
    cont = {k: 0 for k, _ in CANON}
    for f in fontes:
        if f.get("tipo") in cont: cont[f["tipo"]] += 1
    cobertos = sum(1 for k, _ in CANON if cont[k] > 0)
    pct = cobertos / len(CANON) * 100
    cells = ""
    for k, c in CANON:
        on = cont[k] > 0
        cells += f'''<div class="cov" style="background:{'#1A2740' if on else 'transparent'};border:1px solid {'#26324B' if on else '#1A2235'};opacity:{1 if on else .45}">
          <div class="cd" style="background:{c if on else '#5C6C8C'}"></div>
          <div class="cl" style="color:{'#E7ECF6' if on else '#5C6C8C'}">{k}</div>
          <div class="cn" style="color:{c if on else '#5C6C8C'}">{cont[k]}</div></div>'''
    return f'''<div class="rcard">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px">
        <span class="eyebrow">COBERTURA DE EVIDÊNCIAS</span>
        <span style="font-size:13px;color:#8A99B5"><b style="color:{cor(pct)}">{cobertos} de 5</b> perspectivas · {len(fontes)} evidências</span>
      </div>
      <div class="covgrid">{cells}</div>
      <div class="covnote">A confiança sobe com o nº de evidências e com quantas perspectivas do ecossistema convergem.</div></div>'''

def render(p):
    g = p.get("confianca_global", {})
    fontes = p.get("fontes", [])
    h = CSS
    h += f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px"><div class="rtitle">{esc(p.get("tema",""))}</div>'
    if "score" in g:
        h += f'<div class="conf"><div class="k">CONFIANÇA</div><div class="v" style="color:{cor(g["score"])}">{g["score"]}<span style="font-size:12px;color:#8A99B5">/100</span></div><div class="n">{esc(g.get("nivel",""))}</div></div>'
    h += '</div>'
    if p.get("sintese"):
        h += f'<div class="synth"><div class="eyebrow">SÍNTESE EXECUTIVA</div><p class="body">{esc(p["sintese"])}</p></div>'
    if p.get("recomendacao"):
        h += f'<div class="rec"><div class="eyebrow" style="color:#F5A623">RECOMENDAÇÃO</div><p class="body" style="font-weight:600">{esc(p["recomendacao"])}</p></div>'
    if fontes: h += cobertura(fontes)
    if p.get("definicao"): h += f'<div class="rcard"><div class="eyebrow">DEFINIÇÃO</div><p class="body">{esc(p["definicao"])}</p></div>'
    m = p.get("maturidade")
    if m:
        pos = max(0, min(100, m.get("posicao", 0)))
        h += f'''<div class="rcard">
          <div style="display:flex;justify-content:space-between;align-items:center"><span class="eyebrow">NÍVEL DE MATURIDADE</span><b style="font-size:13px;color:#F5A623">{esc(m.get("estagio",""))}</b></div>
          <div class="mtrack"><div class="mfill" style="width:{pos}%"></div><div class="mknob" style="left:calc({pos}% - 6px)"></div></div>
          <div class="mscale"><span>EMERGENTE</span><span>ASCENSÃO</span><span>CONSOLIDAÇÃO</span><span>MADURA</span></div>
          <p style="font-size:13.5px;color:#8A99B5;margin-top:10px">{esc(m.get("justificativa",""))}</p></div>'''
    h += f'<div class="row2">{bloco_lista("APLICAÇÕES", p.get("aplicacoes"), "#4FD1E0")}{bloco_lista("SETORES IMPACTADOS", p.get("setores"), "#F5A623")}</div>'
    if p.get("players"):
        pills = "".join(f'<span class="pill">{esc(x)}</span>' for x in p["players"])
        h += f'<div class="rcard"><div class="eyebrow">PLAYERS E INSTITUIÇÕES</div><div>{pills}</div></div>'
    h += f'<div class="row2">{bloco_texto("INVESTIMENTOS E MERCADO", p.get("investimentos"))}{bloco_texto("SINAIS DE ADOÇÃO", p.get("sinais_adocao"))}</div>'
    h += f'<div class="row2">{bloco_lista("OPORTUNIDADES", p.get("oportunidades"), "#34D399")}{bloco_lista("DESAFIOS E RISCOS", p.get("riscos"), "#F87171")}</div>'
    if p.get("perspectivas"): h += f'<div class="rcard"><div class="eyebrow">PERSPECTIVAS FUTURAS</div><p class="body">{esc(p["perspectivas"])}</p></div>'
    if p.get("proximos_passos"):
        h += bloco_lista("PRÓXIMOS PASSOS", p.get("proximos_passos"), "#F5A623")
    if fontes:
        rows = ""
        for f in fontes:
            c = dict(CANON).get(f.get("tipo"), "#5C6C8C")
            rows += f'<a class="src" href="{esc(f.get("url"))}" target="_blank"><span class="tag" style="color:{c}">{esc((f.get("tipo") or "Outra").upper())}</span><span class="sti">{esc(f.get("titulo"))}</span><span style="color:#5C6C8C">↗</span></a>'
        h += f'<div class="rcard"><div class="eyebrow">BASE DE EVIDÊNCIAS · {len(fontes)} FONTES VERIFICÁVEIS</div>{rows}</div>'
    st.markdown(h, unsafe_allow_html=True)

# ---------- UI ----------
st.markdown(CSS, unsafe_allow_html=True)
st.markdown('<div class="rtitle">📡 Radar de Tendências Tecnológicas</div>', unsafe_allow_html=True)
st.caption("Painel executivo fundamentado em evidências")
tema = st.text_input("Tema", placeholder="Ex.: Eficiência Energética na Indústria 4.0")

if st.button("Gerar painel", type="primary") and tema:
    with st.spinner("Planejando buscas e coletando evidências…"):
        ev = coletar(tema)
    if not ev:
        st.error("Nenhuma evidência coletada. Verifique a chave do Tavily."); st.stop()
    with st.spinner("Sintetizando com IA…"):
        p = sintetizar(tema, ev)
    render(p)
