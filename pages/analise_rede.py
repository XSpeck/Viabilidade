"""
Página de Análise da Rede FTTH
Salve como: pages/analise_rede.py
"""

import streamlit as st
from login_system import require_authentication
import pandas as pd
from xml.etree import ElementTree as ET
import io
from openlocationcode import openlocationcode as olc
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Análise da Rede - Validador de Projetos",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação
if not require_authentication():
    st.stop()

# Verificar se é Admin (nível 1)
if st.session_state.user_nivel != 1:
    st.error("🚫 Acesso Negado! Esta página é restrita a administradores.")
    st.info("👈 Use o menu lateral para navegar.")
    st.stop()

# ======================
# Funções Auxiliares
# ======================

def coords_to_pluscode(lat, lon):
    """Converte coordenadas para Plus Code"""
    try:
        return olc.encode(lat, lon)
    except Exception as e:
        logger.error(f"Erro ao converter coordenadas: {e}")
        return f"{lat:.6f},{lon:.6f}"

def processar_kml(uploaded_file):
    """Processa arquivo KML e retorna dicionário {nome_cto: plus_code}"""
    if uploaded_file is None:
        return {}
    
    try:
        content = uploaded_file.read()
        root = ET.fromstring(content)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        ctos_localizacao = {}
        
        for placemark in root.findall('.//kml:Placemark', ns):
            nome_elem = placemark.find('kml:name', ns)
            coords_elem = placemark.find('.//kml:coordinates', ns)
            
            if nome_elem is not None and coords_elem is not None:
                nome_cto = nome_elem.text.strip()
                coords_text = coords_elem.text.strip()
                
                coords = coords_text.split(',')
                if len(coords) >= 2:
                    try:
                        lon = float(coords[0])
                        lat = float(coords[1])
                        pluscode = coords_to_pluscode(lat, lon)
                        ctos_localizacao[nome_cto] = pluscode
                    except ValueError:
                        continue
        
        return ctos_localizacao
        
    except Exception as e:
        st.error(f"❌ Erro ao processar KML: {e}")
        return {}

@st.cache_data
def processar_dados(relatorio_csv, logins_csv, kml_file, ctos_csv):
    """Processa todos os dados e retorna DataFrame filtrado"""
    
    # Carregar relatório
    df = pd.read_csv(io.StringIO(relatorio_csv.decode('utf-8')), sep=";")
    df_relatorio_original = df.copy()
    
    df_logins_completo = None
    df_ctos = None
    
    # Carregar logins se disponível
    if logins_csv is not None:
        df_logins_completo = pd.read_csv(io.StringIO(logins_csv.decode('utf-8')), sep=";", low_memory=False)
        
        # Identificar a coluna de status
        col_status = None
        for col in df_logins_completo.columns:
            if any(palavra in col.lower().replace('"', '') for palavra in ["ativo", "status"]):
                col_status = col
                break
        
        if col_status:
            ativos = df_logins_completo[df_logins_completo[col_status].astype(str).str.lower().str.strip().isin(
                ["sim", "ativo", "active", "yes", "true", "1", "on"]
            )]
        else:
            st.warning("⚠️ Coluna de status não encontrada, usando todos os registros")
            ativos = df_logins_completo
        
        # Fazer merge se possível
        col_login = None
        for col in df.columns:
            if col.lower().replace('"', '') == "login":
                col_login = col
                break
        
        col_login_arquivo = None
        for col in df_logins_completo.columns:
            if col.lower().replace('"', '') == "login":
                col_login_arquivo = col
                break
        
        if col_login and col_login_arquivo:
            df = df.merge(ativos[[col_login_arquivo, col_status]], 
                         left_on=col_login, right_on=col_login_arquivo, how="inner")
    
    # Converter sinais para numérico
    df["Sinal RX"] = pd.to_numeric(df["Sinal RX"], errors="coerce")
    df["Sinal TX"] = pd.to_numeric(df["Sinal TX"], errors="coerce")
    
    # Remover registros inválidos
    registros_antes_limpeza = len(df)
    df = df.dropna(subset=["Sinal RX", "Sinal TX"])
    if registros_antes_limpeza != len(df):
        st.info(f"🧹 Limpeza: {registros_antes_limpeza - len(df)} registros removidos (sinais inválidos)")
    
    # Processar KML
    ctos_localizacao = processar_kml(kml_file) if kml_file else {}

    # Carregar relatório de CTOs se disponível
    if ctos_csv is not None:
        df_ctos = pd.read_csv(io.StringIO(ctos_csv.decode('utf-8')), sep=";")
    
    return df, ctos_localizacao, df_logins_completo, df_relatorio_original, df_ctos

def criar_tabela_onus(df_onus, plus_codes):
    """Cria tabela formatada para exibição"""
    if len(df_onus) == 0:
        return pd.DataFrame()
    
    tabela = df_onus.copy()
    
    if plus_codes:
        tabela["Plus_Code"] = tabela["Caixa FTTH"].map(plus_codes).fillna("N/A")
    else:
        tabela["Plus_Code"] = "N/A"
    
    colunas_exibir = []
    
    if "ONU ID" in tabela.columns:
        colunas_exibir.append("ONU ID")
    elif "ID" in tabela.columns:
        colunas_exibir.append("ID")
    
    if "Login" in tabela.columns:
        colunas_exibir.append("Login")
    elif "Nome" in tabela.columns:
        colunas_exibir.append("Nome")
    
    colunas_exibir.extend(["Caixa FTTH", "Sinal RX", "Sinal TX"])
    
    if "Última atualização" in tabela.columns:
        colunas_exibir.append("Última atualização")
    elif "Data" in tabela.columns:
        colunas_exibir.append("Data")
    
    colunas_exibir.append("Plus_Code")
    
    colunas_existentes = [col for col in colunas_exibir if col in tabela.columns]
    
    return tabela[colunas_existentes]

# ======================
# Header
# ======================
st.title("🔧 Análise da Rede FTTH")
st.markdown("Sistema de análise de ONUs com problemas - Apenas clientes ativos")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ======================
# Sidebar - Upload de Arquivos
# ======================
with st.sidebar:
    st.header("📁 Upload de Arquivos")
    
    relatorio_file = st.file_uploader(
        "Relatório de Sinais (CSV)",
        type=['csv'],
        help="Arquivo CSV com dados de sinais das ONUs"
    )
    
    logins_file = st.file_uploader(
        "Status dos Logins (CSV)",
        type=['csv'],
        help="Arquivo CSV com status dos clientes (ativo/inativo)"
    )
    
    kml_file = st.file_uploader(
        "Localização das CTOs (KML) - Opcional",
        type=['kml'],
        help="Arquivo KML com coordenadas das CTOs"
    )

    ctos_file = st.file_uploader(
        "Relatório de CTOs (CSV) - Opcional",
        type=['csv'],
        help="Arquivo CSV com cadastro de CTOs por porta/OLT"
    )

# ======================
# Verificação e Processamento
# ======================
if relatorio_file is None:
    st.warning("⚠️ Por favor, faça o upload do arquivo de relatório para começar.")
    st.info("""
    **Arquivos necessários:**
    - **relatorio.csv**: Dados de sinais das ONUs (obrigatório)
    - **logins.csv**: Status dos clientes (recomendado)
    - **ctos_localizacao.kml**: Coordenadas das CTOs (opcional)
    """)
    st.stop()

# Processar dados
try:
    with st.spinner("Processando dados..."):
        df, ctos_localizacao, df_logins_completo, df_relatorio_original, df_ctos = processar_dados(
            relatorio_file.read(), 
            logins_file.read() if logins_file else None,
            kml_file,
            ctos_file.read() if ctos_file else None
        )
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total de Registros", len(df))
    
    with col2:
        clientes_ativos = len(df) if logins_file else "N/A"
        st.metric("✅ Clientes Ativos", clientes_ativos)
    
    with col3:
        ctos_total = df["Caixa FTTH"].nunique()
        st.metric("🏢 CTOs Analisadas", ctos_total)
    
    with col4:
        ctos_com_localizacao = len(ctos_localizacao)
        st.metric("📍 CTOs Localizadas", ctos_com_localizacao)
    
    st.markdown("---")
    
    # ======================
    # ABAS DE ANÁLISE
    # ======================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔧 ONUs com Defeito (TX > RX)", 
        "📶 ONUs com Sinal Fraco (< -26 dBm)", 
        "👥 Clientes Sem ONU", 
        "🏢 Clientes N1 (Rede Neutra)", 
        "📊 CTOs Saturadas",
        "🔌 CTOs por Porta/OLT"
    ])
    
    # ABA 1: ONUs com defeito
    with tab1:
        st.header("🚨 ONUs com Possível Defeito")
        st.markdown("**Critério:** TX > RX (anômalo)")
        
        onus_defeito = df[df["Sinal TX"] > df["Sinal RX"]].copy()
        
        if len(onus_defeito) > 0:
            onus_defeito["Diferença TX-RX"] = onus_defeito["Sinal TX"] - onus_defeito["Sinal RX"]
            onus_defeito = onus_defeito.sort_values("Diferença TX-RX", ascending=False)
            
            # Métricas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔧 ONUs com Defeito", len(onus_defeito), 
                         delta=f"{len(onus_defeito)/len(df)*100:.1f}% do total")
            with col2:
                pior_diferenca = onus_defeito["Diferença TX-RX"].max()
                st.metric("📈 Pior Diferença", f"{pior_diferenca:+.1f} dBm")
            with col3:
                ctos_afetadas = onus_defeito["Caixa FTTH"].nunique()
                st.metric("🏢 CTOs Afetadas", ctos_afetadas)
            
            # Tabela
            st.subheader("📋 Lista Detalhada")
            tabela_defeitos = criar_tabela_onus(onus_defeito, ctos_localizacao)
            
            if "Diferença TX-RX" in onus_defeito.columns:
                tabela_defeitos["Diferença"] = onus_defeito["Diferença TX-RX"].round(1)
            
            st.dataframe(tabela_defeitos, width='stretch', height=400)
            
            # Download
            csv_defeitos = tabela_defeitos.to_csv(sep=';', index=False)
            st.download_button(
                label="💾 Baixar Lista de ONUs com Defeito",
                data=csv_defeitos,
                file_name="onus_com_defeito.csv",
                mime="text/csv"
            )
            
            # Resumo por CTO
            st.subheader("📊 Resumo por CTO")
            
            resumo_defeitos = []
            
            for cto in onus_defeito["Caixa FTTH"].unique():
                dados_cto = onus_defeito[onus_defeito["Caixa FTTH"] == cto]
                
                qtd_onus = len(dados_cto)
                diferenca_media = dados_cto["Diferença TX-RX"].mean()
                pior_caso = dados_cto["Diferença TX-RX"].max()
                melhor_rx = dados_cto["Sinal RX"].max()
                
                transmissor = "N/A"
                for col in dados_cto.columns:
                    if any(palavra in col.lower() for palavra in ["transmissor", "olt", "equipamento", "central"]):
                        valores = dados_cto[col].value_counts()
                        if len(valores) > 0:
                            transmissor = str(valores.index[0])
                        break
                
                porta = "0"
                if "PON ID" in dados_cto.columns:
                    valores = dados_cto["PON ID"].value_counts()
                    if len(valores) > 0:
                        porta = str(valores.index[0])
                
                pon_id = f"{porta}"
                plus_code = ctos_localizacao.get(cto, "N/A") if ctos_localizacao else "N/A"
                
                resumo_defeitos.append({
                    "Caixa FTTH": cto,
                    "ONUs com Defeito": qtd_onus,
                    "Diferença Média": round(diferenca_media, 2),
                    "Pior Caso": round(pior_caso, 2),
                    "Melhor RX": round(melhor_rx, 1),
                    "Transmissor": transmissor,
                    "PON ID": pon_id,
                    "Plus Code": plus_code
                })
            
            resumo_df = pd.DataFrame(resumo_defeitos)
            resumo_df = resumo_df.sort_values("ONUs com Defeito", ascending=False)
            
            st.dataframe(resumo_df, width='stretch')
            
        else:
            st.success("✅ Nenhuma ONU com defeito detectada!")
            st.balloons()
    
    # ABA 2: ONUs com sinal fraco
    with tab2:
        st.header("📶 ONUs com Sinal Fraco")
        st.markdown("**Critério:** RX < -26 dBm (sinal fraco)")
        
        onus_sinal_fraco = df[df["Sinal RX"] < -26].copy()
        
        if len(onus_sinal_fraco) > 0:
            onus_sinal_fraco = onus_sinal_fraco.sort_values("Sinal RX", ascending=True)
            
            # Métricas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📶 ONUs com Sinal Fraco", len(onus_sinal_fraco),
                         delta=f"{len(onus_sinal_fraco)/len(df)*100:.1f}% do total")
            with col2:
                pior_rx = onus_sinal_fraco["Sinal RX"].min()
                st.metric("📉 Pior RX", f"{pior_rx:.1f} dBm")
            with col3:
                ctos_afetadas = onus_sinal_fraco["Caixa FTTH"].nunique()
                st.metric("🏢 CTOs Afetadas", ctos_afetadas)
            
            # Tabela
            st.subheader("📋 Lista Detalhada")
            tabela_sinal_fraco = criar_tabela_onus(onus_sinal_fraco, ctos_localizacao)
            
            st.dataframe(tabela_sinal_fraco, width='stretch', height=400)
            
            # Download
            csv_sinal_fraco = tabela_sinal_fraco.to_csv(sep=';', index=False)
            st.download_button(
                label="💾 Baixar Lista de ONUs com Sinal Fraco",
                data=csv_sinal_fraco,
                file_name="onus_sinal_fraco.csv",
                mime="text/csv"
            )
            
            # Resumo por CTO (similar ao anterior)
            st.subheader("📊 Resumo por CTO")
            
            resumo_sinal = []
            
            for cto in onus_sinal_fraco["Caixa FTTH"].unique():
                dados_cto = onus_sinal_fraco[onus_sinal_fraco["Caixa FTTH"] == cto]
                
                qtd_onus = len(dados_cto)
                rx_medio = dados_cto["Sinal RX"].mean()
                pior_rx = dados_cto["Sinal RX"].min()
                melhor_rx = dados_cto["Sinal RX"].max()
                
                transmissor = "N/A"
                for col in dados_cto.columns:
                    if any(palavra in col.lower() for palavra in ["transmissor", "olt", "equipamento", "central"]):
                        valores = dados_cto[col].value_counts()
                        if len(valores) > 0:
                            transmissor = str(valores.index[0])
                        break
                
                porta = "0"
                if "PON ID" in dados_cto.columns:
                    valores = dados_cto["PON ID"].value_counts()
                    if len(valores) > 0:
                        porta = str(valores.index[0])
                
                pon_id = f"{porta}"
                plus_code = ctos_localizacao.get(cto, "N/A") if ctos_localizacao else "N/A"
                
                resumo_sinal.append({
                    "Caixa FTTH": cto,
                    "ONUs com Sinal Fraco": qtd_onus,
                    "RX Médio": round(rx_medio, 1),
                    "Pior RX": round(pior_rx, 1),
                    "Melhor RX": round(melhor_rx, 1),
                    "Transmissor": transmissor,
                    "PON ID": pon_id,
                    "Plus Code": plus_code
                })
            
            resumo_df = pd.DataFrame(resumo_sinal)
            resumo_df = resumo_df.sort_values("ONUs com Sinal Fraco", ascending=False)
            
            st.dataframe(resumo_df, width='stretch')
            
        else:
            st.success("✅ Nenhuma ONU com sinal fraco detectada!")
            st.balloons()
    
    # ABA 3, 4 e 5: Continue o padrão...
    # (Devido ao limite de caracteres, vou mostrar apenas as abas principais)
    # O código completo continua igual ao seu app original, apenas adaptando:
    # - As mensagens de erro/sucesso
    # - O estilo dos st.metric
    # - Mantendo a mesma lógica de processamento
    
    # ABA 3: Clientes sem ONU
    with tab3:
        st.header("👥 Clientes Ativos sem ONU Cadastrada")
        st.markdown("**Clientes que estão ativos no sistema mas não aparecem no relatório de ONUs**")
        
        if df_logins_completo is not None:
            # Identificar coluna de status
            col_status_completo = None
            for col in df_logins_completo.columns:
                if any(palavra in col.lower().replace('"', '') for palavra in ["ativo", "status"]):
                    col_status_completo = col
                    break
            
            # Filtrar apenas clientes ativos
            if col_status_completo:
                clientes_ativos_todos = df_logins_completo[
                    df_logins_completo[col_status_completo].astype(str).str.lower().str.strip() == "sim"
                ].copy()
            else:
                clientes_ativos_todos = df_logins_completo.copy()
            
            # Identificar coluna de login
            col_login_completo = None
            for col in df_logins_completo.columns:
                if col.lower().replace('"', '') == "login":
                    col_login_completo = col
                    break
            
            if col_login_completo:
                # Logins que estão no arquivo logins mas não no relatório
                logins_no_relatorio = set()
                if "Login" in df.columns:
                    logins_no_relatorio = set(df["Login"].unique())
                
                logins_todos_ativos = set(clientes_ativos_todos[col_login_completo].unique())
                clientes_sem_onu = logins_todos_ativos - logins_no_relatorio
                
                # Filtrar o dataframe para mostrar apenas clientes sem ONU
                df_clientes_sem_onu = clientes_ativos_todos[
                    clientes_ativos_todos[col_login_completo].isin(clientes_sem_onu)
                ].copy()
                
                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Clientes Ativos sem ONU", len(df_clientes_sem_onu))
                with col2:
                    # Contar quantos são UTP
                    clientes_utp = 0
                    if "Transmissor" in df_clientes_sem_onu.columns:
                        clientes_utp = len(df_clientes_sem_onu[
                            df_clientes_sem_onu["Transmissor"].astype(str).str.contains("Clientes_UTP", case=False, na=False)
                        ])
                    st.metric("📡 Clientes UTP", clientes_utp)
                with col3:
                    outros_tipos = len(df_clientes_sem_onu) - clientes_utp
                    st.metric("🔗 Outros Tipos", outros_tipos)
                
                if len(df_clientes_sem_onu) > 0:
                    # Filtros
                    st.subheader("🔍 Filtros")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Filtro por tipo de transmissor
                        tipos_transmissor = ["Todos"] + list(df_clientes_sem_onu["Transmissor"].value_counts().index)
                        filtro_transmissor = st.selectbox("Filtrar por Transmissor:", tipos_transmissor, key="transmissor_sem_onu")
                    
                    with col2:
                        # Filtro por complemento
                        complementos = ["Todos"] + [comp for comp in df_clientes_sem_onu["Complemento"].value_counts().index if pd.notna(comp)]
                        filtro_complemento = st.selectbox("Filtrar por Complemento:", complementos, key="complemento_sem_onu")
                    
                    # Aplicar filtros
                    df_filtrado = df_clientes_sem_onu.copy()
                    
                    if filtro_transmissor != "Todos":
                        df_filtrado = df_filtrado[df_filtrado["Transmissor"] == filtro_transmissor]
                    
                    if filtro_complemento != "Todos":
                        df_filtrado = df_filtrado[df_filtrado["Complemento"] == filtro_complemento]
                    
                    # Preparar tabela para exibição
                    colunas_exibir = [col_login_completo, "Cliente", "Transmissor", "Complemento", "Plano", "Endereco", "Bairro"]
                    colunas_existentes = [col for col in colunas_exibir if col in df_filtrado.columns]
                    
                    tabela_clientes = df_filtrado[colunas_existentes].copy()
                    
                    # Renomear colunas para melhor visualização
                    if col_login_completo in tabela_clientes.columns:
                        tabela_clientes = tabela_clientes.rename(columns={col_login_completo: "Login"})
                    
                    st.subheader(f"📋 Lista de Clientes ({len(df_filtrado)} registros)")
                    st.dataframe(
                        tabela_clientes,
                        width='stretch',
                        height=400
                    )
                    
                    # Botão de download
                    csv_clientes_sem_onu = tabela_clientes.to_csv(sep=';', index=False)
                    st.download_button(
                        label="💾 Baixar Lista de Clientes sem ONU",
                        data=csv_clientes_sem_onu,
                        file_name="clientes_sem_onu.csv",
                        mime="text/csv"
                    )
                    
                    # Resumo por transmissor
                    st.subheader("📊 Resumo por Transmissor")
                    resumo_transmissor = df_clientes_sem_onu.groupby("Transmissor").agg({
                        col_login_completo: "count",
                        "Bairro": "nunique"
                    }).reset_index()
                    
                    resumo_transmissor.columns = ["Transmissor", "Qtd Clientes", "Bairros Atendidos"]
                    resumo_transmissor = resumo_transmissor.sort_values("Qtd Clientes", ascending=False)
                    
                    st.dataframe(resumo_transmissor, width='stretch')
                    
                else:
                    st.success("✅ Todos os clientes ativos possuem ONU cadastrada!")
                    st.balloons()
            else:
                st.error("❌ Coluna de Login não encontrada no arquivo logins.csv")
        else:
            st.warning("⚠️ Arquivo logins.csv não foi carregado. Esta análise requer o arquivo de logins.")
    
    # ABA 4: Clientes N1 (Rede Neutra)
    with tab4:
        st.header("🏢 Clientes N1 CONEXÕES DE INTERNET LTDA (Rede Neutra)")
        st.markdown("**Análise de clientes N1 CONEXÕES DE INTERNET LTDA - Operadora de Rede Neutra**")
        
        if df_logins_completo is not None:
            # Filtrar clientes N1 na coluna Cliente
            clientes_n1 = df_logins_completo[
                df_logins_completo["Cliente"].astype(str).str.contains(
                    "N1 CONEXOES DE INTERNET LTDA", case=False, na=False
                )
            ].copy()
            
            # Identificar coluna de status para separar ativos/inativos
            col_status_n1 = None
            for col in df_logins_completo.columns:
                if any(palavra in col.lower().replace('"', '') for palavra in ["ativo", "status"]):
                    col_status_n1 = col
                    break
            
            clientes_n1_ativos = pd.DataFrame()
            clientes_n1_inativos = pd.DataFrame()
            
            if col_status_n1:
                clientes_n1_ativos = clientes_n1[
                    clientes_n1[col_status_n1].astype(str).str.lower().str.strip() == "sim"
                ].copy()
                
                clientes_n1_inativos = clientes_n1[
                    clientes_n1[col_status_n1].astype(str).str.lower().str.strip() != "sim"
                ].copy()
            else:
                clientes_n1_ativos = clientes_n1.copy()
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🏢 Total N1", len(clientes_n1))
            with col2:
                st.metric("✅ N1 Ativos", len(clientes_n1_ativos))
            with col3:
                st.metric("❌ N1 Inativos", len(clientes_n1_inativos))
            with col4:
                # Verificar quantos N1 ativos têm ONUs
                n1_com_onu = 0
                col_login_n1 = None
                for col in df_logins_completo.columns:
                    if col.lower().replace('"', '') == "login":
                        col_login_n1 = col
                        break
                
                if col_login_n1 and "Login" in df.columns:
                    logins_n1_ativos = set(clientes_n1_ativos[col_login_n1].unique())
                    logins_com_onu = set(df["Login"].unique())
                    n1_com_onu = len(logins_n1_ativos.intersection(logins_com_onu))
                
                st.metric("📶 N1 com ONU", n1_com_onu)
            
            if len(clientes_n1) > 0:
                st.info("ℹ️ **Rede Neutra**: N1 CONEXÕES é uma operadora de rede neutra que utiliza a infraestrutura para atender outros provedores.")
                
                # Filtros
                st.subheader("🔍 Filtros")
                col1, col2 = st.columns(2)
                
                with col1:
                    status_filtro = st.selectbox(
                        "Status:", 
                        ["Todos", "Apenas Ativos", "Apenas Inativos"],
                        key="status_filtro_n1"
                    )
                
                with col2:
                    # Filtro por transmissor
                    tipos_transmissor_n1 = ["Todos"] + list(clientes_n1["Transmissor"].value_counts().index)
                    filtro_transmissor_n1 = st.selectbox("Transmissor:", tipos_transmissor_n1, key="transmissor_n1")
                
                # Aplicar filtros
                if status_filtro == "Apenas Ativos":
                    df_n1_filtrado = clientes_n1_ativos.copy()
                elif status_filtro == "Apenas Inativos":
                    df_n1_filtrado = clientes_n1_inativos.copy()
                else:
                    df_n1_filtrado = clientes_n1.copy()
                
                if filtro_transmissor_n1 != "Todos":
                    df_n1_filtrado = df_n1_filtrado[df_n1_filtrado["Transmissor"] == filtro_transmissor_n1]
                
                # ---- NOVA TABELA ----
                # Juntar com informações técnicas do relatório
                tabela_n1 = df_n1_filtrado.merge(
                    df[["Login", "PON ID", "Caixa FTTH", "Sinal RX", "Última atualização", "Transmissor"]],
                    on="Login",
                    how="left",
                    suffixes=("_logins", "_relatorio")
                )

                # Ajustar transmissor:
                # 1. Se vier dos logins, usa ele
                # 2. Se não tiver, pega do relatório
                if "Transmissor_logins" in tabela_n1.columns and "Transmissor_relatorio" in tabela_n1.columns:
                    tabela_n1["Transmissor"] = tabela_n1["Transmissor_logins"].fillna(tabela_n1["Transmissor_relatorio"])
                elif "Transmissor_logins" in tabela_n1.columns:
                    tabela_n1["Transmissor"] = tabela_n1["Transmissor_logins"]
                elif "Transmissor_relatorio" in tabela_n1.columns:
                    tabela_n1["Transmissor"] = tabela_n1["Transmissor_relatorio"]
                else:
                    tabela_n1["Transmissor"] = "N/A"

                # Adicionar Plus Code
                if ctos_localizacao:
                    tabela_n1["Plus Code"] = tabela_n1["Caixa FTTH"].map(ctos_localizacao).fillna("N/A")
                else:
                    tabela_n1["Plus Code"] = "N/A"

                # Selecionar colunas na ordem desejada
                colunas_exibir_n1 = ["Login", "Transmissor", "PON ID", "Caixa FTTH", "Sinal RX", "Última atualização", "Plus Code"]
                colunas_existentes_n1 = [col for col in colunas_exibir_n1 if col in tabela_n1.columns]
                tabela_n1 = tabela_n1[colunas_existentes_n1]
                
                st.subheader(f"📋 Lista de Clientes N1 - Rede Neutra ({len(tabela_n1)} registros)")
                st.dataframe(
                    tabela_n1,
                    width='stretch',
                    height=400
                )
                
                # Botão de download
                csv_n1 = tabela_n1.to_csv(sep=';', index=False)
                st.download_button(
                    label="💾 Baixar Lista Clientes N1 (Rede Neutra)",
                    data=csv_n1,
                    file_name="clientes_n1_rede_neutra.csv",
                    mime="text/csv"
                )
                
                # Resumos
                st.subheader("📊 Análise da Rede Neutra")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Distribuição por Transmissor**")
                    resumo_transmissor_n1 = clientes_n1.groupby("Transmissor").agg({
                        "Login": "count"
                    }).reset_index()
                    resumo_transmissor_n1.columns = ["Transmissor", "Qtd Clientes N1"]
                    resumo_transmissor_n1 = resumo_transmissor_n1.sort_values("Qtd Clientes N1", ascending=False)
                    st.dataframe(resumo_transmissor_n1, width='stretch')
                
                
                
                # Análise de conectividade
                if n1_com_onu > 0:
                    st.subheader("🔗 Análise de Conectividade FTTH")
                    
                    porcentagem_ftth = (n1_com_onu / len(clientes_n1_ativos)) * 100 if len(clientes_n1_ativos) > 0 else 0
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Clientes N1 com FTTH", f"{n1_com_onu} ({porcentagem_ftth:.1f}%)")
                    with col2:
                        n1_sem_ftth = len(clientes_n1_ativos) - n1_com_onu
                        st.metric("Clientes N1 sem FTTH", f"{n1_sem_ftth} ({100-porcentagem_ftth:.1f}%)")
                    
            else:
                st.info("ℹ️ Nenhum cliente N1 CONEXÕES DE INTERNET LTDA encontrado no sistema.")
        else:
            st.warning("⚠️ Arquivo logins.csv não foi carregado. Esta análise requer o arquivo de logins.")
    
    # ABA 5: CTOs Saturadas        
    with tab5:
        st.header("📊 CTOs Saturadas")

        if df_logins_completo is not None:
            # Identificar coluna de status
            col_status_completo = None
            for col in df_logins_completo.columns:
                if any(palavra in col.lower().replace('"', '') for palavra in ["ativo", "status"]):
                    col_status_completo = col
                    break

            if col_status_completo:
                contagem_status = df_logins_completo[col_status_completo].value_counts().reset_index()
                contagem_status.columns = ["Status", "Quantidade"]
                
                # Substituir valores 'sim' e 'não'
                contagem_status["Status"] = contagem_status["Status"].astype(str).str.lower().str.strip()
                contagem_status["Status"] = contagem_status["Status"].replace({
                    "sim": "Ativos",
                    "não": "Não ativos",
                    "nao": "Não ativos"
                })

                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "✅ Logins Ativos",
                        int(contagem_status[contagem_status["Status"].astype(str).str.lower().str.contains("sim|ativo")]["Quantidade"].sum())
                    )
                with col2:
                    st.metric("👥 Total de Logins", len(df_logins_completo))

                st.subheader("📋 Distribuição por Status de Login")
                st.dataframe(contagem_status, width='stretch')

                # NOVA TABELA: CTOs com logins NÃO ATIVOS (ordem: relatório -> checagem no logins)
                st.subheader("🚫 Logins Não Ativos por CTO (do Relatório)")
                # Verificações básicas
                if "Login" in df_relatorio_original.columns and "Caixa FTTH" in df_relatorio_original.columns:
                    # Detectar coluna de Login no arquivo de logins (robusto a aspas/case)
                    col_login_logins = None
                    for col in df_logins_completo.columns:
                        if col.lower().replace('"', '') == "login":
                            col_login_logins = col
                            break

                    # Procurar especificamente a coluna 'Ativo'
                    col_ativo = None
                    for col in df_logins_completo.columns:
                        if col.strip().lower().replace('"', '') == "ativo":
                            col_ativo = col
                            break

                    if col_login_logins and col_ativo:
                        # 1) Partir do relatório (bruto, sem restrições)
                        df_rel = df_relatorio_original[["Login", "Caixa FTTH"]].dropna(subset=["Login"]).copy()
                        df_rel["login_norm"] = df_rel["Login"].astype(str).str.lower().str.strip()

                        # 2) Buscar status no logins.csv
                        df_log = df_logins_completo[[col_login_logins, col_ativo]].copy()
                        df_log["login_norm"] = df_log[col_login_logins].astype(str).str.lower().str.strip()
                        df_log["ativo_norm"] = df_log[col_ativo].astype(str).str.lower().str.strip()

                        # 3) Voltar ao relatório e pegar apenas onde o status é NÃO ativo
                        cruzado = df_rel.merge(
                            df_log[["login_norm", col_ativo, "ativo_norm"]],
                            on="login_norm",
                            how="left"
                        )

                        valores_nao_ativos = ["não", "nao", "no", "0", "false", "inativo"]
                        tabela_nao_ativos = cruzado[cruzado["ativo_norm"].isin(valores_nao_ativos)][["Caixa FTTH", "Login"]].drop_duplicates()

                        if len(tabela_nao_ativos) > 0:
                            st.dataframe(tabela_nao_ativos.sort_values(["Caixa FTTH", "Login"]).reset_index(drop=True), width='stretch', height=400)
                            csv_tabela_nao = tabela_nao_ativos.to_csv(sep=';', index=False)
                            st.download_button(
                                label="💾 Baixar Logins Não Ativos por CTO",
                                data=csv_tabela_nao,
                                file_name="ctos_logins_nao_ativos_relatorio.csv",
                                mime="text/csv"
                            )
                        else:
                            st.success("✅ Nenhum login não ativo encontrado ocupando ONU no relatório.")
                    else:
                        st.warning("⚠️ Não foi possível localizar as colunas 'Login' e/ou 'Ativo' em logins.csv.")
                else:
                    st.warning("⚠️ O relatório precisa conter as colunas 'Login' e 'Caixa FTTH'.")

        # Contagem de ONUs por CTO
        if "Caixa FTTH" in df.columns:
            st.subheader("🏢 Quantidade de ONUs por CTO")

            resumo_cto = df.groupby("Caixa FTTH").agg({
                "Login": "count",
                "Transmissor": lambda x: x.mode().iloc[0] if not x.mode().empty else "N/A",
                "PON ID": lambda x: x.mode().iloc[0] if not x.mode().empty else "N/A"
            }).reset_index()

            resumo_cto.columns = ["Caixa FTTH", "Qtd ONUs", "Transmissor", "PON ID"]
            resumo_cto = resumo_cto.sort_values("Qtd ONUs", ascending=False)

            st.dataframe(resumo_cto, width='stretch')

            # Botão de download
            csv_cto = resumo_cto.to_csv(sep=';', index=False)
            st.download_button(
                label="💾 Baixar Resumo ONUs por CTO",
                data=csv_cto,
                file_name="resumo_cto.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ Coluna 'Caixa FTTH' não encontrada no relatório.") 

    # ABA 6: CTOs por Porta/OLT
    with tab6:
        st.header("🔌 CTOs Cadastradas por Porta/OLT")
        st.markdown("**Análise de distribuição de CTOs por Interface (Porta) e Transmissor (OLT)**")
        
        if df_ctos is not None:
            # Verificar se as colunas necessárias existem
            col_transmissor = None
            col_interface = None
            col_descricao = None
            
            # Buscar coluna Transmissor(OLT)
            for col in df_ctos.columns:
                col_lower = col.lower().replace('"', '').strip()
                if "transmissor" in col_lower or "olt" in col_lower:
                    col_transmissor = col
                    break
            
            # Buscar coluna Interface
            for col in df_ctos.columns:
                col_lower = col.lower().replace('"', '').strip()
                if "interface" in col_lower or "porta" in col_lower:
                    col_interface = col
                    break
            
            # Buscar coluna Descrição
            for col in df_ctos.columns:
                col_lower = col.lower().replace('"', '').strip()
                if "descricao" in col_lower or "descrição" in col_lower or "cto" in col_lower or "nome" in col_lower:
                    col_descricao = col
                    break
            
            if col_transmissor and col_interface and col_descricao:
                # Limpar dados
                df_ctos_limpo = df_ctos[[col_transmissor, col_interface, col_descricao]].copy()
                df_ctos_limpo = df_ctos_limpo.dropna()
                
                # Normalizar descrições (remover duplicatas)
                df_ctos_limpo['descricao_norm'] = df_ctos_limpo[col_descricao].astype(str).str.strip().str.upper()
                
                # Contar CTOs únicas por OLT e Porta
                resumo_ctos_porta = df_ctos_limpo.groupby([col_transmissor, col_interface])['descricao_norm'].nunique().reset_index()
                resumo_ctos_porta.columns = ['Transmissor (OLT)', 'Interface (Porta)', 'CTOs Únicas']
                resumo_ctos_porta = resumo_ctos_porta.sort_values(['Transmissor (OLT)', 'Interface (Porta)'])
                
                # Métricas gerais
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_olts = df_ctos_limpo[col_transmissor].nunique()
                    st.metric("🏭 Total de OLTs", total_olts)
                with col2:
                    total_portas = len(resumo_ctos_porta)
                    st.metric("🔌 Total de Portas", total_portas)
                with col3:
                    total_ctos_unicas = df_ctos_limpo['descricao_norm'].nunique()
                    st.metric("📦 CTOs Únicas", total_ctos_unicas)
                with col4:
                    media_ctos = resumo_ctos_porta['CTOs Únicas'].mean()
                    st.metric("📊 Média CTOs/Porta", f"{media_ctos:.1f}")
                
                st.markdown("---")
                
                # Filtros
                st.subheader("🔍 Filtros")
                col1, col2 = st.columns(2)
                
                with col1:
                    olts_disponiveis = ["Todos"] + sorted(df_ctos_limpo[col_transmissor].unique().tolist())
                    filtro_olt = st.selectbox("Filtrar por OLT:", olts_disponiveis, key="filtro_olt_ctos")
                
                with col2:
                    # Filtro por quantidade mínima de CTOs
                    min_ctos = st.number_input(
                        "Mínimo de CTOs por porta:", 
                        min_value=0, 
                        max_value=int(resumo_ctos_porta['CTOs Únicas'].max()),
                        value=0,
                        key="min_ctos_filter"
                    )
                
                # Aplicar filtros
                df_filtrado = resumo_ctos_porta.copy()
                
                if filtro_olt != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['Transmissor (OLT)'] == filtro_olt]
                
                if min_ctos > 0:
                    df_filtrado = df_filtrado[df_filtrado['CTOs Únicas'] >= min_ctos]
                
                # Tabela principal
                st.subheader(f"📋 CTOs por Porta ({len(df_filtrado)} registros)")
                
                # Adicionar coluna de status (alerta se muitas CTOs)
                df_filtrado['Status'] = df_filtrado['CTOs Únicas'].apply(
                    lambda x: '🔴 Saturada' if x >= 8 else ('🟡 Atenção' if x >= 6 else '🟢 Normal')
                )
                
                st.dataframe(
                    df_filtrado[['Transmissor (OLT)', 'Interface (Porta)', 'CTOs Únicas', 'Status']],
                    width='stretch',
                    height=400
                )
                
                # Download
                csv_ctos_porta = df_filtrado.to_csv(sep=';', index=False)
                st.download_button(
                    label="💾 Baixar Relatório CTOs por Porta",
                    data=csv_ctos_porta,
                    file_name="ctos_por_porta_olt.csv",
                    mime="text/csv"
                )
                
                st.markdown("---")
                
                # Análises adicionais
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Resumo por OLT")
                    resumo_olt = resumo_ctos_porta.groupby('Transmissor (OLT)').agg({
                        'Interface (Porta)': 'count',
                        'CTOs Únicas': ['sum', 'mean', 'max']
                    }).reset_index()
                    resumo_olt.columns = ['OLT', 'Portas Ativas', 'Total CTOs', 'Média CTOs/Porta', 'Máx CTOs/Porta']
                    resumo_olt['Média CTOs/Porta'] = resumo_olt['Média CTOs/Porta'].round(1)
                    resumo_olt = resumo_olt.sort_values('Total CTOs', ascending=False)
                    st.dataframe(resumo_olt, width='stretch')
                
                with col2:
                    st.subheader("⚠️ Portas com Mais CTOs")
                    top_portas = resumo_ctos_porta.nlargest(10, 'CTOs Únicas')
                    st.dataframe(
                        top_portas[['Transmissor (OLT)', 'Interface (Porta)', 'CTOs Únicas']], 
                        width='stretch'
                    )
                
                # Detalhamento por porta selecionada
                st.markdown("---")
                st.subheader("🔍 Detalhamento de CTOs por Porta")
                
                col1, col2 = st.columns(2)
                with col1:
                    olt_selecionada = st.selectbox(
                        "Selecione a OLT:",
                        sorted(df_ctos_limpo[col_transmissor].unique().tolist()),
                        key="olt_detail"
                    )
                
                with col2:
                    portas_olt = sorted(
                        df_ctos_limpo[df_ctos_limpo[col_transmissor] == olt_selecionada][col_interface].unique().tolist()
                    )
                    porta_selecionada = st.selectbox(
                        "Selecione a Porta:",
                        portas_olt,
                        key="porta_detail"
                    )
                
                # Mostrar CTOs da porta selecionada
                ctos_porta = df_ctos_limpo[
                    (df_ctos_limpo[col_transmissor] == olt_selecionada) & 
                    (df_ctos_limpo[col_interface] == porta_selecionada)
                ][col_descricao].unique()
                
                st.info(f"📦 **{len(ctos_porta)} CTOs únicas** cadastradas nesta porta")
                
                # Listar CTOs
                ctos_lista = pd.DataFrame({
                    'Nº': range(1, len(ctos_porta) + 1),
                    'Descrição da CTO': sorted(ctos_porta)
                })
                
                st.dataframe(ctos_lista, width='stretch', height=300)
                
                # Download da lista específica
                csv_ctos_lista = ctos_lista.to_csv(sep=';', index=False)
                st.download_button(
                    label=f"💾 Baixar CTOs de {olt_selecionada} - {porta_selecionada}",
                    data=csv_ctos_lista,
                    file_name=f"ctos_{olt_selecionada}_{porta_selecionada}.csv",
                    mime="text/csv",
                    key="download_ctos_detail"
                )
                
            else:
                st.error("❌ Colunas necessárias não encontradas no arquivo!")
                st.info("""
                **Colunas esperadas:**
                - Transmissor(OLT) ou similar
                - Interface ou Porta
                - Descrição ou CTO ou Nome
                """)
                st.write("**Colunas encontradas:**", df_ctos.columns.tolist())
        else:
            st.warning("⚠️ Arquivo relatorio_CTOs.csv não foi carregado.")
            st.info("""
            **Para usar esta funcionalidade:**
            1. Faça upload do arquivo 'Relatório de CTOs (CSV)' na barra lateral
            2. O arquivo deve conter as colunas: Transmissor(OLT), Interface e Descrição
            """)


except Exception as e:
    st.error(f"❌ Erro ao processar os dados: {e}")
    logger.error(f"Erro no processamento: {e}")
    st.exception(e)

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔧 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
