"""
Funções compartilhadas para o sistema de viabilização
Salve como: viability_functions.py
"""

import streamlit as st
import logging
from datetime import datetime
from typing import Dict, List, Optional
from supabase_config import supabase
import pytz

logger = logging.getLogger(__name__)

TIMEZONE_BR = pytz.timezone('America/Sao_Paulo')  # Brasília (UTC-3)
# ======================
# Funções de CRUD
# ======================

def get_current_time():
    """Retorna data/hora atual no fuso horário do Brasil"""
    return datetime.now(TIMEZONE_BR).isoformat()

def create_viability_request(user_name: str, plus_code: str, tipo: str, urgente: bool = False, nome_predio: str = None) -> bool:
    """
    Cria nova solicitação de viabilização no Supabase
    
    Args:
        user_name: Nome do usuário solicitante
        plus_code: Plus Code do cliente
        tipo: 'FTTH' ou 'FTTA'
        urgente: Se é cliente presencial (urgente)
        nome_predio: Nome do prédio (apenas para FTTA)
    """
    try:
        new_request = {
            'usuario': user_name,
            'plus_code_cliente': plus_code,
            'tipo_instalacao': tipo,
            'urgente': urgente,
            'status': 'pendente'
        }

        # Adicionar nome do prédio se for FTTA
        if tipo == 'FTTA' and nome_predio:
            new_request['predio_ftta'] = nome_predio
            
        response = supabase.table('viabilizacoes').insert(new_request).execute()
        
        if response.data:
            logger.info(f"Viabilização criada: {user_name} - {plus_code} - Tipo: {tipo} - Urgente: {urgente}")
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
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar pendentes: {e}")
        return []

def get_user_results(username: str) -> List[Dict]:
    """Busca resultados do usuário (aprovados e rejeitados e UTPs que ainda não foram finalizados)"""
    try:
        response = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('usuario', username)\
            .in_('status', ['aprovado', 'rejeitado', 'utp'])\
            .is_('data_finalizacao', None)\
            .order('data_auditoria', desc=True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Erro ao buscar resultados: {e}")
        return []

def get_archived_viabilities() -> Dict[str, List[Dict]]:
    """Busca viabilizações finalizadas e rejeitadas para o arquivo"""
    try:
        finalizadas = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'finalizado')\
            .order('data_finalizacao', desc=True)\
            .execute()
        
        rejeitadas = supabase.table('viabilizacoes')\
            .select('*')\
            .eq('status', 'rejeitado')\
            .order('data_auditoria', desc=True)\
            .execute()
        
        return {
            'finalizadas': finalizadas.data if finalizadas.data else [],
            'rejeitadas': rejeitadas.data if rejeitadas.data else []
        }
    except Exception as e:
        logger.error(f"Erro ao buscar arquivo: {e}")
        return {'finalizadas': [], 'rejeitadas': []}

def update_viability_ftth(viability_id: str, status: str, dados: Dict) -> bool:
    """
    Atualiza viabilização FTTH (casa)
    
    Args:
        viability_id: ID da viabilização
        status: 'aprovado' ou 'rejeitado'
        dados: Dicionário com os dados FTTH
    """
    try:
        update_data = {
            'status': status,
            'data_auditoria': get_current_time().isoformat(),
            'auditado_por': 'leo'
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

def update_viability_ftta(viability_id: str, status: str, dados: Dict) -> bool:
    """
    Atualiza viabilização FTTA (edifício)
    
    Args:
        viability_id: ID da viabilização
        status: 'aprovado' ou 'rejeitado'
        dados: Dicionário com os dados FTTA
    """
    try:
        update_data = {
            'status': status,
            'data_auditoria': get_current_time().isoformat(),
            'auditado_por': 'leo'
        }
        
        if status == 'aprovado':
            update_data.update({
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
            
            'data_finalizacao': get_current_time().isoformat()
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
            'data_finalizacao': get_current_time().isoformat()
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

def delete_viability(viability_id: str) -> bool:
    """Deleta uma viabilização (somente Leo)"""
    try:
        response = supabase.table('viabilizacoes').delete().eq('id', viability_id).execute()
        
        if response.data or response.status_code == 204:
            logger.info(f"Viabilização {viability_id} deletada")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao deletar viabilização: {e}")
        st.error(f"❌ Erro ao deletar: {e}")
        return False

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
