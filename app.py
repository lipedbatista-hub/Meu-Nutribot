import streamlit as st
import pandas as pd
import math
import urllib.request
import urllib.parse
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Tenta importar o pacote google.generativeai de forma defensiva
try:
    import google.generativeai as genai
except ImportError:
    st.error("Biblioteca 'google-generativeai' não encontrada. Verifique o seu requirements.txt no GitHub.")
    st.stop()

# Configuração da página do site
st.set_page_config(page_title="Meu NutriBot IA", page_icon="🍏", layout="centered")

st.title("🍏 Meu NutriBot Inteligente")
st.markdown("Controle de peso, metas e inteligência artificial para calorias.")

# --- CONEXÃO INVISÍVEL E SEGURA COM OS SECRETS ---
try:
    CHAVE_GEMINI = st.secrets["GEMINI_API_KEY"]
    JSONBIN_KEY = st.secrets["JSONBIN_KEY"]
    
    # Limpa rigorosamente o ID de qualquer caractere inválido ou espaço extra enviado pelo celular
    BIN_ID = str(st.secrets["BIN_ID"]).strip().replace("/", "").replace(" ", "").replace("\n", "").replace("\r", "")
    
    # ENDEREÇOS FIXOS DO SERVIDOR JSONBIN TRAVADOS E SEPARADOS
    URL_LEITURA = f"https://jsonbin.io{BIN_ID}/latest"
    URL_ESCRITA = f"https://jsonbin.io{BIN_ID}"
    
    HEADERS = {
        "X-Master-Key": JSONBIN_KEY, 
        "Content-Type": "application/json"
    }
except Exception:
    st.error("Erro crítico de chaves: Verifique se GEMINI_API_KEY, JSONBIN_KEY e BIN_ID estão salvos nos Secrets do Streamlit Cloud.")
    st.stop()

# --- AJUSTE DE FUSO HORÁRIO SEGURO (SÃO PAULO) ---
def obter_data_hora_brasil():
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

# --- FUNÇÕES DE SALVAMENTO NATIVAS (SEM REQUEStS) ---
def carregar_nuvem():
    try:
        url_dinamica = f"{URL_LEITURA}?nocache={obter_data_hora_brasil().timestamp()}"
        req = urllib.request.Request(url_dinamica, headers=HEADERS, method='GET')
        with urllib.request.urlopen(req, timeout=7) as resposta:
            conteudo = json.loads(resposta.read().decode('utf-8'))
            record = conteudo.get("record", {})
            
            if isinstance(record, str):
                record = json.loads(record)
                
            perfil = record.get("perfil", [])
            diario = record.get("diario", [])
            return list(perfil), list(diario)
    except Exception:
        pass
    return [], []

def salvar_nuvem(perfil, diario):
    try:
        payload = json.dumps({"perfil": list(perfil), "diario": list(diario)}).encode('utf-8')
        req = urllib.request.Request(URL_ESCRITA, data=payload, headers=HEADERS, method='PUT')
        with urllib.request.urlopen(req, timeout=7) as resposta:
            return resposta.status == 200
    except Exception as e:
        st.error(f"Falha na gravação remota: {e}")
        return False

# --- CONTROLE SÍNCRONO DE INICIALIZAÇÃO ---
if "dados_sincronizados" not in st.session_state:
    with st.spinner("Conectando ao banco de dados estável..."):
        banco_perfil, banco_diario = carregar_nuvem()
        st.session_state.banco_perfil = banco_perfil
        st.session_state.banco_diario = banco_diario
        st.session_state.dados_sincronizados = True

# Cria os DataFrames estruturados garantindo a existência das colunas base desde o início
df_p = pd.DataFrame(st.session_state.banco_perfil, columns=['data', 'sexo', 'idade', 'altura', 'peso_atual', 'peso_meta', 'atividade', 'meta_calorica'])
df_d = pd.DataFrame(st.session_state.banco_diario, columns=['data', 'refeicao', 'calorias'])

if not df_d.empty:
    df_d['calorias'] = pd.to_numeric(df_d['calorias'], errors='coerce').fillna(0).astype(int)

# --- PAINEL LATERAL: DADOS DE SAÚDE ---
st.sidebar.header("⚖️ Seus Dados de Saúde")

p_peso, p_meta, p_idade, p_altura, v_sexo, val_at = 70.0, 65.0, 25, 170, "Feminino", "Sedentário"

if len(st.session_state.banco_perfil) > 0:
    ultimo_p = st.session_state.banco_perfil[-1]
    p_peso = float(ultimo_p.get('peso_atual', 70.0))
    p_meta = float(ultimo_p.get('peso_meta', 65.0))
    p_idade = int(ultimo_p.get('idade', 25))
    p_altura = int(ultimo_p.get('altura', 170))
    v_sexo = str(ultimo_p.get('sexo', 'Feminino'))
    val_at = str(ultimo_p.get('atividade', 'Sedentário'))

sexo = st.sidebar.selectbox("Sexo", ["Feminino", "Masculino"], index=0 if v_sexo == "Feminino" else 1)
idade = st.sidebar.number_input("Idade (anos)", value=p_idade)
altura = st.sidebar.number_input("Altura (cm)", value=p_altura)
peso_atual = st.sidebar.number_input("Peso Atual (kg)", value=p_peso, step=0.1)
peso_meta = st.sidebar.number_input("Sua Meta de Peso (kg)", value=p_meta, step=0.1)

lista_atividades = ["Sedentário", "Leve", "Moderado", "Intenso"]
index_atividade = lista_atividades.index(val_at) if val_at in lista_atividades else 0
atividade = st.sidebar.selectbox("Nível de Atividade", lista_atividades, index=index_atividade)

# Fórmulas de Nutrição
fatores = {"Sedentário": 1.2, "Leve": 1.375, "Moderado": 1.55, "Intenso": 1.725}
fator = fatores[atividade]
tmb = (10 * peso_atual) + (6.25 * altura) - (5 * idade) + (5 if sexo == "Masculino" else -161)
get = tmb * fator

# Cálculo da Estratégia de Peso
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

if st.sidebar.button("💾 Salvar/Atualizar Peso"):
    novo_p = {
        'data': obter_data_hora_brasil().strftime('%Y-%m-%d %H:%M:%S'), 
        'sexo': sexo, 
        'idade': int(idade), 
        'altura': int(altura), 
        'peso_atual': float(peso_atual), 
        'peso_meta': float(peso_meta), 
        'atividade': atividade, 
        'meta_calorica': int(round(meta_calorica))
    }
    
    lista_perfil_temp = list(st.session_state.banco_perfil) + [novo_p]
    if salvar_nuvem(lista_perfil_temp, st.session_state.banco_diario):
        st.session_state.banco_perfil = lista_perfil_temp
        st.sidebar.success("Dados de peso fixados na nuvem!")
        st.rerun()

# --- CORPO PRINCIPAL DO SITE ---
col1, col2, col3 = st.columns(3)
col1.metric("Peso Atual", f"{peso_atual} kg")
col2.metric("Meta Final", f"{peso_meta} kg")
col3.metric("Tempo Restante", f"{dias_restantes} dias" if dias_restantes > 0 else "Na Meta! 🎉")

hoje_str = obter_data_hora_brasil().strftime('%Y-%m-%d')
comido_hoje = 0

# Processamento seguro da coluna de data curta contra tabelas vazias
if len(st.session_state.banco_diario) > 0:
    df_d['Data_Curta'] = df_d['data'].astype(str).str.slice(0, 10)
    comido_hoje = df_d[df_d['Data_Curta'] == hoje_str]['calorias'].sum()
else:
    df_d['Data_Curta'] = pd.Series(dtype='str')

restante = round(meta_calorica) - comido_hoje

st.subheader("🔥 Contador de Calorias")
c_meta, c_comido, c_resta = st.columns(3)
c_meta.markdown(f"**Sua Meta:**  \n{round(meta_calorica)} kcal")
c_comido.markdown(f"**Consumido:**  \n{comido_hoje} kcal")
c_resta.markdown(f"### **Disponível:**  \n## {restante} kcal")

st.markdown("---")

st.subheader("📝 Adicionar Alimento com IA")
texto_comida = st.text_input("O que você comeu?", placeholder="Ex: Cuscuz com 2 ovos")

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
                
                nova_comida = {
                    'data': obter_data_hora_brasil().strftime('%Y-%m-%d %H:%M:%S'),
                    'refeicao': str(texto_comida),
                    'calorias': int(calorias)
                }
                
                lista_diario_temp = list(st.session_state.banco_diario) + [nova_comida]
                if salvar_nuvem(st.session_state.banco_perfil, lista_diario_temp):
                    st.session_state.banco_diario = lista_diario_temp
                    st.success(f"Registrado com sucesso! +{calorias} kcal.")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar com a IA: {e}")

# --- EXIBIÇÃO EM TELA ---
st.markdown("---")
st.subheader("📋 Consumido Hoje")

hoje_comidas = df_d[df_d['Data_Curta'] == hoje_str] if 'Data_Curta' in df_d.columns else pd.DataFrame()

if hoje_comidas.empty:
    st.info("Nenhum alimento registrado hoje.")
else:
    for i, (idx, row) in enumerate(hoje_comidas.iterrows()):
        col_txt, col_btn = st.columns([0.85, 0.15])
        with col_txt:
            st.markdown(f"• **{row['refeicao']}** — {row['calorias']} kcal")
        with col_btn:
            chave_botao = f"btn_del_{i}_{idx}"
            if st.button("🗑️", key=chave_botao):
                string_alvo_data = str(row['data'])
                string_alvo_ref = str(row['refeicao'])
                
                lista_diario_limpa = [
                    item for item in st.session_state.banco_diario 
                    if not (str(item.get('data')) == string_alvo_data and str(item.get('refeicao')) == string_alvo_ref)
                ]
                
                if salvar_nuvem(st.session_state.banco_perfil, lista_diario_limpa):
                    st.session_state.banco_diario = lista_diario_limpa
