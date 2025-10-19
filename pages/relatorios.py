"""
Página de Relatórios - Histórico e estatísticas
Salve como: pages/relatorios.py
"""

import streamlit as st
from login_system import require_authentication
from viability_functions import get_archived_viabilities, get_statistics, format_time_br_supa, format_datetime_resultados
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Relatórios - Validador de Projetos",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação
if not require_authentication():
    st.stop()

# ======================
# Header
# ======================
st.title("📁 Relatórios e Arquivo")
st.markdown("Histórico completo de viabilizações")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.rerun()

st.markdown("---")

# ======================
# Estatísticas Gerais
# ======================
st.subheader("📊 Estatísticas Gerais")

stats = get_statistics()

col1, col2, col3 = st.columns(3)
#with col1:
   # st.metric("📦 Total", stats['total'])
with col1:
    st.metric("⏳ Pendentes", stats['pendentes'])
with col2:
    st.metric("✅ Finalizadas", stats['finalizadas'])
with col3:
    st.metric("❌ Rejeitadas", stats['rejeitadas'])
#with col5:
  #  st.metric("📈 Taxa Aprovação", f"{stats['taxa_aprovacao']:.1f}%")

st.markdown("---")

# ======================
# Buscar Dados Arquivados
# ======================
archived = get_archived_viabilities()
finalizadas = archived['finalizadas']
rejeitadas = archived['rejeitadas']

# ======================
# Abas de Visualização
# ======================
tab1, tab2 = st.tabs(["✅ Viabilidades Aprovadas", "❌ Sem Viabilidade"])

# ======================
# TAB 1: Viabilidades Aprovadas
# ======================
with tab1:
    st.markdown("### 📋 Viabilizações Finalizadas")
    
    if not finalizadas:
        st.info("Nenhuma viabilização finalizada ainda.")
    else:
        # Busca
        search_approved = st.text_input(
            "🔍 Buscar", 
            placeholder="Plus Code, CTO, Usuário, Prédio...", 
            key="search_approved"
        )
        
        # Filtrar
        df_finalizadas = pd.DataFrame(finalizadas)
        
        if search_approved:
            mask = df_finalizadas.astype(str).apply(
                lambda x: x.str.lower().str.contains(search_approved.lower(), na=False)
            ).any(axis=1)
            df_finalizadas = df_finalizadas[mask]
        
        st.caption(f"Mostrando {len(df_finalizadas)} de {len(finalizadas)} registros")
        
        # Exibir dados
        for _, row in df_finalizadas.iterrows():
            tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
            
            with st.expander(
                f"{tipo_icon} {row['plus_code_cliente']} - {row['usuario']} - {format_datetime_resultados(row['data_finalizacao'])}"
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📍 Informações Gerais")
                    st.text(f"Usuário: {row['usuario']}")
                    st.text(f"Plus Code: {row['plus_code_cliente']}")
                    st.text(f"Tipo: {row['tipo_instalacao']}")
                    st.text(f"Solicitado: {format_time_br_supa(row['data_solicitacao'])}")
                    st.text(f"Auditado: {format_datetime_resultados(row['data_auditoria'])}")
                    st.text(f"Finalizado: {format_datetime_resultados(row['data_finalizacao'])}")
                    st.text(f"Auditado por: {row['auditado_por']}")
                
                with col2:
                    if row['tipo_instalacao'] == 'FTTH':
                        st.markdown("#### 🏠 Dados FTTH")
                        st.text(f"N° Caixa: {row['cto_numero']}")
                        st.text(f"Portas: {row['portas_disponiveis']}")
                        st.text(f"Menor RX: {row['menor_rx']} dBm")
                        st.text(f"Distância: {row['distancia_cliente']}")
                        st.text(f"Localização: {row['localizacao_caixa']}")
                        if row.get('observacoes'):
                            st.text(f"Obs: {row['observacoes']}")
                    else:
                        st.markdown("#### 🏢 Dados FTTA")
                        st.text(f"Prédio: {row['predio_ftta']}")
                        st.text(f"Portas: {row['portas_disponiveis']}")
                        st.text(f"Média RX: {row['media_rx']} dBm")
                        if row.get('observacoes'):
                            st.text(f"Obs: {row['observacoes']}")

# ======================
# TAB 2: Sem Viabilidade
# ======================
with tab2:
    st.markdown("### 🚫 Solicitações Rejeitadas")
    
    if not rejeitadas:
        st.info("Nenhuma solicitação rejeitada.")
    else:
        # Busca
        search_rejected = st.text_input(
            "🔍 Buscar", 
            placeholder="Plus Code, Usuário...", 
            key="search_rejected"
        )
        
        # Filtrar
        df_rejeitadas = pd.DataFrame(rejeitadas)
        
        if search_rejected:
            mask = df_rejeitadas.astype(str).apply(
                lambda x: x.str.lower().str.contains(search_rejected.lower(), na=False)
            ).any(axis=1)
            df_rejeitadas = df_rejeitadas[mask]
        
        st.caption(f"Mostrando {len(df_rejeitadas)} de {len(rejeitadas)} registros")
        
        # Exibir dados
        for _, row in df_rejeitadas.iterrows():
            tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
            
            with st.expander(
                f"❌ {tipo_icon} {row['plus_code_cliente']} - {row['usuario']} - {format_datetime_resultados(row['data_auditoria'])}"
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📍 Informações")
                    st.text(f"Usuário: {row['usuario']}")
                    st.text(f"Plus Code: {row['plus_code_cliente']}")
                    st.text(f"Tipo: {row['tipo_instalacao']}")
                    st.text(f"Solicitado: {format_time_br_supa(row['data_solicitacao'])}")
                    st.text(f"Auditado: {format_datetime_resultados(row['data_auditoria'])}")
                    st.text(f"Auditado por: {row['auditado_por']}")
                
                with col2:
                    st.markdown("#### ❌ Motivo da Rejeição")
                    st.error(row.get('motivo_rejeicao', 'Não temos projeto neste ponto'))

# ======================
# Exportar Dados (se for Leo)
# ======================
st.markdown("---")

if st.session_state.user_login.lower() == "leo":
    st.subheader("📥 Exportar Dados")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        if finalizadas:
            df_export_fin = pd.DataFrame(finalizadas)
            csv_fin = df_export_fin.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Baixar Viabilizações Aprovadas (CSV)",
                data=csv_fin,
                file_name="viabilizacoes_aprovadas.csv",
                mime="text/csv",
                width='stretch'
            )
    
    with col_exp2:
        if rejeitadas:
            df_export_rej = pd.DataFrame(rejeitadas)
            csv_rej = df_export_rej.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Baixar Rejeitadas (CSV)",
                data=csv_rej,
                file_name="viabilizacoes_rejeitadas.csv",
                mime="text/csv",
                width='stretch'
            )

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📁 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
