import streamlit as st

st.set_page_config(page_title="Radar de Tendências", page_icon="📡", layout="centered")
st.title("📡 Radar de Tendências Tecnológicas")
st.caption("Painel executivo fundamentado em evidências")

tema = st.text_input("Tema", placeholder="Ex.: Edge AI")
if st.button("Gerar painel"):
    st.info(f"Em breve: painel de **{tema}**")
