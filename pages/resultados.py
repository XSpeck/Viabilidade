"""
Página de Resultados - Cada usuário vê apenas seus resultados
Salve como: pages/resultados.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import get_user_results, finalize_viability, finalize_viability_approved, format_datetime_resultados
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

# ======================
# Atualização automática
# ======================
st_autorefresh(interval=20000, key="resultados_refresh")  # 20000 ms = 20 segundos

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

# ======================
# Notificação de novos resultados
# ======================
if "resultados_anteriores" not in st.session_state:
    st.session_state.resultados_anteriores = len(results)

# Se há novos resultados desde a última atualização
if len(results) > st.session_state.resultados_anteriores:
    novos = len(results) - st.session_state.resultados_anteriores
    st.toast(f"🎉 {novos} novo(s) resultado(s) disponível(is)!", icon="✅")
    st.markdown("""
    <audio autoplay>
        <source src="https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg" type="audio/ogg">
    </audio>
    """, unsafe_allow_html=True)

# Atualiza contador
st.session_state.resultados_anteriores = len(results)

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
building_pending = [r for r in results if r.get('status_predio') in ['aguardando_dados', 'pronto_auditoria', 'agendado']]
pending_analysis = [r for r in results if r['status'] == 'pendente' and not r.get('status_predio')]

st.markdown("---")

# ======================
# Mostrar Em Andamento
# ======================
if pending_analysis:
    st.subheader("⏳ Em Análise Técnica")
    st.info("🔍 Suas solicitações estão sendo analisadas pela equipe técnica")
    
    for row in pending_analysis:
        tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
        tipo_nome = "Casa (FTTH)" if row['tipo_instalacao'] == 'FTTH' else "Edifício (FTTA)"
        urgente_badge = " 🔥 **URGENTE**" if row.get('urgente', False) else ""
        
        with st.expander(f"⏳ {tipo_icon} {row['plus_code_cliente']} - {tipo_nome}{urgente_badge}"):
            
            col_pend1, col_pend2 = st.columns(2)
            
            with col_pend1:
                st.markdown("### 📋 Informações")
                st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                st.text(f"🏷️ Tipo: {tipo_nome}")
                if row.get('predio_ftta'):
                    st.text(f"🏢 Edifício: {row['predio_ftta']}")
                st.text(f"📅 Solicitado: {format_datetime_resultados(row['data_solicitacao'])}")
                
                if row.get('urgente', False):
                    st.error("🔥 **Solicitação Urgente - Cliente Presencial**")
            
            with col_pend2:
                st.markdown("### ⏱️ Status")
                st.warning("🔍 **Em análise pela equipe técnica**")
                st.info("⏳ Aguarde a auditoria do Leo")
                st.caption("💡 Você será notificado quando a análise for concluída")
    
    st.markdown("---")

# ======================
# Mostrar Aprovadas
# ======================
if approved:
    st.subheader("✅ Viabilizações Aprovadas")
    st.success("🎉 Parabéns! Suas solicitações foram aprovadas!")
    
    for row in approved:
        with st.expander(f"📦 {row['plus_code_cliente']} - Auditado em {format_datetime_resultados(row['data_auditoria'])}", expanded=True):
            
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
                    if finalize_viability_approved(row['id']):
                        st.success("✅ Viabilização finalizada e arquivada!")
                        st.balloons()
                        st.rerun()
            
            st.caption(f"🕐 Auditado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

# ======================
# Mostrar Rejeitadas
# ======================
if rejected:
    st.markdown("---")
    st.subheader("❌ Solicitações Sem Viabilidade")
    
    for row in rejected:
        tipo_icon = "🏠" if row['tipo_instalacao'] == 'FTTH' else "🏢"
        with st.expander(f"⚠️ {tipo_icon} {row['plus_code_cliente']} - {format_datetime_resultados(row['data_auditoria'])}"):
            # Verificar se é rejeição de prédio
            if row.get('status_predio') == 'rejeitado':
                st.error("### 🏢 Edifício Sem Viabilidade")
                st.markdown(f"**Edifício:** {row.get('predio_ftta', 'N/A')}")
                st.markdown(f"**Localização:** {row['plus_code_cliente']}")
                
                if row.get('motivo_rejeicao'):
                    st.markdown("**Motivo:**")
                    st.warning(row['motivo_rejeicao'].replace('Edifício sem viabilidade: ', ''))
            else:
                # Mensagem padrão
                st.error("### 📝 Não temos projeto neste ponto")
            
                # Motivo
                if row.get('motivo_rejeicao'):
                    st.markdown(f"**Motivo:** {row['motivo_rejeicao']}")
            
            # Informações adicionais
            st.text(f"Tipo: {row['tipo_instalacao']}")
            st.text(f"Plus Code: {row['plus_code_cliente']}")
            st.caption(f"🕐 Analisado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")

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
        with st.expander(f"📡 {row['plus_code_cliente']} - {format_datetime_resultados(row['data_auditoria'])}"):
            
            # Mensagem padrão
            st.info("### 📡 Atendemos UTP")
            
            # Informações adicionais            
            st.text(f"Plus Code: {row['plus_code_cliente']}")
            st.caption(f"🕐 Analisado por: {row['auditado_por']} em {format_datetime_resultados(row['data_auditoria'])}")
            
            # Botão finalizar (não arquiva, apenas remove da lista)
            if st.button("✅ Finalizar", key=f"finish_utp_{row['id']}", type="primary", use_container_width=True):
                if finalize_viability(row['id']):
                    st.success("✅ Finalizado!")
                    st.rerun()
                    
# ======================
# Mostrar Viabilizações de Prédio Pendentes
# ======================
if building_pending:
    st.markdown("---")
    st.subheader("🏢 Viabilização de Prédio")
    st.warning("⚠️ Temos projeto na rua, mas precisamos viabilizar a estrutura no prédio.")    
    
    for row in building_pending:
        status_atual = row.get('status_predio')
        
        # Título diferente baseado no status
        if status_atual == 'agendado':
            titulo = f"📅 {row.get('predio_ftta', 'Prédio')} - Viabilidade Agendada"
            expandido = False
        elif status_atual == 'pronto_auditoria':
            titulo = f"⏳ {row.get('predio_ftta', 'Prédio')} - Aguardando Agendamento"
            expandido = False  # Não expandir automaticamente
        else:
            titulo = f"🏗️ {row.get('predio_ftta', 'Prédio')} - {row['plus_code_cliente']}"
            expandido = True  # Expandir para preencher
        
        with st.expander(titulo, expanded=expandido):
            # Se está agendado, mostrar informações e botão para consultar agenda
            if status_atual == 'agendado':
                st.success("✅ **Visita Técnica Agendada!**")
                
                col_agend1, col_agend2 = st.columns(2)
                
                with col_agend1:
                    st.markdown("### 📅 Dados do Agendamento")
                    st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                    st.text(f"📍 Localização: {row['plus_code_cliente']}")
                    st.text(f"📅 Data: {row.get('data_visita', 'N/A')}")
                    st.text(f"🕐 Período: {row.get('periodo_visita', 'N/A')}")
                
                with col_agend2:
                    st.markdown("### 👷 Informações Técnicas")
                    st.text(f"👤 Técnico: {row.get('tecnico_responsavel', 'N/A')}")
                    st.text(f"🔧 Tecnologia: {row.get('tecnologia_predio', 'N/A')}")
                    st.text(f"📆 Agendado em: {format_datetime_resultados(row.get('data_agendamento', ''))}")                
                    
            # Se já foi enviado, mostrar mensagem de aguardando
            elif status_atual == 'pronto_auditoria':
                st.success("✅ **Dados enviados com sucesso!**")
                st.info("⏳ **Aguardando agendamento da visita técnica pelo Leo**")
                
                st.markdown("---")
                st.markdown("### 📋 Dados Enviados")
                
                col_enviado1, col_enviado2 = st.columns(2)
                with col_enviado1:
                    st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
                    st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
                    st.text(f"👤 Síndico: {row.get('nome_sindico', 'N/A')}")
                    st.text(f"📞 Contato: {row.get('contato_sindico', 'N/A')}")
                
                with col_enviado2:
                    st.text(f"🏠 Cliente: {row.get('nome_cliente_predio', 'N/A')}")
                    st.text(f"📞 Contato: {row.get('contato_cliente_predio', 'N/A')}")
                    st.text(f"🚪 Apartamento: {row.get('apartamento', 'N/A')}")
                
                if row.get('obs_agendamento'):
                    st.markdown("**📝 Horários sugeridos:**")
                    st.info(row['obs_agendamento'])
                
                st.caption("💡 Você será notificado quando a visita for agendada")
                
            else:
                # Formulário para preencher (código que já existe)
                st.markdown("### 📋 Informações da Solicitação Original")
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.text(f"Nome do Edifício: {row.get('predio_ftta', 'N/A')}")
                    st.text(f"Plus Code: {row['plus_code_cliente']}")
                with col_info2:
                    st.text(f"Tipo: {row['tipo_instalacao']}")
                    st.text(f"Solicitado em: {format_datetime_resultados(row['data_solicitacao'])}")
                
                st.markdown("---")
                st.markdown("### 🔧 Preencha os Dados para Viabilização")
                
                with st.form(key=f"form_building_{row['id']}"):
                    
                    col_form1, col_form2 = st.columns(2)
                    
                    with col_form1:
                        st.markdown("#### 👤 Dados do Síndico")
                        nome_sindico = st.text_input(
                            "Nome do Síndico *",
                            placeholder="Nome completo",
                            key=f"sindico_nome_{row['id']}"
                        )
                        contato_sindico = st.text_input(
                            "Contato do Síndico *",
                            placeholder="(48) 99999-9999",
                            key=f"sindico_contato_{row['id']}"
                        )
                    
                    with col_form2:
                        st.markdown("#### 🏠 Dados do Cliente")
                        nome_cliente = st.text_input(
                            "Nome do Cliente *",
                            placeholder="Nome completo",
                            key=f"cliente_nome_{row['id']}"
                        )
                        contato_cliente = st.text_input(
                            "Contato do Cliente *",
                            placeholder="(48) 99999-9999",
                            key=f"cliente_contato_{row['id']}"
                        )
                        apartamento = st.text_input(
                            "Apartamento *",
                            placeholder="Ex: 301, Bloco A",
                            key=f"apartamento_{row['id']}"
                        )
                    
                    st.markdown("#### 📝 Observações")
                    obs_agendamento = st.text_area(
                        "Melhores datas e horários para visita técnica",
                        placeholder="Ex: Segunda ou Quarta, manhã (9h-12h)",
                        height=100,
                        key=f"obs_agend_{row['id']}"
                    )
                    
                    st.markdown("---")
                    col_submit = st.columns([1, 2, 1])[1]
                    with col_submit:
                        submit_building = st.form_submit_button(
                            "📤 Enviar para Auditoria Técnica",
                            type="primary",
                            use_container_width=True
                        )
                    
                    if submit_building:
                        # Validar campos obrigatórios
                        if not all([nome_sindico, contato_sindico, nome_cliente, contato_cliente, apartamento]):
                            st.error("❌ Preencha todos os campos obrigatórios (*)")
                        else:
                            from viability_functions import submit_building_data
                            
                            dados = {
                                'nome_sindico': nome_sindico.strip(),
                                'contato_sindico': contato_sindico.strip(),
                                'nome_cliente_predio': nome_cliente.strip(),
                                'contato_cliente_predio': contato_cliente.strip(),
                                'apartamento': apartamento.strip(),
                                'obs_agendamento': obs_agendamento.strip()
                            }
                            
                            if submit_building_data(row['id'], dados):
                                st.success("✅ Dados enviados com sucesso!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("❌ Erro ao enviar dados. Tente novamente.")                    
# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📊 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
