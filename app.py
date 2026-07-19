import streamlit as st
import pandas as pd
import math
from datetime import datetime, date
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# Configuração da página do site
st.set_page_config(page_title="Meu NutriBot IA", page_icon="🍏", layout="centered")

# Título do Site
st.title("🍏 Meu NutriBot Inteligente")
st.markdown("Controle de peso, metas e inteligência artificial para calorias.")

# --- CONEXÃO INVISÍVEL E SEGURA (GOOGLE SHEETS E GEMINI) ---
try:
    ID_PLANILHA = st.secrets["ID_PLANILHA"]
    CHAVE_GEMINI = st.secrets["GEMINI_API_KEY"]
    URL_SUSH = f"https://google.com{ID_PLANILHA}"
except Exception as e:
    st.error("Erro crítico de inicialização. Por favor, configure os Secrets no painel do Streamlit Cloud.")
    st.stop()

# Inicializa conexão nativa com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE BUSCA DE DADOS ---
def carregar_dados_perfil():
    try:
        df = conn.read(spreadsheet=URL_SUSH, worksheet="perfil", ttl=0)
        return pd.DataFrame(df)
    except Exception:
        return pd.DataFrame(columns=['data', 'sexo', 'idade', 'altura', 'peso_atual', 'peso_meta', 'atividade', 'meta_calorica'])

def carregar_dados_diario():
    try:
        df = conn.read(spreadsheet=URL_SUSH, worksheet="diario", ttl=0)
        return pd.DataFrame(df)
    except Exception:
        return pd.DataFrame(columns=['data', 'refeicao', 'calorias'])

df_p = carregar_dados_perfil()
df_d = carregar_dados_diario()

# --- PAINEL LATERAL: DADOS DE SAÚDE ---
st.sidebar.header("⚖️ Seus Dados de Saúde")

p_peso = 70.0 if df_p.empty else float(df_p.iloc[-1]['peso_atual'])
p_meta = 65.0 if df_p.empty else float(df_p.iloc[-1]['peso_meta'])
p_idade = 25 if df_p.empty else int(df_p.iloc[-1]['idade'])
p_altura = 170 if df_p.empty else int(df_p.iloc[-1]['altura'])

sexo = st.sidebar.selectbox("Sexo", ["Feminino", "Masculino"], index=0 if df_p.empty or df_p.iloc[-1]['sexo'] == "Feminino" else 1)
idade = st.sidebar.number_input("Idade (anos)", value=p_idade)
altura = st.sidebar.number_input("Altura (cm)", value=p_altura)
peso_atual = st.sidebar.number_input("Peso Atual (kg)", value=p_peso, step=0.1)
peso_meta = st.sidebar.number_input("Sua Meta de Peso (kg)", value=p_meta, step=0.1)

lista_atividades = ["Sedentário", "Leve", "Moderado", "Intenso"]
index_atividade = lista_atitudes.index(df_p.iloc[-1]['atividade']) if not df_p.empty and df_p.iloc[-1]['atividade'] in lista_atividades else 0
atividade = st.sidebar.selectbox("Nível de Atividade", lista_atividades, index=index_atividade)

# Fórmulas de Nutrição
fatores = {"Sedentário": 1.2, "Leve": 1.375, "Moderado": 1.55, "Intenso": 1.725}
fator = fatores[atividade]
tmb = (10 * peso_atual) + (6.25 * altura) - (5 * idade) + (5 if sexo == "Masculino" else -161)
get = tmb * fator

peso_a_mudar = peso_meta - peso_atual
if peso_a_mudar < 0:
    meta_calorica = get - 500
    dias_restantes = math.ceil((abs(peso_a_mudar) * 7700) / 500)
elif peso_a_mudar > 0:
    meta_calorica = get + 300
    dias_restantes = math.ceil((abs(peso_a_mudar) * 7700) / 300)
else:
    meta_calorica = get
    dias_restantes = 0

# GRAVAÇÃO DO PESO NA PLANILHA
if st.sidebar.button("💾 Salvar/Atualizar Peso"):
    novo_p = pd.DataFrame([{
        'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'sexo': sexo, 'idade': int(idade), 
        'altura': int(altura), 'peso_atual': float(peso_atual), 'peso_meta': float(peso_meta), 
        'atividade': atividade, 'meta_calorica': int(round(meta_calorica))
    }])
    df_p_novo = pd.concat([df_p, novo_p], ignore_index=True)
    conn.update(spreadsheet=URL_SUSH, worksheet="perfil", data=df_p_novo)
    st.sidebar.success("Dados de peso gravados na planilha Google!")
    st.rerun()

# --- CORPO PRINCIPAL DO SITE ---
col1, col2, col3 = st.columns(3)
col1.metric("Peso Atual", f"{peso_atual} kg")
col2.metric("Meta Final", f"{peso_meta} kg")
col3.metric("Tempo Restante", f"{dias_restantes} dias" if dias_restantes > 0 else "Na Meta! 🎉")

hoje_str = datetime.now().strftime('%Y-%m-%d')
comido_hoje = 0

if not df_d.empty:
    df_d['Data_Curta'] = pd.to_datetime(df_d['data']).dt.strftime('%Y-%m-%d')
    comido_hoje = df_d[df_d['Data_Curta'] == hoje_str]['calorias'].sum()

restante = round(meta_calorica) - comido_hoje

st.subheader("🔥 Contador de Calorias")
c_meta, c_comido, c_resta = st.columns(3)
c_meta.markdown(f"**Sua Meta:**  \n{round(meta_calorica)} kcal")
c_comido.markdown(f"**Consumido:**  \n{comido_hoje} kcal")
c_resta.markdown(f"### **Disponível:**  \n## {restante} kcal")

st.markdown("---")

st.subheader("📝 Adicionar Alimento com IA")
texto_comida = st.text_input("O que você comeu?", placeholder="Ex: Cuscuz com 2 ovos")

# GRAVAÇÃO DA COMIDA NA PLANILHA VIA IA
if st.button("Analisar e Gravar Alimento 🤖"):
    if not texto_comida:
        st.warning("Digite o que você comeu antes de enviar.")
    else:
        with st.spinner("A IA está calculando e salvando..."):
            try:
                genai.configure(api_key=CHAVE_GEMINI)
                instrucao_sistema = (
                    "Você é um nutricionista focado em contagem de calorias. O usuário vai dizer o que comeu. "
                    "Estime o total de calorias. Responda APENAS com o número inteiro estimado de calorias da refeição."
                )
                model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite", system_instruction=instrucao_sistema)
                response = model.generate_content(texto_comida)
                calorias = int(''.join(filter(str.isdigit, response.text.strip())) or 0)
                
                novo_alimento = pd.DataFrame([{
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'refeicao': texto_comida,
                    'calorias': calorias
                }])
                df_d_novo = pd.concat([df_d, novo_alimento], ignore_index=True).drop(columns=['Data_Curta'], errors='ignore')
                conn.update(spreadsheet=URL_SUSH, worksheet="diario", data=df_d_novo)
                
                st.success(f"Gravado na planilha! +{calorias} kcal adicionadas.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar: {e}")

# Lista consumidos hoje salvos no Sheets
st.markdown("---")
st.subheader("📋 Consumido Hoje")
hoje_comidas = df_d[df_d['Data_Curta'] == hoje_str] if not df_d.empty else pd.DataFrame()

if hoje_comidas.empty:
    st.info("Nenhum alimento registrado hoje.")
else:
    for idx, row in hoje_comidas.iterrows():
        col_txt, col_btn = st.columns([0.85, 0.15])
        with col_txt:
            st.markdown(f"• **{row['refeicao']}** — {row['calorias']} kcal")
        with col_btn:
            if st.button("🗑️", key=f"del_{idx}"):
                df_limpo = df_d.drop(idx).drop(columns=['Data_Curta'], errors='ignore')
                conn.update(spreadsheet=URL_SUSH, worksheet="diario", data=df_limpo)
                st.rerun()

# --- HISTÓRICO COMPLETO ---
st.markdown("---")
st.subheader("📅 Histórico Completo de Registros")

if df_d.empty:
    st.info("O banco de dados na planilha ainda está vazio.")
else:
    periodo = st.date_input("Filtrar por data", value=[date.today(), date.today()], key="filtro_datas")
    if isinstance(periodo, (list, tuple)) and len(periodo) == 2:
        data_inicio, data_fim = periodo
        df_historico = df_d.copy()
        df_historico['Data_Objeto'] = pd.to_datetime(df_historico['data']).dt.date
        df_filtrado = df_historico[(df_historico['Data_Objeto'] >= data_inicio) & (df_historico['Data_Objeto'] <= data_fim)]
        
        if df_filtrado.empty:
            st.warning("Nenhum registro encontrado para este período.")
        else:
            total_periodo = df_filtrado['calorias'].sum()
            st.markdown(f"**Total consumido no período selecionado:** {total_periodo} kcal")
            df_exibicao = df_filtrado[['data', 'refeicao', 'calorias']].rename(columns={
                'data': 'Data e Hora', 'refeicao': 'Refeição consumida', 'calorias': 'Calorias (kcal)'
            })
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
