"""
Manipulador de Viabilizações FTTA/Prédios
Salve como: pages/auditoria_functions/ftta_handler.py
"""

import streamlit as st
import logging
from pages.auditoria_functions.map_viewer import show_project_map

logger = logging.getLogger(__name__)

# ======================
# Função Principal
# ======================

def show_ftta_form(row: dict):
    """
    Exibe formulário de auditoria FTTA/Prédio
    
    Args:
        row: Dicionário com dados da viabilização
    """
    from viability_functions import (
        update_viability_ftta,
        request_building_viability,
        reject_building_viability,
        schedule_building_visit,
        format_time_br_supa
    )
    
    # Verificar status do prédio
    status_predio = row.get('status_predio')
    
    # ========================================
    # FORMULÁRIO INICIAL (sem viabilização ou rejeitado)
    # ========================================
    if status_predio is None or status_predio == 'rejeitado':
        st.markdown("#### 🏢 Dados do Prédio")
        
        # BOTÃO VER MAPA
        st.markdown("### 🗺️ Visualizar Projeto no Mapa")
        
        col_mapa_ftta = st.columns([1, 2, 1])[1]
        with col_mapa_ftta:
            if st.button(
                "🗺️ Ver Mapa do Projeto",
                width='stretch',
                key=f"ver_mapa_ftta_{row['id']}"
            ):
                st.session_state[f'show_map_ftta_{row["id"]}'] = True
        
        if st.session_state.get(f'show_map_ftta_{row["id"]}', False):
            show_project_map(
                pluscode=row['plus_code_cliente'],
                client_name=row.get('predio_ftta', 'Prédio'),
                unique_key=f"ftta_view_{row['id']}",
                show_ctos=False
            )
            
            col_fechar_mapa_ftta = st.columns([1, 2, 1])[1]
            with col_fechar_mapa_ftta:
                if st.button("❌ Fechar Mapa", width='stretch', key=f"fechar_mapa_ftta_{row['id']}"):
                    del st.session_state[f'show_map_ftta_{row["id"]}']
                    st.rerun()
        
        st.markdown("---")
        
        with st.form(key=f"form_ftta_{row['id']}"):
            cdoi_ftta = st.text_input(
                "📡 CDOI *",
                placeholder="Ex: CDOI-001, CDOI-ABC",
                key=f"cdoi_ftta_{row['id']}",
                help="Código da CDOI utilizada"
            )
            
            st.markdown("---")
            
            predio = st.text_input("Prédio FTTA", value=row.get('predio_ftta', ''), key=f"predio_{row['id']}")
                                    
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                portas = st.number_input("Portas Disponíveis", min_value=0, max_value=50, value=0, key=f"portas_ftta_{row['id']}")
            with col_f2:
                media_rx = st.text_input("Média RX (dBm)", placeholder="-20.5", key=f"media_rx_{row['id']}")
            
            obs = st.text_area("Observações", key=f"obs_ftta_{row['id']}", height=80)
            
            # Botões
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                aprovado = st.form_submit_button("✅ Viabilizar", type="primary", width='stretch')
            with col_btn2:
                utp = st.form_submit_button("📡 Atendemos UTP", width='stretch')                    
            with col_btn3:
                rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", width='stretch')
            
            if aprovado:
                if not cdoi_ftta or not cdoi_ftta.strip():
                    st.error("❌ Preencha a CDOI!")
                elif not predio or not predio.strip():
                    st.error("❌ Preencha o nome do Prédio!")
                elif portas <= 0:
                    st.error("❌ Preencha as Portas Disponíveis!")
                elif not media_rx or not media_rx.strip():
                    st.error("❌ Preencha a Média RX!")
                else:
                    dados = {
                        'cdoi': cdoi_ftta.strip(),
                        'predio_ftta': predio,
                        'portas_disponiveis': portas,
                        'media_rx': media_rx,
                        'observacoes': obs
                    }
                    if update_viability_ftta(row['id'], 'aprovado', dados):
                        st.success("✅ Viabilização aprovada!")
                        st.rerun()
            
            if rejeitado:
                st.session_state[f'show_reject_predio_form_{row["id"]}'] = True
            
            if utp:
                dados = {'motivo_rejeicao': 'Atendemos UTP'}
                if update_viability_ftta(row['id'], 'utp', dados):
                    st.success("📡 Marcado como Atendemos UTP")
                    st.rerun()
        
        # Formulário de rejeição
        if st.session_state.get(f'show_reject_predio_form_{row["id"]}', False):
            st.markdown("---")
            st.error("### ❌ Registrar Prédio Sem Viabilidade")
            
            with st.form(key=f"form_reject_predio_inicial_{row['id']}"):
                st.markdown("**Os seguintes dados serão registrados para consulta futura:**")
                
                col_rej1, col_rej2 = st.columns(2)
                with col_rej1:
                    st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                with col_rej2:
                    st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                
                motivo_rejeicao_predio = st.text_area(
                    "📝 Motivo da Não Viabilidade *",
                    placeholder="Descreva o motivo: não temos projeto nesta rua, distância muito grande, etc.",
                    height=100
                )
                
                col_btn_rej1, col_btn_rej2 = st.columns(2)
                
                with col_btn_rej1:
                    confirmar_rej_predio = st.form_submit_button(
                        "✅ Confirmar Rejeição",
                        type="primary",
                        width='stretch'
                    )
                
                with col_btn_rej2:
                    cancelar_rej_predio = st.form_submit_button(
                        "🔙 Cancelar",
                        width='stretch'
                    )
                
                if confirmar_rej_predio:
                    if not motivo_rejeicao_predio or motivo_rejeicao_predio.strip() == "":
                        st.error("❌ Descreva o motivo da não viabilidade!")
                    else:
                        if reject_building_viability(
                            row['id'],
                            row.get('predio_ftta', 'Prédio'),
                            row['plus_code_cliente'],
                            motivo_rejeicao_predio.strip()
                        ):
                            st.success("✅ Prédio registrado como sem viabilidade!")
                            st.info("📋 Registro salvo para consulta futura")
                            del st.session_state[f'show_reject_predio_form_{row["id"]}']
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar. Tente novamente.")
                
                if cancelar_rej_predio:
                    del st.session_state[f'show_reject_predio_form_{row["id"]}']
                    st.rerun()
        
        # BOTÃO VIABILIZAR PRÉDIO
        if status_predio is None:
            st.markdown("---")
            st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
            st.info("🔧 Temos projeto na rua, mas não temos estrutura pronta no prédio")
            
            col_viab_pred = st.columns([1, 2, 1])[1]
            with col_viab_pred:
                if st.button(
                    "🏢 Solicitar Viabilização do Prédio", 
                    type="primary", 
                    width='stretch',
                    key=f"viab_predio_{row['id']}"
                ):
                    if request_building_viability(row['id'], {}):
                        st.success("✅ Solicitação enviada! Aguardando dados do usuário.")
                        st.info("👤 O usuário receberá um formulário para preencher.")
                        st.rerun()
    
    # ========================================
    # AGUARDANDO DADOS
    # ========================================
    elif status_predio == 'aguardando_dados':
        st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
        st.warning("⏳ **Aguardando dados do usuário**")
        st.caption(f"📅 Solicitado em: {format_time_br_supa(row.get('data_solicitacao_predio', ''))}")
        st.info("👤 O usuário está preenchendo o formulário com os dados do prédio.")
    
    # ========================================
    # PRONTO PARA AUDITORIA
    # ========================================
    elif status_predio == 'pronto_auditoria':
        st.markdown("#### 🏗️ Viabilização de Estrutura no Prédio")
        st.success("✅ **Dados recebidos! Pronto para análise**")
        
        # Mostrar dados recebidos
        with st.expander("👁️ Ver Dados do Cliente", expanded=True):
            col_dados1, col_dados2 = st.columns(2)
            with col_dados1:
                st.markdown("**👤 Síndico**")
                st.text(f"Nome: {row.get('nome_sindico', 'N/A')}")
                st.text(f"Contato: {row.get('contato_sindico', 'N/A')}")
            with col_dados2:
                st.markdown("**🏠 Cliente**")
                st.text(f"Nome: {row.get('nome_cliente_predio', 'N/A')}")
                st.text(f"Contato: {row.get('contato_cliente_predio', 'N/A')}")
            
            st.text(f"🚪 Apartamento: {row.get('apartamento', 'N/A')}")
            st.text(f"🏢 Edifício: {row.get('predio_ftta', 'N/A')}")
            st.text(f"📍 Localização: {row['plus_code_cliente']}")
            
            if row.get('obs_agendamento'):
                st.markdown("**📝 Melhores horários:**")
                st.info(row['obs_agendamento'])
        
        st.markdown("---")
        st.markdown("### 📅 Agendar Visita Técnica")
        
        # Formulário de agendamento
        col_ag1, col_ag2 = st.columns(2)
        
        with col_ag1:
            data_visita = st.date_input(
                "📅 Data da Visita",
                key=f"data_visita_{row['id']}",
                help="Selecione a data para visita técnica",
                format="DD/MM/YYYY"
            )
        
        with col_ag2:
            periodo = st.selectbox(
                "🕐 Período",
                options=["Manhã", "Tarde"],
                key=f"periodo_{row['id']}"
            )
            
        # Segunda linha com Técnico e Tecnologia
        col_ag3, col_ag4 = st.columns(2)

        with col_ag3:
            tecnico = st.text_input(
                "👷 Técnico Responsável",
                placeholder="Nome do técnico",
                key=f"tecnico_{row['id']}"
            )
        with col_ag4:
            tecnologia = st.selectbox(
                "🔧 Tecnologia",
                options=["FTTA", "UTP", "FTTH"],
                key=f"tecnologia_{row['id']}",
                help="Tipo de tecnologia a ser instalada"
            )

        # Checkbox Giga
        giga_agendamento = st.checkbox("⚡ Prédio Giga?", key=f"giga_agendamento_{row['id']}")

        st.markdown("---")
        
        # Botões de ação
        col_action1, col_action2 = st.columns(2)
        
        with col_action1:
            if st.button(
                "📋 Agendar Visita Técnica",
                type="primary",
                width='stretch',
                key=f"agendar_{row['id']}"
            ):
                if not tecnico or not data_visita or not tecnologia:
                    st.error("❌ Preencha todos os campos de agendamento!")
                else:
                    if schedule_building_visit(
                        row['id'],
                        data_visita,
                        periodo,
                        tecnico,
                        tecnologia,
                        giga_agendamento
                    ):
                        st.success("✅ Visita agendada com sucesso!")
                        st.info("📅 Agendamento registrado na Agenda FTTA/UTP")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao agendar. Tente novamente.")
        
        with col_action2:
            if st.button(
                "❌ Edifício Sem Viabilidade",
                type="secondary",
                width='stretch',
                key=f"sem_viab_{row['id']}"
            ):
                st.session_state[f'show_reject_form_{row["id"]}'] = True
        
        # Formulário de rejeição (aparece ao clicar no botão)
        if st.session_state.get(f'show_reject_form_{row["id"]}', False):
            st.markdown("---")
            st.error("### ❌ Registrar Edifício Sem Viabilidade")
            
            with st.form(key=f"form_reject_building_{row['id']}"):
                st.markdown("**Os seguintes dados serão registrados para consulta futura:**")
                
                col_rej1, col_rej2 = st.columns(2)
                with col_rej1:
                    st.text_input("🏢 Condomínio", value=row.get('predio_ftta', ''), disabled=True)
                with col_rej2:
                    st.text_input("📍 Localização", value=row['plus_code_cliente'], disabled=True)
                
                motivo_rejeicao = st.text_area(
                    "📝 Motivo da Não Viabilidade *",
                    placeholder="Descreva o motivo: estrutura inadequada, recusa do síndico, etc.",
                    height=100
                )
                
                col_btn_rej1, col_btn_rej2 = st.columns(2)
                
                with col_btn_rej1:
                    confirmar_rejeicao = st.form_submit_button(
                        "✅ Confirmar Rejeição",
                        type="primary",
                        width='stretch'
                    )
                
                with col_btn_rej2:
                    cancelar = st.form_submit_button(
                        "🔙 Cancelar",
                        width='stretch'
                    )
                
                if confirmar_rejeicao:
                    if not motivo_rejeicao or motivo_rejeicao.strip() == "":
                        st.error("❌ Descreva o motivo da não viabilidade!")
                    else:                                                                        
                        if reject_building_viability(
                            row['id'],
                            row.get('predio_ftta', 'Prédio'),
                            row['plus_code_cliente'],
                            motivo_rejeicao.strip()
                        ):
                            st.success("✅ Edifício registrado como sem viabilidade!")
                            st.info("📝 Registro salvo para consulta futura")
                            del st.session_state[f'show_reject_form_{row["id"]}']
                            st.rerun()
                        else:
                            st.error("❌ Erro ao registrar. Tente novamente.")
                
                if cancelar:
                    del st.session_state[f'show_reject_form_{row["id"]}']
                    st.rerun()
