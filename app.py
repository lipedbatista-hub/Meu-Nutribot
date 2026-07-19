import streamlit as st
import pandas as pd
import math
import os
from datetime import datetime
import google.generativeai as genai

# Configuração da página do site
st.set_page_config(page_title="Meu NutriBot IA", page_icon="🍏", layout="centered")

# Arquivos de banco de dados locais (salvos no servidor do site)
ARQUIVO_PERFIL = 'historico_perfil.csv'
ARQUIVO_DIARIO = 'diario_alimentos.csv'

# Inicializa os arquivos com as colunas corretas se eles não existirem
if not os.path.exists(ARQUIVO_PERFIL):
    pd.DataFrame(columns=['Data', 'Sexo', 'Idade', 'Altura', 'Peso_Atual', 'Peso_Meta', 'Atividade', 'Meta_Calorica']).to_csv(ARQUIVO_PERFIL, index=False)
if not os.path.exists(ARQUIVO_DIARIO):
    pd.DataFrame(columns=['Data', 'Refeicao', 'Calorias']).to_csv(ARQUIVO_DIARIO, index=False)

# Título do Site
st.title("🍏 Meu NutriBot Inteligente")
st.markdown("Controle de peso, metas e inteligência artificial para calorias.")

# --- PAINEL LATERAL: CONFIGURAÇÕES E CHAVE API ---
st.sidebar.header("🔑 Configurações do Sistema")
chave_api = st.sidebar.text_input("Sua Chave Gemini (AI Studio)", type="password")

st.sidebar.subheader("⚖️ Seus Dados de Saúde")
df_p = pd.read_csv(ARQUIVO_PERFIL)

# Carrega os valores padrão do último registro salvo (se houver)
p_peso = 70.0 if df_p.empty else float(df_p.iloc[-1]['Peso_Atual'])
p_meta = 65.0 if df_p.empty else float(df_p.iloc[-1]['Peso_Meta'])
p_idade = 25 if df_p.empty else int(df_p.iloc[-1]['Idade'])
p_altura = 170 if df_p.empty else int(df_p.iloc[-1]['Altura'])

# Campos visuais para o usuário preencher na barra lateral
sexo = st.sidebar.selectbox("Sexo", ["Feminino", "Masculino"], index=0 if df_p.empty or df_p.iloc[-1]['Sexo'] == "Feminino" else 1)
idade = st.sidebar.number_input("Idade (anos)", value=p_idade)
altura = st.sidebar.number_input("Altura (cm)", value=p_altura)
peso_atual = st.sidebar.number_input("Peso Atual (kg)", value=p_peso, step=0.1)
peso_meta = st.sidebar.number_input("Sua Meta de Peso (kg)", value=p_meta, step=0.1)
atividade = st.sidebar.selectbox("Nível de Atividade", ["Sedentário", "Leve", "Moderado", "Intenso"])

# Fórmulas de Nutrição (Mifflin-St Jeor)
fatores = {"Sedentário": 1.2, "Leve": 1.375, "Moderado": 1.55, "Intenso": 1.725}
fator = fatores[atividade]
tmb = (10 * peso_atual) + (6.25 * altura) - (5 * idade) + (5 if sexo == "Masculino" else -161)
get = tmb * fator

# Cálculo da Estratégia de Calorias e do Tempo Restante
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

# Botão para salvar alterações de peso
if st.sidebar.button("💾 Salvar/Atualizar Peso"):
    novo_p = pd.DataFrame([{'Data': datetime.now().strftime('%Y-%m-%d'), 'Sexo': sexo, 'Idade': idade, 'Altura': altura, 'Peso_Atual': peso_atual, 'Peso_Meta': peso_meta, 'Atividade': atividade, 'Meta_Calorica': round(meta_calorica)}])
    pd.concat([df_p, novo_p], ignore_index=True).to_csv(ARQUIVO_PERFIL, index=False)
    st.sidebar.success("Dados de peso atualizados!")
    st.rerun()

# --- CORPO PRINCIPAL DO SITE ---
col1, col2, col3 = st.columns(3)
col1.metric("Peso Atual", f"{peso_atual} kg")
col2.metric("Meta Final", f"{peso_meta} kg")
col3.metric("Tempo Restante", f"{dias_restantes} dias" if dias_restantes > 0 else "Na Meta! 🎉")

# Processamento e exibição das calorias do dia atual
df_d = pd.read_csv(ARQUIVO_DIARIO)
hoje_str = datetime.now().strftime('%Y-%m-%d')
df_d['Data_Curta'] = df_d['Data'].str.slice(0, 10)
comido_hoje = df_d[df_d['Data_Curta'] == hoje_str]['Calorias'].sum()
restante = round(meta_calorica) - comido_hoje

st.subheader("🔥 Contador de Calorias")
c_meta, c_comido, c_resta = st.columns(3)
c_meta.markdown(f"**Sua Meta:**  \n{round(meta_calorica)} kcal")
c_comido.markdown(f"**Consumido:**  \n{comido_hoje} kcal")
c_resta.markdown(f"### **Disponível:**  \n## {restante} kcal")

st.markdown("---")

# Caixa de texto para o usuário digitar a refeição de forma livre
st.subheader("📝 Adicionar Alimento com IA")
texto_comida = st.text_input("O que você comeu?", placeholder="Ex: Cuscuz com 2 ovos e um copo de café com leite")

if st.button("Analisar e Registrar comida 🤖"):
    if not chave_api:
        st.error("Por favor, insira sua chave da API do Gemini no menu lateral.")
    elif not texto_comida:
        st.warning("Digite o que você comeu antes de enviar.")
    else:
        with st.spinner("A IA está calculando as calorias..."):
            try:
                # --- CONFIGURAÇÃO E CHAMADA DA API DO GEMINI ---
                genai.configure(api_key=chave_api)
                
                # Definição do comportamento (System Instruction)
                instrucao_sistema = (
                    "Você é um nutricionista focado em contagem de calorias. O usuário vai dizer o que comeu. "
                    "Estime o total de calorias. Responda APENAS com o número inteiro estimado de calorias da refeição, "
                    "absolutamente nada mais. Se não for comida, responda 0."
                )
                
                # Atualizado para o modelo de produção mais recente e gratuito
                model = genai.GenerativeModel(
                    model_name="gemini-3.1-flash-lite",
                    system_instruction=instrucao_sistema
                )
                
                # Envia o prompt para o modelo
                response = model.generate_content(texto_comida)
                texto_resposta = response.text.strip()
                
                # Filtra apenas os números da resposta da IA
                calorias = int(''.join(filter(str.isdigit, texto_resposta)) or 0)
                
                # Salva a refeição no histórico do diário
                novo_alimento = pd.DataFrame([{'Data': datetime.now().strftime('%Y-%m-%d %H:%M'), 'Refeicao': texto_comida, 'Calorias': calorias}])
                pd.concat([df_d, novo_alimento], ignore_index=True).drop(columns=['Data_Curta'], errors='ignore').to_csv(ARQUIVO_DIARIO, index=False)
                
                st.success(f"Registrado com sucesso! +{calorias} kcal adicionadas.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao conectar com a IA: {e}")

# Lista na tela todos os alimentos consumidos no dia de hoje
st.markdown("---")
st.subheader("📋 Consumido Hoje")
hoje_comidas = df_d[df_d['Data_Curta'] == hoje_str]
if hoje_comidas.empty:
    st.info("Nenhum alimento registrado hoje.")
else:
    for idx, row in hoje_comidas.iterrows():
        st.write(f"• **{row['Refeicao']}** — {row['Calorias']} kcal")
