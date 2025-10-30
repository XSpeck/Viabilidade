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
def processar_dados(relatorio_csv, logins_csv, kml_file):
    """Processa todos os dados e retorna DataFrame filtrado"""
    
    # Carregar relatório
    df = pd.read_csv(io.StringIO(relatorio_csv.decode('utf-8')), sep=";")
    df_relatorio_original = df.copy()
    
    df_logins_completo = None
    
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
    
    return df, ctos_localizacao, df_logins_completo, df_relatorio_original

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
    if st.button("🔄 Atualizar", use_container_width=True):
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
        df, ctos_localizacao, df_logins_completo, df_relatorio_original = processar_dados(
            relatorio_file.read(), 
            logins_file.read() if logins_file else None,
            kml_file
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
        "📊 CTOs Saturadas"
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
            
            st.dataframe(tabela_defeitos, use_container_width=True, height=400)
            
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
            
            st.dataframe(resumo_df, use_container_width=True)
            
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
            
            st.dataframe(tabela_sinal_fraco, use_container_width=True, height=400)
            
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
            
            st.dataframe(resumo_df, use_container_width=True)
            
        else:
            st.success("✅ Nenhuma ONU com sinal fraco detectada!")
            st.balloons()
    
    # ABA 3, 4 e 5: Continue o padrão...
    # (Devido ao limite de caracteres, vou mostrar apenas as abas principais)
    # O código completo continua igual ao seu app original, apenas adaptando:
    # - As mensagens de erro/sucesso
    # - O estilo dos st.metric
    # - Mantendo a mesma lógica de processamento
    
    with tab3:
        st.header("👥 Clientes Ativos sem ONU Cadastrada")
        st.info("⚙️ Funcionalidade em desenvolvimento - Copie o código da ABA 3 do app original aqui")
    
    with tab4:
        st.header("🏢 Clientes N1 (Rede Neutra)")
        st.info("⚙️ Funcionalidade em desenvolvimento - Copie o código da ABA 4 do app original aqui")
    
    with tab5:
        st.header("📊 CTOs Saturadas")
        st.info("⚙️ Funcionalidade em desenvolvimento - Copie o código da ABA 5 do app original aqui")
    
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
