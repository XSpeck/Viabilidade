"""
Funções compartilhadas para o sistema de viabilização
Salve como: viability_functions.py
"""

import streamlit as st
import logging
from datetime import datetime
from typing import Dict, List, Optional
from supabase_config import supabase
from notifier import notify_new_viability, notify_new_agenda_data
import pytz
import re

logger = logging.getLogger(__name__)

TIMEZONE_BR = pytz.timezone('America/Sao_Paulo')  # Brasília (UTC-3)
# ======================
# Funções de CRUD
# ======================

def get_current_time():
    """Retorna data/hora atual no fuso horário do Brasil"""
    return datetime.now(TIMEZONE_BR).isoformat()

# ======================
# Funções Utilitárias
# ======================
def validate_plus_code(plus_code: str) -> bool:
    pattern = r'^[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3}$'
    return bool(re.match(pattern, plus_code.upper().strip()))

def format_time_br(iso_string: str, only_time: bool = False) -> str:
    """Converte string ISO em formato legível no fuso horário de Brasília"""
    if not iso_string:
        return "-"
    try:
        # Se for timestamp (número), converter direto
        if isinstance(iso_string, (int, float)):
            dt = datetime.fromtimestamp(iso_string, TIMEZONE_BR)
        else:
            # Se for string ISO, converter para datetime
            dt = datetime.fromisoformat(str(iso_string).replace('Z', '+00:00'))
            # Converter para fuso de Brasília
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            dt = dt.astimezone(TIMEZONE_BR)
        
        # Formatar conforme solicitado
        fmt = '%H:%M:%S' if only_time else '%d/%m/%Y %H:%M'
        return dt.strftime(fmt)
    except Exception as e:
        logger.warning(f"Erro ao converter horário '{iso_string}': {e}")
        return "-"
    
def format_time_br_supa(utc_time_str: str) -> str:
    """
    Converte uma string de datetime UTC (ISO) para horário de Brasília (UTC-3)
    e formata como 'dd/mm/aaaa hh:mm'.
    """
    if not utc_time_str:
        return "-"
    
    try:
        # Se for string vazia ou None
        if isinstance(utc_time_str, str):
            utc_time_str = utc_time_str.strip()
            if not utc_time_str:
                return "-"
        
        # Remover 'Z' final se existir (ISO 8601 UTC indicator)
        utc_time_str = str(utc_time_str).replace('Z', '+00:00')
        
        # Converter para datetime
        utc_dt = datetime.fromisoformat(utc_time_str)
        
        # Se não tiver timezone, adicionar UTC
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        
        # Converter para Brasília
        br_dt = utc_dt.astimezone(TIMEZONE_BR)
        
        # Formatar
        return br_dt.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        logger.warning(f"Erro ao formatar data Supabase '{utc_time_str}': {e}")
        return str(utc_time_str)[:16]  # Retorna string truncada como fallback   

def format_datetime_resultados(iso_datetime: str) -> str:
    """
    Converte datetime ISO para formato brasileiro
    Ex: 2025-10-19T20:19:15.374522 -> 19/10/2025 20:19
    """
    try:
        # Verificar se é None ou vazio
        if not iso_datetime or iso_datetime == '' or pd.isna(iso_datetime):
            return "N/A"
        
        # Converter para string se não for
        iso_datetime = str(iso_datetime)
        
        # Tentar converter para datetime
        dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception as e:
        logger.error(f"Erro ao formatar data '{iso_datetime}': {e}")
        
        # Fallback seguro: garantir que é string antes de fazer slice
        try:
            iso_str = str(iso_datetime)
            if len(iso_str) >= 16:
                return iso_str[:16]
            else:
                return iso_str
        except:
            return "N/A"
   
def create_viability_request(user_name: str, plus_code: str, tipo: str, urgente: bool = False, nome_predio: str = None, nome_cliente: str = None, andar: str = None, bloco: str = None) -> bool:
    """
    Cria nova solicitação de viabilização no Supabase
    
    Args:
        user_name: Nome do usuário solicitante
        plus_code: Plus Code do cliente
        tipo: 'FTTH' ou 'Prédio'
        urgente: Se é cliente presencial (urgente)
        nome_predio: Nome do prédio (apenas para Prédio)
        nome_cliente: Nome do cliente final
        andar: Andar onde o cliente mora (para Prédio)
        bloco: Bloco do prédio se houver (para Prédio)
    """
    try:
        new_request = {
            'usuario': user_name,
            'plus_code_cliente': plus_code,
            'tipo_instalacao': tipo,
            'urgente': urgente,
            'status': 'pendente'
        }

        # Adicionar nome do prédio/condomínio se for Prédio ou Condomínio
        if tipo in ['Prédio', 'Predio', 'Condomínio'] and nome_predio:
            new_request['predio_ftta'] = nome_predio
        # Adicionar nome do cliente se fornecido
        if nome_cliente:
            new_request['nome_cliente'] = nome_cliente

        if tipo in ['Prédio', 'Predio', 'Condomínio']:
            if andar:
                new_request['andar_predio'] = andar
            if bloco:
                new_request['bloco_predio'] = bloco
            
        response = supabase.table('viabilizacoes').insert(new_request).execute()
        
        if response.data:
            logger.info(f"Viabilização criada: {user_name} - {plus_code} - Tipo: {tipo} - Urgente: {urgente}")
           
            # 🚀 Enviar notificação via Telegram ao criar nova solicitação
            try:                
                notify_new_viability()
            except Exception as e:
                logger.warning(f"Não foi possível enviar notificação Telegram: {e}")
            
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao criar solicitação: {e}")
        st.error(f"❌ Erro ao criar viabilização: {e}")
        return False

def get_pending_viabilities() -> List[Dict]:
    """Busca viabilizações pendentes ordenadas por urgência"""
    try:
        # Buscar pendentes ordenados por urgência (urgentes primeiro) e depois por data
        response = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'pendente')\
            .order('urgente', desc=True)\
            .order('data_solicitacao', desc=False)\
            .execute()
        
        # Filtrar manualmente os que NÃO devem aparecer
        if response.data:
            filtered = []
            for r in response.data:
                
                # Excluir Prédios que já foram agendados
                if r.get('status_predio') == 'agendado':
                    continue
                
                # Todos os outros devem aparecer
                filtered.append(r)
            
            return filtered
        
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar pendentes: {e}")
        return []

def get_user_results(username: str) -> List[Dict]:
    """Busca resultados do usuário (aprovados, rejeitados, UTPs, estruturados pendentes)"""
    try:
        response = (
            supabase.table('viabilizacoes')
            .select('*')
            .ilike('usuario', username)
            .or_('status.in.(aprovado,rejeitado,utp,pendente,em_auditoria),status_predio.in.(aguardando_dados,agendado,estruturado)')
            .is_('data_finalizacao', None)
            .order('data_auditoria', desc=True)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar resultados: {e}")
        return []

def get_archived_viabilities() -> Dict[str, List[Dict]]:
    """Busca viabilizações finalizadas e rejeitadas para o arquivo (exceto estruturados)"""
    try:
        finalizadas = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'finalizado')\
            .neq('status_predio', 'estruturado')\
            .order('data_finalizacao', desc=True)\
            .execute()
        
        rejeitadas = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'rejeitado')\
            .or_('status_predio.is.null,status_predio.neq.rejeitado')\
            .order('data_auditoria', desc=True)\
            .execute()
        
        return {
            'finalizadas': finalizadas.data if finalizadas.data else [],
            'rejeitadas': rejeitadas.data if rejeitadas.data else []
        }
    except Exception as e:
        logger.error(f"Erro ao buscar arquivo: {e}")
        return {'finalizadas': [], 'rejeitadas': []}

def update_viability_ftth(viability_id: str, status: str, dados: Dict, auditado_por: str = None) -> bool:
    """
    Atualiza viabilização FTTH (casa)
    
    Args:
        viability_id: ID da viabilização
        status: 'aprovado' ou 'rejeitado'
        dados: Dicionário com os dados FTTH
        auditado_por: Nome do auditor
    """
    try:
        # ✅ DEFINIR auditado_por ANTES de usar
        if auditado_por is None:
            auditado_por = st.session_state.get('user_name', 'Sistema')
        
        update_data = {
            'status': status,
            'data_auditoria': get_current_time(),
            'auditado_por': auditado_por
        }
                
        if status == 'aprovado':
            update_data.update({
                'cto_numero': dados.get('cto_numero'),
                'portas_disponiveis': dados.get('portas_disponiveis'),
                'menor_rx': dados.get('menor_rx'),
                'distancia_cliente': dados.get('distancia_cliente'),
                'localizacao_caixa': dados.get('localizacao_caixa'),
                'observacoes': dados.get('observacoes', '')
            })
        elif status == 'rejeitado':
            update_data['motivo_rejeicao'] = dados.get('motivo_rejeicao', 'Não temos projeto neste ponto')
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Viabilização FTTH {viability_id} atualizada para {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao atualizar viabilização FTTH: {e}")
        st.error(f"❌ Erro ao atualizar: {e}")
        return False

def update_viability_ftta(viability_id: str, status: str, dados: Dict, auditado_por: str = None) -> bool:
    """
    Atualiza viabilização FTTA (edifício)
    
    Args:
        viability_id: ID da viabilização
        status: 'aprovado' ou 'rejeitado'
        dados: Dicionário com os dados FTTA
        auditado_por: Nome do auditor
    """
    try:
        if auditado_por is None:
            auditado_por = st.session_state.get('user_name', 'Sistema')
        
        update_data = {
            'status': status,
            'data_auditoria': get_current_time(),
            'auditado_por': auditado_por
        }
        
        if status == 'aprovado':
            update_data.update({
                'cdoi': dados.get('cdoi'),
                'predio_ftta': dados.get('predio_ftta'),
                'portas_disponiveis': dados.get('portas_disponiveis'),
                'media_rx': dados.get('media_rx'),
                'observacoes': dados.get('observacoes', '')
            })
        elif status == 'rejeitado':
            update_data['motivo_rejeicao'] = dados.get('motivo_rejeicao', 'Não temos projeto neste ponto')
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Viabilização FTTA {viability_id} atualizada para {status}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao atualizar viabilização FTTA: {e}")
        st.error(f"❌ Erro ao atualizar: {e}")
        return False

def finalize_viability(viability_id: str) -> bool:
    """Marca viabilização como finalizada"""
    try:
        update_data = {
            
            'data_finalizacao': get_current_time()
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Viabilização {viability_id} finalizada")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao finalizar viabilização: {e}")
        st.error(f"❌ Erro ao finalizar: {e}")
        return False

def finalize_viability_approved(viability_id: str) -> bool:
    """Finaliza viabilização aprovada (muda status para finalizado)"""
    try:
        update_data = {
            'status': 'finalizado',
            'data_finalizacao': get_current_time()
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Viabilização aprovada {viability_id} finalizada")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao finalizar viabilização aprovada: {e}")
        st.error(f"❌ Erro ao finalizar: {e}")
        return False

def delete_viability(viability_id: str) -> tuple:
    """Deleta uma viabilização (somente Leo).

    Retorna um tuple (success: bool, info: dict) onde `info` contém detalhes
    úteis para depuração (status_code, data, repr).
    """
    try:
        response = supabase.table('viabilizacoes').delete().eq('id', viability_id).execute()

        status = getattr(response, 'status_code', None)
        data = getattr(response, 'data', None)

        info = {
            'status_code': status,
            'data': data,
            'response_repr': repr(response)
        }

        if data or status in (200, 204):
            logger.info(f"Viabilização {viability_id} deletada (status={status})")
            return True, info

        logger.warning(f"Tentativa de deletar viabilização retornou sem dados: id={viability_id}, status={status}")
        return False, info
    except Exception as e:
        logger.exception(f"Erro ao deletar viabilização: {e}")
        info = {'error': str(e)}
        return False, info

def request_building_viability(viability_id: str, dados: Dict) -> bool:
    """
    Marca viabilização FTTA como 'aguardando dados do prédio'
    E solicita preenchimento de formulário ao usuário
    
    Args:
        viability_id: ID da viabilização
        dados: Dicionário vazio (por enquanto)
    """
    try:
        update_data = {
            'status_predio': 'aguardando_dados',
            'data_solicitacao_predio': get_current_time()
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Viabilização de prédio solicitada: {viability_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao solicitar viabilização de prédio: {e}")
        st.error(f"❌ Erro ao solicitar: {e}")
        return False

def register_building_without_viability(condominio: str, localizacao: str, observacao: str, registrado_por: str = None) -> bool:
    """
    Registra prédio sem viabilidade na tabela de consulta
    
    Args:
        condominio: Nome do prédio
        localizacao: Plus Code ou endereço
        observacao: Motivo da não viabilidade
        registrado_por: Nome do usuário
    """
    try:
        if registrado_por is None:
            registrado_por = st.session_state.get('user_name', 'Sistema')
            
        new_record = {
            'condominio': condominio,
            'localizacao': localizacao,
            'observacao': observacao,
            'registrado_por': registrado_por
        }
        
        response = supabase.table('predios_sem_viabilidade').insert(new_record).execute()
        
        if response.data:
            logger.info(f"Prédio sem viabilidade registrado: {condominio}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao registrar prédio sem viabilidade: {e}")
        st.error(f"❌ Erro ao registrar: {e}")
        return False


def reject_building_viability(viability_id: str, condominio: str, localizacao: str, observacao: str, auditado_por: str = None) -> bool:
    """
    Rejeita viabilização de prédio e registra na tabela de consulta
    
    Args:
        viability_id: ID da viabilização
        condominio: Nome do prédio
        localizacao: Plus Code
        observacao: Motivo da rejeição
        auditado_por: Nome do auditor
    """
    try:
        if auditado_por is None:
            auditado_por = st.session_state.get('user_name', 'Sistema')
        
        # 1. Registrar na tabela de prédios sem viabilidade
        if not register_building_without_viability(condominio, localizacao, observacao, auditado_por):
            return False
        
        # 2. Atualizar status da viabilização
        update_data = {
            'status': 'rejeitado',
            'status_predio': 'rejeitado',
            'motivo_rejeicao': f'Edifício sem viabilidade: {observacao}',
            'data_auditoria': get_current_time(),
            'auditado_por': auditado_por
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Viabilização de prédio rejeitada: {viability_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao rejeitar viabilização de prédio: {e}")
        st.error(f"❌ Erro ao rejeitar: {e}")
        return False

def submit_building_data(viability_id: str, dados: Dict) -> bool:
    """
    Submete dados do prédio preenchidos pelo usuário
    E retorna para auditoria técnica
    
    Args:
        viability_id: ID da viabilização
        dados: {
            'nome_sindico': str,
            'contato_sindico': str,
            'nome_cliente_predio': str,
            'contato_cliente_predio': str,
            'apartamento': str,
            'obs_agendamento': str
        }
    """
    try:
        update_data = {
            'status_predio': 'pronto_auditoria',
            'nome_sindico': dados.get('nome_sindico'),
            'contato_sindico': dados.get('contato_sindico'),
            'nome_cliente_predio': dados.get('nome_cliente_predio'),
            'contato_cliente_predio': dados.get('contato_cliente_predio'),
            'apartamento': dados.get('apartamento'),
            'obs_agendamento': dados.get('obs_agendamento', '')
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Dados do prédio submetidos: {viability_id}")
            try:                
                notify_new_agenda_data()
            except Exception as e:
                logger.warning(f"Não foi possível enviar notificação Telegram: {e}")
            
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao submeter dados do prédio: {e}")
        st.error(f"❌ Erro ao submeter: {e}")
        return False

def schedule_building_visit(viability_id: str, data_visita: str, periodo: str, tecnico: str, tecnologia: str, giga: bool = False) -> bool:
    """
    Agenda visita técnica para prédio

    Args:
        viability_id: ID da viabilização
        data_visita: Data da visita (formato: YYYY-MM-DD)
        periodo: "Manhã" ou "Tarde"
        tecnico: Nome do técnico responsável
        tecnologia: "FTTA" ou "UTP"
        giga: Se o prédio é Giga ou não
    """
    try:
        update_data = {
            'status_predio': 'agendado',
            'status_agendamento': 'pendente',
            'data_visita': str(data_visita),
            'periodo_visita': periodo,
            'tecnico_responsavel': tecnico,
            'tecnologia_predio': tecnologia,
            'data_agendamento': get_current_time(),
            'giga': giga
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Visita agendada: {viability_id} - {data_visita} {periodo} - {tecnico}")            
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao agendar visita: {e}")
        st.error(f"❌ Erro ao agendar: {e}")
        return False

def reschedule_building_visit(viability_id: str, nova_data: str, novo_periodo: str, novo_tecnico: str, motivo_reagendamento: str = None) -> bool:
    """
    Reagenda visita técnica para prédio
    
    Args:
        viability_id: ID da viabilização
        nova_data: Nova data da visita (formato: YYYY-MM-DD)
        novo_periodo: "Manhã" ou "Tarde"
        novo_tecnico: Nome do técnico responsável
        motivo_reagendamento: Motivo do reagendamento (opcional)
    """
    try:
        # Buscar dados atuais para histórico
        response_atual = supabase.table('viabilizacoes')\
            .select('data_visita, periodo_visita, tecnico_responsavel')\
            .eq('id', viability_id)\
            .execute()
        
        historico_texto = ""
        if response_atual.data and len(response_atual.data) > 0:
            dados_antigos = response_atual.data[0]
            historico_texto = f"Reagendado de {dados_antigos.get('data_visita', 'N/A')} {dados_antigos.get('periodo_visita', '')} "
            historico_texto += f"({dados_antigos.get('tecnico_responsavel', 'N/A')}) "
            
            if motivo_reagendamento:
                historico_texto += f"- Motivo: {motivo_reagendamento}"
        
        # Atualizar com novos dados
        update_data = {
            'data_visita': str(nova_data),
            'periodo_visita': novo_periodo,
            'tecnico_responsavel': novo_tecnico,
            'data_agendamento': get_current_time(),  # Atualiza timestamp
            'historico_reagendamento': historico_texto  # Novo campo para histórico
        }
        
        response = supabase.table('viabilizacoes')\
            .update(update_data)\
            .eq('id', viability_id)\
            .execute()
        
        if response.data:
            logger.info(f"Visita reagendada: {viability_id} - {nova_data} {novo_periodo} - {novo_tecnico}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao reagendar visita: {e}")
        st.error(f"❌ Erro ao reagendar: {e}")
        return False

def get_scheduled_visits() -> List[Dict]:
    """Busca agendamentos pendentes"""
    try:
        response = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status_predio', 'agendado')\
            .eq('status_agendamento', 'pendente')\
            .order('data_visita', desc=False)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar agendamentos: {e}")
        return []

def finalize_building_structured(viability_id: str, condominio: str, tecnologia: str, localizacao: str, observacao: str, tecnico: str, giga: bool = False) -> bool:
    """
    Finaliza agendamento como estruturado e registra na tabela de atendidos

    Args:
        viability_id: ID da viabilização
        condominio: Nome do prédio
        tecnologia: "FTTA" ou "UTP"
        localizacao: Plus Code
        observacao: Observações sobre a estruturação
        tecnico: Nome do técnico que estruturou
        giga: Se o prédio é Giga ou não
    """
    try:
        # 1. Registrar na tabela de atendidos
        new_record = {
            'condominio': condominio,
            'tecnologia': tecnologia,
            'localizacao': localizacao,
            'observacao': observacao,
            'estruturado_por': tecnico,
            'viabilizacao_id': viability_id,
            'giga': giga
        }
        
        response_insert = supabase.table('utps_fttas_atendidos').insert(new_record).execute()
        
        if not response_insert.data:
            return False
        
        # 2. Atualizar viabilização como finalizada
        update_data = {
            'status': 'finalizado',
            'status_predio': 'estruturado',
            'status_agendamento': 'concluido',
            #'data_finalizacao': get_current_time()
        }
        
        response_update = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response_update.data:
            logger.info(f"Prédio estruturado: {condominio} - {tecnologia} - por {tecnico}")            
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao finalizar estruturação: {e}")
        st.error(f"❌ Erro ao finalizar: {e}")
        return False


def reject_scheduled_building(viability_id: str, condominio: str, localizacao: str, observacao: str) -> bool:
    """
    Rejeita agendamento e registra prédio sem viabilidade
    """
    try:
        # 1. Registrar na tabela de sem viabilidade
        if not register_building_without_viability(condominio, localizacao, observacao):
            return False
        
        # 2. Atualizar status
        update_data = {
            'status': 'rejeitado',
            'status_predio': 'rejeitado',
            'status_agendamento': 'cancelado',
            'motivo_rejeicao': f'Edifício sem viabilidade: {observacao}',
            'data_finalizacao': get_current_time()
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"Agendamento rejeitado: {viability_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao rejeitar agendamento: {e}")
        st.error(f"❌ Erro ao rejeitar: {e}")
        return False

def get_structured_buildings() -> List[Dict]:
    """Busca prédios estruturados (UTPs/FTTAs atendidos)"""
    try:
        response = supabase.table('utps_fttas_atendidos')\
            .select('*')\
            .order('data_estruturacao', desc=True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar prédios estruturados: {e}")
        return []


def get_buildings_without_viability() -> List[Dict]:
    """Busca prédios sem viabilidade"""
    try:
        response = supabase.table('predios_sem_viabilidade')\
            .select('*')\
            .order('data_registro', desc=True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar prédios sem viabilidade: {e}")
        return []

def save_selected_cto(viability_id: str, cto_data: Dict) -> bool:
    """
    Salva a CTO escolhida pelo Leo na busca detalhada
    
    Args:
        viability_id: ID da viabilização
        cto_data: {
            'cto_numero': str,
            'distancia_cliente': str,
            'localizacao_caixa': str
        }
    """
    try:
        update_data = {
            'status_busca': 'cto_escolhida',
            'cto_numero': cto_data.get('cto_numero'),
            'distancia_cliente': cto_data.get('distancia_cliente'),
            'localizacao_caixa': cto_data.get('localizacao_caixa')
        }
        
        response = supabase.table('viabilizacoes').update(update_data).eq('id', viability_id).execute()
        
        if response.data:
            logger.info(f"CTO escolhida salva: {viability_id} - {cto_data.get('cto_numero')}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao salvar CTO escolhida: {e}")
        st.error(f"❌ Erro ao salvar: {e}")
        return False

def get_ftth_pending_search() -> List[Dict]:
    """Busca solicitações FTTH aguardando busca detalhada (Leo escolher CTO)"""
    try:
        response = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('tipo_instalacao', 'FTTH')\
            .eq('status', 'pendente')\
            .is_('status_busca', None)\
            .order('urgente', desc=True)\
            .order('data_solicitacao', desc=False)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar FTTH pendentes: {e}")
        return []

def get_auditor_viabilities(auditor_name: str) -> List[Dict]:
    """Busca viabilizações em auditoria do auditor específico"""
    try:
        response = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'em_auditoria')\
            .eq('auditor_responsavel', auditor_name)\
            .order('urgente', desc=True)\
            .order('data_solicitacao', desc=False)\
            .execute()
        
        if response.data:
            # Filtrar prédios agendados
            filtered = [r for r in response.data if r.get('status_predio') != 'agendado']
            return filtered
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar viabilizações do auditor: {e}")
        return []

def devolver_viabilidade(viability_id: str) -> tuple:
    """Devolve viabilização para fila (remove auditor e volta para pendente).

    Retorna (success: bool, info: dict) com detalhes de resposta para depuração.
    """
    try:
        update_data = {
            'status': 'pendente',
            'auditor_responsavel': None
        }

        response = supabase.table('viabilizacoes')\
            .update(update_data)\
            .eq('id', viability_id)\
            .execute()

        status = getattr(response, 'status_code', None)
        data = getattr(response, 'data', None)
        info = {
            'status_code': status,
            'data': data,
            'response_repr': repr(response)
        }

        if data or status in (200, 204):
            logger.info(f"Viabilização {viability_id} devolvida (status={status})")
            return True, info
        logger.warning(f"Devolver viabilização retornou sem dados: {viability_id} - resp: {status}")
        return False, info
    except Exception as e:
        logger.exception(f"Erro ao devolver viabilização: {e}")
        return False, {'error': str(e)}
        
# ======================
# Funções para Relatórios
# ======================

def get_ftth_approved(data_inicio: str = None, data_fim: str = None) -> List[Dict]:
    """Busca todas as viabilizações FTTH aprovadas (inclui finalizadas)"""
    try:
        query = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('tipo_instalacao', 'FTTH')\
            .in_('status', ['aprovado', 'finalizado'])
        
        # Filtro por data (se fornecido)
        if data_inicio:
            query = query.gte('data_auditoria', data_inicio)
        if data_fim:
            query = query.lte('data_auditoria', data_fim)
        
        response = query.order('data_auditoria', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar FTTH aprovadas: {e}")
        return []

def get_all_approved(data_inicio: str = None, data_fim: str = None) -> List[Dict]:
    """Busca todas as viabilizações aprovadas (FTTH, Prédio, Condomínio)"""
    try:
        query = supabase.table('viabilizacoes')\
            .select('*')\
            .in_('status', ['aprovado', 'finalizado'])

        # Filtro por data (se fornecido)
        if data_inicio:
            query = query.gte('data_auditoria', data_inicio)
        if data_fim:
            query = query.lte('data_auditoria', data_fim)

        response = query.order('data_auditoria', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar todas aprovadas: {e}")
        return []

def get_ftth_rejected(data_inicio: str = None, data_fim: str = None) -> List[Dict]:
    """Busca todas as viabilizações FTTH rejeitadas"""
    try:
        query = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('tipo_instalacao', 'FTTH')\
            .eq('status', 'rejeitado')
        
        # Filtro por data (se fornecido)
        if data_inicio:
            query = query.gte('data_auditoria', data_inicio)
        if data_fim:
            query = query.lte('data_auditoria', data_fim)
        
        response = query.order('data_auditoria', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar FTTH rejeitadas: {e}")
        return []

def get_report_statistics(data_inicio: str = None, data_fim: str = None) -> Dict:
    """Retorna estatísticas detalhadas para relatórios"""
    try:
        query = supabase.table('viabilizacoes').select('*')
        
        # Filtro por data (se fornecido)
        if data_inicio:
            query = query.gte('data_auditoria', data_inicio)
        if data_fim:
            query = query.lte('data_auditoria', data_fim)
        
        response = query.execute()
        
        if not response.data:
            return {
                'ftth_aprovadas': 0,
                'ftth_rejeitadas': 0,
                'predios_estruturados': 0,
                'pontos_sem_viabilidade': 0,
                'taxa_aprovacao_ftth': 0
            }
        
        data = response.data
        
        # APROVADAS = aprovado + finalizado
        ftth_aprovadas = len([d for d in data 
                             if d['tipo_instalacao'] == 'FTTH' 
                             and d['status'] in ['aprovado', 'finalizado']])
        
        ftth_rejeitadas = len([d for d in data 
                              if d['tipo_instalacao'] == 'FTTH' 
                              and d['status'] == 'rejeitado'])
        
        # Prédios estruturados (sem filtro de data - mostra total)
        predios_response = supabase.table('utps_fttas_atendidos').select('*').execute()
        predios_estruturados = len(predios_response.data) if predios_response.data else 0
        
        # Taxa de aprovação
        total_ftth = ftth_aprovadas + ftth_rejeitadas
        taxa_aprovacao = (ftth_aprovadas / total_ftth * 100) if total_ftth > 0 else 0
        
        return {
            'ftth_aprovadas': ftth_aprovadas,
            'ftth_rejeitadas': ftth_rejeitadas,
            'predios_estruturados': predios_estruturados,
            'pontos_sem_viabilidade': ftth_rejeitadas,
            'taxa_aprovacao_ftth': taxa_aprovacao
        }
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return {
            'ftth_aprovadas': 0,
            'ftth_rejeitadas': 0,
            'predios_estruturados': 0,
            'pontos_sem_viabilidade': 0,
            'taxa_aprovacao_ftth': 0
        }

def get_statistics() -> Dict:
    """Retorna estatísticas gerais do sistema"""
    try:
        response = supabase.table('viabilizacoes').select('status, urgente').execute()
        
        if not response.data:
            return {
                'total': 0,
                'pendentes': 0,
                'finalizadas': 0,
                'rejeitadas': 0,
                'utp': 0,
                'urgentes_pendentes': 0,
                'taxa_aprovacao': 0
            }
        
        data = response.data
        total = len(data)
        pendentes = len([d for d in data if d['status'] == 'pendente'])
        finalizadas = len([d for d in data if d['status'] == 'finalizado'])
        rejeitadas = len([d for d in data if d['status'] == 'rejeitado'])
        urgentes_pendentes = len([d for d in data if d['status'] == 'pendente' and d.get('urgente', False)])

        utp = total - (pendentes + finalizadas + rejeitadas)
        total_processadas = finalizadas + rejeitadas + utp
        taxa_aprovacao = (finalizadas / total_processadas * 100) if total_processadas > 0 else 0
        
        return {
            'total': total,
            'pendentes': pendentes,
            'finalizadas': finalizadas,
            'rejeitadas': rejeitadas,
            'utp': utp,
            'urgentes_pendentes': urgentes_pendentes,
            'taxa_aprovacao': taxa_aprovacao
        }
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return {
            'total': 0,
            'pendentes': 0,
            'finalizadas': 0,
            'rejeitadas': 0,
            'utp': 0,
            'urgentes_pendentes': 0,
            'taxa_aprovacao': 0
        }
