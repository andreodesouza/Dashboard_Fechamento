from datetime import datetime
import io
import pandas as pd
from fpdf import FPDF
import plotly.express as px
import streamlit as st

# Configuração da página do Dashboard
st.set_page_config(
    page_title="Dashboard Universal de Planilhas", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Universal - Squads, Filas & Automação")
st.markdown(
    "Painel interativo com filtros avançados, divisão Robô x Humano e exportação"
    " em PDF."
)

# --- BOTÃO DE UPLOAD NA BARRA LATERAL ---
st.sidebar.header("📁 Enviar Arquivo")
uploaded_file = st.sidebar.file_uploader(
    "Escolha a planilha (.csv ou .xlsx)", type=["csv", "xlsx"]
)


# Função para carregar os dados
@st.cache_data
def load_data(file):
  if file.name.endswith(".csv"):
    df = pd.read_csv(file, low_memory=False)
  else:
    df = pd.read_excel(file)
  return df


if uploaded_file is None:
  st.info(
      "👈 Envie qualquer arquivo de planilha na barra lateral para começar."
  )
  st.stop()

try:
  with st.spinner("Lendo e estruturando os dados..."):
    df = load_data(uploaded_file)
except Exception as e:
  st.error(f"Erro ao ler o arquivo: {e}")
  st.stop()

colunas = df.columns.tolist()

# --- MAPEAMENTO DINÂMICO INTELIGENTE ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configuração de Colunas")


def encontrar_coluna(lista_colunas, palavras_chave):
  for col in lista_colunas:
    for palavra in palavras_chave:
      if palavra.lower() in str(col).lower():
        return col
  return lista_colunas[0] if lista_colunas else None


# 1. Coluna de Fila / Produto
default_cat = encontrar_coluna(
    colunas, ["product", "fila", "categoria", "tipo", "status_name", "campaign"]
)
col_categoria = st.sidebar.selectbox(
    "Coluna de Categoria / Fila",
    colunas,
    index=colunas.index(default_cat) if default_cat in colunas else 0,
)

# 2. Coluna de Operador / Responsável / Backoffice
default_op = encontrar_coluna(
    colunas,
    [
        "backoffice",
        "operador",
        "user",
        "registry",
        "responsavel",
        "agent",
        "nome",
    ],
)
col_operador = st.sidebar.selectbox(
    "Coluna de Operador / Responsável",
    colunas,
    index=colunas.index(default_op) if default_op in colunas else 0,
)

# 3. Coluna de Motivo / Status Descritivo
default_desc = encontrar_coluna(
    colunas, ["description", "motivo", "status", "erro", "detalhe", "obs"]
)
col_descricao = st.sidebar.selectbox(
    "Coluna de Motivo / Status",
    colunas,
    index=colunas.index(default_desc) if default_desc in colunas else 0,
)

# 4. Coluna de Data
default_data = encontrar_coluna(
    colunas, ["date", "data", "entry", "created", "at"]
)
col_data = st.sidebar.selectbox(
    "Coluna de Data (Opcional)",
    ["Nenhuma"] + colunas,
    index=(
        colunas.index(default_data) + 1
        if default_data in colunas
        else 0
    ),
)

if col_data != "Nenhuma" and col_data in df.columns:
  df[col_data] = pd.to_datetime(df[col_data], errors="coerce")


# --- CLASSIFICAÇÃO AUTOMÁTICA POR SQUAD ---
def classificar_squad(valor):
  v = str(valor).lower()
  if "aquisi" in v:
    return "Aquisição"
  elif "rentabiliza" in v:
    return "Rentabilização"
  else:
    return "Retenção"


if col_categoria in df.columns:
  df["_squad_geral"] = df[col_categoria].apply(classificar_squad)
else:
  df["_squad_geral"] = "Retenção"


# --- CLASSIFICAÇÃO ROBÔ vs HUMANO ---
def classificar_origem(valor):
  v = str(valor).strip()
  v_lower = v.lower()

  if v_lower == "" or v_lower == "nan" or v_lower == "none":
    return "Robô"

  termos_robo = [
      "ativo",
      "rpa",
      "plataforma",
      "port",
      "refid",
      "upsell",
      "controle",
  ]
  if any(termo in v_lower for termo in termos_robo):
    return "Robô"

  if "@" in v or " " in v:
    return "Humano"

  return "Humano"


if col_operador in df.columns:
  df["_tipo_tratamento"] = df[col_operador].apply(classificar_origem)
else:
  df["_tipo_tratamento"] = "Robô"


# --- FILTROS NA BARRA LATERAL ---
st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtros Dinâmicos")

squads_disponiveis = sorted(df["_squad_geral"].unique().tolist())
sel_squads = st.sidebar.multiselect(
    "Filtrar por Squad", squads_disponiveis, default=[]
)
if sel_squads:
  df = df[df["_squad_geral"].isin(sel_squads)]

if col_categoria in df.columns:
  filas_disponiveis = sorted(df[col_categoria].dropna().unique().tolist())
  sel_filas = st.sidebar.multiselect(
      "Filtrar por Fila / Produto", filas_disponiveis, default=[]
  )
  if sel_filas:
    df = df[df[col_categoria].isin(sel_filas)]

if col_operador in df.columns:
  op_opts = sorted(df[col_operador].dropna().unique().tolist())
  sel_op = st.sidebar.multiselect(f"Filtrar por {col_operador}", op_opts)
  if sel_op:
    df = df[df[col_operador].isin(sel_op)]

if col_descricao in df.columns:
  desc_opts = sorted(df[col_descricao].dropna().unique().tolist())
  sel_desc = st.sidebar.multiselect(f"Filtrar por {col_descricao}", desc_opts)
  if sel_desc:
    df = df[df[col_descricao].isin(sel_desc)]

if len(df) == 0:
  st.warning("⚠️ Nenhum registro encontrado com os filtros selecionados.")
  st.stop()


# --- MÉTRICAS (KPIs) GERAIS ---
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

total_registros = len(df)
col1.metric("Total de Tratados", f"{total_registros:,}".replace(",", "."))

df_sucesso = df.copy()
if col_descricao in df.columns:
  mask_sucesso = (
      df_sucesso[col_descricao]
      .astype(str)
      .str.contains(
          "sucesso|cadastrada|concluid|efetivad", case=False, na=False
      )
  )
  df_sucesso = df_sucesso[mask_sucesso]

col2.metric(
    "Vendas com Sucesso", f"{len(df_sucesso):,}".replace(",", ".")
)

total_robo = len(df[df["_tipo_tratamento"] == "Robô"])
total_humano = len(df[df["_tipo_tratamento"] == "Humano"])

col3.metric("Tratados por Robô", f"{total_robo:,}".replace(",", "."))
col4.metric("Tratados por Humano", f"{total_humano:,}".replace(",", "."))

st.markdown("---")


# --- FUNÇÃO DE GERAÇÃO DE PDF (10% ROBUSTA E COMPATÍVEL) ---
def gerar_pdf(data_frame):
  pdf = FPDF()
  pdf.add_page()
  pdf.set_auto_page_break(auto=True, margin=15)

  # Cabeçalho
  pdf.set_font("helvetica", "B", 16)
  pdf.cell(0, 10, "Relatorio Executivo - Squads & Automacao", ln=True, align="C")
  pdf.set_font("helvetica", "", 10)
  pdf.cell(
      0,
      6,
      f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
      ln=True,
      align="C",
  )
  pdf.ln(10)

  # 1. GERAL POR SQUAD (Robô x Humano com %)
  pdf.set_font("helvetica", "B", 12)
  pdf.cell(0, 8, "1. Visao Geral por Squad (Robo x Humano)", ln=True)
  pdf.set_font("helvetica", "", 10)

  if "_squad_geral" in data_frame.columns:
    resumo_squad = (
        data_frame.groupby("_squad_geral")
        .agg(
            Total=("_squad_geral", "count"),
            Robo=("_tipo_tratamento", lambda x: (x == "Robô").sum()),
            Humano=("_tipo_tratamento", lambda x: (x == "Humano").sum()),
        )
        .reset_index()
    )

    for _, row in resumo_squad.iterrows():
      tot = row["Total"]
      p_robo = (row["Robo"] / tot * 100) if tot > 0 else 0
      p_humano = (row["Humano"] / tot * 100) if tot > 0 else 0

      pdf.set_font("helvetica", "B", 10)
      pdf.cell(
          0,
          6,
          f"Squad: {row['_squad_geral']} (Total: {tot:,} tratados)".replace(
              ",", "."
          ),
          ln=True,
      )
      pdf.set_font("helvetica", "", 10)
      pdf.cell(10, 6, "")
      pdf.cell(
          0,
          6,
          f"- Robo: {row['Robo']:,} ({p_robo:.1f}%)  |  Humano:"
          f" {row['Humano']:,} ({p_humano:.1f}%)".replace(",", "."),
          ln=True,
      )
  pdf.ln(5)

  # 2. POR FILA (Discriminar cada operador e RPA)
  pdf.set_font("helvetica", "B", 12)
  pdf.cell(0, 8, "2. Detalhamento por Fila (Operadores e RPA)", ln=True)
  pdf.set_font("helvetica", "", 10)

  if (
      col_categoria in data_frame.columns
      and col_operador in data_frame.columns
  ):
    filas = sorted(data_frame[col_categoria].dropna().unique())
    for fila in filas:
      pdf.set_font("helvetica", "B", 10)
      pdf.cell(0, 6, f"Fila / Produto: {fila}", ln=True)

      df_fila = data_frame[data_frame[col_categoria] == fila]
      operadores_fila = (
          df_fila.groupby([col_operador, "_tipo_tratamento"])
          .size()
          .reset_index(name="Qtd")
      )

      pdf.set_font("helvetica", "", 9)
      for _, op_row in operadores_fila.iterrows():
        tipo_lbl = f"[{op_row['_tipo_tratamento']}]"
        pdf.cell(10, 5, "")
        pdf.cell(
            0,
            5,
            f"{tipo_lbl} {op_row[col_operador]}: {op_row['Qtd']:,} tratados".replace(
                ",", "."
            ),
            ln=True,
        )
      pdf.ln(3)

  # Saída robusta compatível com qualquer versão do FPDF
  output_res = pdf.output()
  if isinstance(output_res, str):
    return output_res.encode("latin1")
  return bytes(output_res)


# --- BOTÃO DIRETO PARA EXPORTAR PDF NA BARRA LATERAL ---
st.sidebar.markdown("---")
st.sidebar.header("📥 Exportar Relatório")

pdf_data = gerar_pdf(df)

st.sidebar.download_button(
    label="📄 Baixar Relatório em PDF",
    data=pdf_data,
    file_name=f"Relatorio_Squads_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
    mime="application/pdf",
)


# --- RESUMO POR SQUAD ---
st.subheader("🏢 Resumo Consolidado por Squad (Tratados, Robô e Humano)")
if "_squad_geral" in df.columns:
  resumo_squad = (
      df.groupby("_squad_geral")
      .agg(
          Total_Tratados=("_squad_geral", "count"),
          Tratados_Robo=(
              "_tipo_tratamento",
              lambda x: (x == "Robô").sum(),
          ),
          Tratados_Humano=(
              "_tipo_tratamento",
              lambda x: (x == "Humano").sum(),
          ),
      )
      .reset_index()
  )

  resumo_squad["% Robô"] = (
      resumo_squad["Tratados_Robo"] / resumo_squad["Total_Tratados"] * 100
  ).round(1).astype(str) + "%"
  resumo_squad["% Humano"] = (
      resumo_squad["Tratados_Humano"] / resumo_squad["Total_Tratados"] * 100
  ).round(1).astype(str) + "%"

  resumo_squad.columns = [
      "Squad",
      "Total Tratados",
      "Tratados por Robô",
      "Tratados por Humano",
      "% Robô",
      "% Humano",
  ]
  st.dataframe(resumo_squad, use_container_width=True, hide_index=True)

st.markdown("---")


# --- RANKING ALFABÉTICO CONSOLIDADO POR OPERADOR ---
st.subheader("🔤 Ranking Alfabético Consolidado (Por Operador)")

if not df.empty and col_operador in df.columns:
  df_tratados = (
      df.groupby(col_operador).size().reset_index(name="Qtd Tratados")
  )

  if not df_sucesso.empty and col_operador in df_sucesso.columns:
    df_vendas = (
        df_sucesso.groupby(col_operador)
        .size()
        .reset_index(name="Qtd Vendas Sucesso")
    )
    ranking_final = pd.merge(
        df_tratados, df_vendas, on=col_operador, how="left"
    ).fillna(0)
    ranking_final["Qtd Vendas Sucesso"] = ranking_final[
        "Qtd Vendas Sucesso"
    ].astype(int)
  else:
    ranking_final = df_tratados.copy()
    ranking_final["Qtd Vendas Sucesso"] = 0

  ranking_final = ranking_final.sort_values(by=col_operador, ascending=True)
  ranking_final.columns = ["Operador", "Qtd Tratados", "Qtd Vendas Sucesso"]

  st.dataframe(ranking_final, use_container_width=True, hide_index=True)

st.markdown("---")


# --- GRÁFICOS AUTOMÁTICOS ---
col_g1, col_g2 = st.columns(2)

with col_g1:
  if col_descricao in df.columns:
    st.subheader(f"📊 Ocorrências por {col_descricao}")
    counts = df[col_descricao].value_counts().reset_index()
    counts.columns = ["Item", "Quantidade"]
    fig = px.bar(
        counts.head(15),
        x="Quantidade",
        y="Item",
        orientation="h",
        template="plotly_dark",
    )
    st.plotly_chart(fig, use_container_width=True)

with col_g2:
  st.subheader("🤖 Distribuição Robô x Humano")
  tipo_counts = df["_tipo_tratamento"].value_counts().reset_index()
  tipo_counts.columns = ["Origem", "Quantidade"]
  fig_pie = px.pie(
      tipo_counts,
      names="Origem",
      values="Quantidade",
      hole=0.4,
      template="plotly_dark",
  )
  st.plotly_chart(fig_pie, use_container_width=True)

# --- TABELA GERAL ---
st.subheader("📋 Dados Detalhados")
st.dataframe(df.head(100), use_container_width=True)