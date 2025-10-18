"""
Página de Resultados - Cada usuário vê apenas seus resultados
Salve como: pages/resultados.py
"""

import streamlit as st
from login_system import require_authentication
from viability_functions import get_user_results, finalize_viability
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Meus Resultados - Validador de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação
if not require_authentication():
    st.stop()

# ======================
# Header
# ======================
st.title("📊 Meus Resultados")
st.markdown(f"Viabilizações de **{st.session_state.user_name}**")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.rerun()


# ======================
# Buscar Resultados
# ======================
results = get_user_results(st.session_state.user_name)

if not results:
    st.info("📭 Você não possui resultados no momento.")
    st.markdown("""
    ### Como funciona?
    1. Faça uma busca na **página principal**
    2. Clique em **"Viabilizar"** ao encontrar uma CTO
    3. Aguarde a **auditoria técnica** do Leo
    4. Seus resultados aparecerão aqui!
    """)
    st.stop()

# Separar aprovados e rejeitados
approved = [r for r in results if r['status'] == 'aprovado']
rejected = [r for r in results if r['status'] == 'rejeitado']
utp = [r for r in results if r['status'] == 'utp']

st.markdown("---")

# ======================
# Mostrar Aprovadas
# ======================
if approved:
    st.subheader("✅ Viabilizações Aprovadas")
    st.success("🎉 Parabéns! Suas solicitações foram aprovadas!")
    
    for row in approved:
        with st.expander(f"📦 {row['plus_code_cliente']} - Auditado em {row['data_auditoria'][:16]}", expanded=True):
            
            # Verificar tipo
            if row['tipo_instalacao'] == 'FTTH':
                st.markdown("### 🏠 FTTH (Casa)")
                
                # Dados para copiar
                dados_completos = f"""N°Caixa: {row['cto_numero']}
Portas disponíveis: {row['portas_disponiveis']}
Menor RX: {row['menor_rx']} dBm
Distância até cliente: {row['distancia_cliente']}
Localização da Caixa: {row['localizacao_caixa']}"""
                
                if row.get('observacoes'):
                    dados_completos += f"\nObs: {row['observacoes']}"
                
            else:  # FTTA
                st.markdown("### 🏢 FTTA (Edifício)")
                
                # Dados para copiar
                dados_completos = f"""Prédio FTTA: {row['predio_ftta']}
Portas disponíveis: {row['portas_disponiveis']}
Média RX: {row['media_rx']} dBm"""
                
                if row.get('observacoes'):
                    dados_completos += f"\nObs: {row['observacoes']}"
            
            # Exibir dados
            st.code(dados_completos, language="text")
            
            col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])
            
            with col_btn1:
                st.markdown("💡 **Dica:** Selecione o texto acima e use Ctrl+C para copiar")
            
            with col_btn3:
                if st.button("✅ Finalizar", key=f"finish_{row['id']}", type="primary", width='stretch'):
                    if finalize_viability(row['id']):
                        st.success("✅ Viabilização finalizada e arquivada!")
                        st.balloons()
                        st.rerun()
            
            st.caption(f"🕐 Auditado por: {row['auditado_por']} em {row['data_auditoria'][:16]}")

# ======================
# Mostrar Rejeitadas
# ======================
if rejected:
    st.markdown("---")
    st.subheader("❌ Solicitações Sem Viabilidade")
    
    for row in rejected:
        with st.expander(f"⚠️ {row['plus_code_cliente']} - {row['data_auditoria'][:16]}"):
            
            # Mensagem padrão
            st.error("### 📝 Não temos projeto neste ponto")
            
            # Motivo
            if row.get('motivo_rejeicao'):
                st.markdown(f"**Motivo:** {row['motivo_rejeicao']}")
            
            # Informações adicionais
            st.text(f"Tipo: {row['tipo_instalacao']}")
            st.text(f"Plus Code: {row['plus_code_cliente']}")
            st.caption(f"🕐 Analisado por: {row['auditado_por']} em {row['data_auditoria'][:16]}")

            st.markdown("---")
            if st.button("✅ OK, Entendi", key=f"finish_rejected_{row['id']}", type="secondary", use_container_width=True):
                if finalize_viability(row['id']):
                    st.success("✅ Confirmado!")
                    st.rerun()
                    
# ======================
# Mostrar UTP
# ======================
if utp:
    st.markdown("---")
    st.subheader("📡 Atendemos UTP")
    
    for row in utp:
        with st.expander(f"📡 {row['plus_code_cliente']} - {row['data_auditoria'][:16]}"):
            
            # Mensagem padrão
            st.info("### 📡 Atendemos UTP")
            
            # Informações adicionais            
            st.text(f"Plus Code: {row['plus_code_cliente']}")
            st.caption(f"🕐 Analisado por: {row['auditado_por']} em {row['data_auditoria'][:16]}")
            
            # Botão finalizar (não arquiva, apenas remove da lista)
            if st.button("✅ Finalizar", key=f"finish_utp_{row['id']}", type="primary", use_container_width=True):
                if finalize_viability(row['id']):
                    st.success("✅ Finalizado!")
                    st.rerun()
                    
# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📊 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
