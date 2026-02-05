"""
Página de Agenda FTTA/UTP - Gerenciamento de Agendamentos
Salve como: pages/agenda_ftta_utp.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import (
    get_scheduled_visits,
    finalize_building_structured,
    reject_scheduled_building,
    format_datetime_resultados,
    reschedule_building_visit
)
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Agenda FTTA/UTP - Validador de Projetos",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh (opcional)
st_autorefresh(interval=30000, key="agenda_refresh")  # 30 segundos

# Verificar autenticação
if not require_authentication():
    st.stop()
    
# Verificar se é Admin (nível 1)
if st.session_state.user_nivel != 1:
    st.error("🚫 Acesso Negado! Esta página é restrita a administradores.")
    st.info("👈 Use o menu lateral para navegar.")
    st.stop()
    
# ======================
# Header
# ======================
st.title("📅 Agenda FTTA/UTP")
st.markdown("Gerenciamento de visitas técnicas agendadas")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", width='stretch'):
        st.rerun()

st.markdown("---")

# ======================
# Buscar Agendamentos
# ======================
agendamentos = get_scheduled_visits()

if agendamentos:  # Só mostra filtros se houver agendamentos
    st.subheader("🔍 Filtros")
    
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    # Extrair valores únicos
    tecnologias = list(set([a.get('tecnologia_predio', 'N/A') for a in agendamentos if a.get('tecnologia_predio')]))
    tecnicos = sorted(list(set([a.get('tecnico_responsavel', 'N/A') for a in agendamentos if a.get('tecnico_responsavel')])))
    datas = sorted(list(set([a.get('data_visita') for a in agendamentos if a.get('data_visita')])))
    
    with col_filtro1:
        filtro_tecnologia = st.selectbox(
            "🔧 Tecnologia",
            options=["Todas"] + tecnologias,
            key="filtro_tech"
        )
    
    with col_filtro2:
        filtro_tecnico = st.selectbox(
            "👷 Técnico",
            options=["Todos"] + tecnicos,
            key="filtro_tecnico"
        )
    
    with col_filtro3:
        # Formatar datas
        datas_dict = {}
        for d in datas:
            if d:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(str(d), '%Y-%m-%d')
                    data_br = dt.strftime('%d/%m/%Y')
                    datas_dict[data_br] = d
                except (ValueError, TypeError):
                    datas_dict[d] = d
        
        filtro_data = st.selectbox(
            "📅 Data",
            options=["Todas"] + list(datas_dict.keys()),
            key="filtro_data"
        )
    
    # APLICAR FILTROS
    agendamentos_original = agendamentos.copy()
    
    if filtro_tecnologia != "Todas":
        agendamentos = [a for a in agendamentos if a.get('tecnologia_predio') == filtro_tecnologia]
    
    if filtro_tecnico != "Todos":
        agendamentos = [a for a in agendamentos if a.get('tecnico_responsavel') == filtro_tecnico]
    
    if filtro_data != "Todas":
        data_iso = datas_dict.get(filtro_data, filtro_data)
        agendamentos = [a for a in agendamentos if a.get('data_visita') == data_iso]
    
    # Contador
    if len(agendamentos) != len(agendamentos_original):
        st.success(f"📊 Mostrando **{len(agendamentos)}** de **{len(agendamentos_original)}** agendamento(s)")
    
    st.markdown("---")
    
if not agendamentos:
    st.success("✅ Nenhuma visita técnica agendada no momento.")
else:
    st.subheader(f"📋 {len(agendamentos)} Visita(s) Agendada(s)")
    
    # Agrupar por data (opcional)
    # Aqui vamos mostrar todos em ordem cronológica
    
    for row in agendamentos:
        # Card de agendamento
        with st.container():
            st.markdown(f"""
            <div style='border-left: 5px solid #4CAF50; padding: 15px; 
                        background-color: #F1F8F4; border-radius: 5px; margin-bottom: 20px;'>
            </div>
            """, unsafe_allow_html=True)
            
            # Título com badge de status
            tecnologia = row.get('tecnologia_predio', 'N/A')
            tipo_instalacao = row.get('tipo_instalacao', 'Prédio')
            if tecnologia == "FTTA":
                cor_tech = "🔵"
            elif tecnologia == "FTTH":
                cor_tech = "🟠"
            else:  # UTP
                cor_tech = "🟢"

            icon_tipo = "🏘️" if tipo_instalacao == "Condomínio" else "🏢"
            st.markdown(f"### {icon_tipo} {row.get('predio_ftta', 'Prédio')} {cor_tech} {tecnologia}")
            
            # Mostrar se foi reagendado
            if row.get('historico_reagendamento'):
                st.warning(f"🔄 **Reagendado:** {row['historico_reagendamento']}")
            
            # Labels dinâmicos baseados no tipo
            is_condominio = tipo_instalacao == "Condomínio"
            label_local = "Condomínio" if is_condominio else "Edifício"
            label_unidade = "Casa" if is_condominio else "Apartamento"
            label_responsavel = "Responsável" if is_condominio else "Síndico"

            # Informações em colunas
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("#### 📍 Localização")
                st.text(f"Plus Code: {row['plus_code_cliente']}")
                st.text(f"{label_local}: {row.get('predio_ftta', 'N/A')}")
                st.text(f"{label_unidade}: {row.get('apartamento', 'N/A')}")

            with col2:
                st.markdown("#### 📅 Agendamento")
                data_visita = row.get('data_visita', 'N/A')
                if data_visita and data_visita != 'N/A':
                    try:
                        from datetime import datetime
                        data_obj = datetime.strptime(data_visita, '%Y-%m-%d')
                        data_visita = data_obj.strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        pass
                st.text(f"Data: {data_visita}")
                st.text(f"Período: {row.get('periodo_visita', 'N/A')}")
                st.text(f"Técnico: {row.get('tecnico_responsavel', 'N/A')}")
                st.text(f"Tecnologia: {row.get('tecnologia_predio', 'N/A')}")

            with col3:
                st.markdown("#### 👥 Contatos")
                st.text(f"{label_responsavel}: {row.get('nome_sindico', 'N/A')}")
                st.text(f"Tel: {row.get('contato_sindico', 'N/A')}")
                st.text(f"Cliente: {row.get('nome_cliente_predio', 'N/A')}")
                st.text(f"Tel: {row.get('contato_cliente_predio', 'N/A')}")
            
            # Observações
            if row.get('obs_agendamento'):
                st.markdown("**📝 Observações do Cliente:**")
                st.info(row['obs_agendamento'])
            
            st.markdown("---")
            
            # Botões de ação
            col_action1, col_action2, col_action3 = st.columns(3)
            
            with col_action1:
                if st.button(
                    "✅ Estruturado",
                    type="primary",
                    width='stretch',
                    key=f"estruturado_{row['id']}"
                ):
                    st.session_state[f'show_estruturado_form_{row["id"]}'] = True
            
            with col_action2:
                if st.button(
                    "🔄 Reagendar",
                    type="secondary",
                    width='stretch',
                    key=f"reagendar_{row['id']}"
                ):
                    st.session_state[f'show_reagendar_form_{row["id"]}'] = True
            
            with col_action3:
                if st.button(
                    "❌ Sem Viabilidade",
                    type="secondary",
                    width='stretch',
                    key=f"sem_viab_agenda_{row['id']}"
                ):
                    st.session_state[f'show_reject_agenda_form_{row["id"]}'] = True
            
            # Formulário de estruturação
            if st.session_state.get(f'show_estruturado_form_{row["id"]}', False):
                st.markdown("---")
                st.success("### ✅ Registrar como Estruturado")
                
                with st.form(key=f"form_estruturado_{row['id']}"):
                    st.markdown("**Os seguintes dados serão registrados:**")

                    col_est1, col_est2 = st.columns(2)
                    with col_est1:
                        st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                        st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                    with col_est2:
                        st.text_input("🔧 Tecnologia", value=row.get('tecnologia_predio', ''), disabled=True)
                        # Usa o valor salvo no agendamento como padrão
                        giga_checkbox = st.checkbox("⚡ Prédio Giga?", value=row.get('giga', False), key=f"giga_{row['id']}")

                    observacao_estrut = st.text_area(
                        "📝 Observações da Estruturação *",
                        placeholder="Detalhes sobre a instalação, materiais utilizados, etc.",
                        height=100
                    )
                    
                    col_btn_est1, col_btn_est2 = st.columns(2)
                    
                    with col_btn_est1:
                        confirmar_estrut = st.form_submit_button(
                            "✅ Confirmar Estruturação",
                            type="primary",
                            width='stretch'
                        )
                    
                    with col_btn_est2:
                        cancelar_est = st.form_submit_button(
                            "🔙 Cancelar",
                            width='stretch'
                        )
                    
                    if confirmar_estrut:
                        if not observacao_estrut or not observacao_estrut.strip():
                            st.error("❌ Adicione observações sobre a estruturação!")
                        else:
                            if finalize_building_structured(
                                row['id'],
                                row.get('predio_ftta', 'Prédio'),
                                row.get('tecnologia_predio', 'N/A'),
                                row['plus_code_cliente'],
                                observacao_estrut.strip(),
                                row.get('tecnico_responsavel', 'Técnico'),
                                giga_checkbox
                            ):
                                st.success("✅ Prédio registrado como estruturado!")
                                st.info("📝 Registro salvo em UTPs/FTTAs Atendidos")
                                del st.session_state[f'show_estruturado_form_{row["id"]}']
                                st.rerun()
                            else:
                                st.error("❌ Erro ao registrar. Tente novamente.")
                    
                    if cancelar_est:
                        del st.session_state[f'show_estruturado_form_{row["id"]}']
                        st.rerun()

            # Formulário de reagendamento
            if st.session_state.get(f'show_reagendar_form_{row["id"]}', False):
                st.markdown("---")
                st.warning("### 🔄 Reagendar Visita Técnica")
                
                with st.form(key=f"form_reagendar_{row['id']}"):
                    st.markdown("**📅 Dados Atuais:**")
                    col_atual1, col_atual2, col_atual3 = st.columns(3)
                    with col_atual1:
                        data_atual = row.get('data_visita', 'N/A')
                        if data_atual and data_atual != 'N/A':
                            try:
                                from datetime import datetime
                                data_obj = datetime.strptime(data_atual, '%Y-%m-%d')
                                data_atual = data_obj.strftime('%d/%m/%Y')
                            except (ValueError, TypeError):
                                pass
                        st.text_input("Data Atual", value=data_atual, disabled=True)
                    with col_atual2:
                        st.text_input("Período Atual", value=row.get('periodo_visita', 'N/A'), disabled=True)
                    with col_atual3:
                        st.text_input("Técnico Atual", value=row.get('tecnico_responsavel', 'N/A'), disabled=True)
                    
                    st.markdown("---")
                    st.markdown("**🆕 Novos Dados:**")
                    
                    col_novo1, col_novo2 = st.columns(2)
                    
                    with col_novo1:
                        nova_data = st.date_input(
                            "📅 Nova Data da Visita *",
                            key=f"nova_data_{row['id']}",
                            format="DD/MM/YYYY"
                        )
                    
                    with col_novo2:
                        novo_periodo = st.selectbox(
                            "🕐 Novo Período *",
                            options=["Manhã", "Tarde"],
                            key=f"novo_periodo_{row['id']}"
                        )
                    
                    novo_tecnico = st.text_input(
                        "👷 Novo Técnico Responsável *",
                        placeholder="Nome do técnico",
                        key=f"novo_tecnico_{row['id']}"
                    )
                    
                    motivo_reagendamento = st.text_area(
                        "📝 Motivo do Reagendamento",
                        placeholder="Ex: Cliente solicitou mudança de horário, técnico indisponível, etc.",
                        height=80,
                        key=f"motivo_reagend_{row['id']}"
                    )
                    
                    st.markdown("---")
                    
                    col_btn_reagend1, col_btn_reagend2 = st.columns(2)
                    
                    with col_btn_reagend1:
                        confirmar_reagend = st.form_submit_button(
                            "✅ Confirmar Reagendamento",
                            type="primary",
                            width='stretch'
                        )
                    
                    with col_btn_reagend2:
                        cancelar_reagend = st.form_submit_button(
                            "🔙 Cancelar",
                            width='stretch'
                        )
                    
                    if confirmar_reagend:
                        if not nova_data or not novo_tecnico or not novo_tecnico.strip():
                            st.error("❌ Preencha todos os campos obrigatórios!")
                        else:
                            if reschedule_building_visit(
                                row['id'],
                                nova_data,
                                novo_periodo,
                                novo_tecnico.strip(),
                                motivo_reagendamento.strip() if motivo_reagendamento else None
                            ):
                                st.success("✅ Visita reagendada com sucesso!")
                                st.info("📅 Novo agendamento registrado")
                                del st.session_state[f'show_reagendar_form_{row["id"]}']
                                st.rerun()
                            else:
                                st.error("❌ Erro ao reagendar. Tente novamente.")
                    
                    if cancelar_reagend:
                        del st.session_state[f'show_reagendar_form_{row["id"]}']
                        st.rerun()
            
            # Formulário de rejeição
            if st.session_state.get(f'show_reject_agenda_form_{row["id"]}', False):
                st.markdown("---")
                st.error("### ❌ Registrar Sem Viabilidade")
                
                with st.form(key=f"form_reject_agenda_{row['id']}"):
                    st.markdown("**Os seguintes dados serão registrados:**")
                    
                    col_rej1, col_rej2 = st.columns(2)
                    with col_rej1:
                        st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                    with col_rej2:
                        st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                    
                    motivo_rej = st.text_area(
                        "📝 Motivo da Não Viabilidade *",
                        placeholder="Ex: Estrutura inadequada, recusa do síndico, inviabilidade técnica...",
                        height=100
                    )
                    
                    col_btn_rej1, col_btn_rej2 = st.columns(2)
                    
                    with col_btn_rej1:
                        confirmar_rej = st.form_submit_button(
                            "✅ Confirmar Rejeição",
                            type="primary",
                            width='stretch'
                        )
                    
                    with col_btn_rej2:
                        cancelar_rej = st.form_submit_button(
                            "🔙 Cancelar",
                            width='stretch'
                        )
                    
                    if confirmar_rej:
                        if not motivo_rej or not motivo_rej.strip():
                            st.error("❌ Descreva o motivo da não viabilidade!")
                        else:
                            if reject_scheduled_building(
                                row['id'],
                                row.get('predio_ftta', 'Prédio'),
                                row['plus_code_cliente'],
                                motivo_rej.strip()
                            ):
                                st.success("✅ Registrado como sem viabilidade!")
                                st.info("📝 Registro salvo para consulta futura")
                                del st.session_state[f'show_reject_agenda_form_{row["id"]}']
                                st.rerun()
                            else:
                                st.error("❌ Erro ao registrar. Tente novamente.")
                    
                    if cancelar_rej:
                        del st.session_state[f'show_reject_agenda_form_{row["id"]}']
                        st.rerun()
            
            st.markdown("---")

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📅 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
