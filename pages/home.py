"""
Página Home - Solicitação de Viabilização
Salve como: pages/home.py
"""

import streamlit as st
from login_system import require_authentication
from openlocationcode import openlocationcode as olc
import re
from viability_functions import create_viability_request
import logging

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Home - Validador de Projetos",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Verificar autenticação
if not require_authentication():
    st.stop()

# ======================
# Configurações
# ======================
reference_lat = -28.6775
reference_lon = -49.3696

# ======================
# Funções de Validação
# ======================
def validate_plus_code(plus_code: str) -> bool:
    """Valida formato de Plus Code"""
    pattern = r'^[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3}$'
    return bool(re.match(pattern, plus_code.upper().strip()))

def validate_coordinates(coord_string: str) -> tuple:
    """
    Valida e extrai coordenadas no formato: lat, lon
    Retorna: (valido: bool, lat: float, lon: float)
    """
    try:
        # Remover espaços extras
        coord_string = coord_string.strip()
        
        # Tentar separar por vírgula
        parts = coord_string.split(',')
        
        if len(parts) != 2:
            return (False, None, None)
        
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
        
        # Validar range
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return (True, lat, lon)
        else:
            return (False, None, None)
    except:
        return (False, None, None)

def coords_to_pluscode(lat: float, lon: float) -> str:
    """Converte coordenadas para Plus Code"""
    return olc.encode(lat, lon)

def pluscode_to_coords(pluscode: str) -> tuple:
    """Converte Plus Code para coordenadas"""
    try:
        pluscode = pluscode.strip().upper()
        if not olc.isFull(pluscode):
            pluscode = olc.recoverNearest(pluscode, reference_lat, reference_lon)
        decoded = olc.decode(pluscode)
        lat = (decoded.latitudeLo + decoded.latitudeHi) / 2
        lon = (decoded.longitudeLo + decoded.longitudeHi) / 2
        return (lat, lon)
    except Exception as e:
        logger.error(f"Erro ao converter Plus Code: {e}")
        return (None, None)

# ======================
# Funções de Busca de Prédios
# ======================
@st.cache_data(ttl=300)  # Cache de 5 minutos
def buscar_predios_cadastrados():
    """Busca todos os prédios cadastrados nas tabelas"""
    try:
        from supabase_config import supabase
        
        # Buscar prédios atendidos
        atendidos = supabase.table('utps_fttas_atendidos')\
            .select('condominio, tecnologia, observacao')\
            .execute()
        
        # Buscar prédios sem viabilidade
        sem_viab = supabase.table('predios_sem_viabilidade')\
            .select('condominio, observacao')\
            .execute()
        
        # Organizar dados
        predios_dict = {}
        
        # Adicionar atendidos
        if atendidos.data:
            for p in atendidos.data:
                nome_lower = p['condominio'].lower().strip()
                predios_dict[nome_lower] = {
                    'nome': p['condominio'],
                    'status': 'atendido',
                    'tecnologia': p.get('tecnologia', 'N/A'),
                    'observacao': p.get('observacao', '')
                }
        
        # Adicionar sem viabilidade
        if sem_viab.data:
            for p in sem_viab.data:
                nome_lower = p['condominio'].lower().strip()
                # Só adicionar se não estiver nos atendidos
                if nome_lower not in predios_dict:
                    predios_dict[nome_lower] = {
                        'nome': p['condominio'],
                        'status': 'sem_viabilidade',
                        'tecnologia': None,
                        'observacao': p.get('observacao', '')
                    }
        
        return predios_dict
    except Exception as e:
        logger.error(f"Erro ao buscar prédios cadastrados: {e}")
        return {}

def verificar_predio_existente(nome_digitado: str, predios_dict: dict):
    """
    Verifica se o prédio digitado já existe nos cadastros
    Retorna: (encontrado: bool, dados: dict)
    """
    if not nome_digitado or len(nome_digitado) < 3:
        return False, None
    
    nome_lower = nome_digitado.lower().strip()
    
    # Busca exata
    if nome_lower in predios_dict:
        return True, predios_dict[nome_lower]
    
    # Busca parcial (se digitou pelo menos 5 caracteres)
    if len(nome_digitado) >= 5:
        for predio_key, predio_data in predios_dict.items():
            if nome_lower in predio_key or predio_key in nome_lower:
                return True, predio_data
    
    return False, None

# ======================
# Header
# ======================
st.title("🏠 Solicitar Viabilização")
st.markdown(f"Bem-vindo, **{st.session_state.user_name}**!")


# ======================
# Instruções
# ======================
with st.expander("❓Como solicitar uma viabilização?", expanded=False):
    st.markdown("""
    1. **Insira a localização** usando:
       - Plus Code (ex: `8J3G+WGV`)
       - Coordenadas (ex: `-28.695133, -49.373710`)
    
    2. **Clique em Viabilizar**
    
    3. **Escolha o tipo** de instalação (FTTH ou FTTA/UTP)
    
    4. **Aguarde** a análise técnica
    """)
    


# ======================
# Input de Localização
# ======================
st.subheader("📍 Localização do Cliente")

input_method = st.radio(
    "Escolha o método de entrada:",
    options=["Plus Code", "Coordenadas"],
    horizontal=True,
    key="input_method"
)

if input_method == "Plus Code":
    location_input = st.text_input(
        "Digite o Plus Code",
        placeholder="Ex: 8J3G+WGV ou 589G8J3G+WGV",
        help="Plus Code é um sistema de endereçamento do Google",
        key="plus_code_input"
    ).strip().upper()
    
    if location_input:
        if validate_plus_code(location_input):
            st.success("✅ Plus Code válido!")
            
            # Converter para coordenadas para exibir
            lat, lon = pluscode_to_coords(location_input)
            if lat and lon:
                st.caption(f"📍 Coordenadas: {lat:.6f}, {lon:.6f}")
                
                # Salvar na sessão
                st.session_state.validated_pluscode = location_input
                st.session_state.validated_lat = lat
                st.session_state.validated_lon = lon
        else:
            st.error("❌ Plus Code inválido! Use o formato correto (ex: 8J3G+WGV)")
            st.session_state.validated_pluscode = None

else:  # Coordenadas
    location_input = st.text_input(
        "Digite as Coordenadas",
        placeholder="Ex: -28.695133, -49.373710",
        help="Formato: latitude, longitude (separado por vírgula)",
        key="coords_input"
    ).strip()
    
    if location_input:
        valid, lat, lon = validate_coordinates(location_input)
        
        if valid:
            st.success("✅ Coordenadas válidas!")
            
            # Converter para Plus Code
            pluscode = coords_to_pluscode(lat, lon)
            st.caption(f"📍 Plus Code equivalente: {pluscode}")
            
            # Salvar na sessão
            st.session_state.validated_pluscode = pluscode
            st.session_state.validated_lat = lat
            st.session_state.validated_lon = lon
        else:
            st.error("❌ Coordenadas inválidas! Use o formato: -28.695133, -49.373710")
            st.session_state.validated_pluscode = None

st.markdown("---")

# ======================
# Botão Viabilizar
# ======================
if st.session_state.get('validated_pluscode'):
    
    col_viab = st.columns([1, 2, 1])[1]
    with col_viab:
        if st.button("🎯 Viabilizar Esta Localização", type="primary", use_container_width=True):
            st.session_state.show_viability_modal = True

    # ===== MENSAGEM DE SUCESSO APÓS CONFIRMAR ===== ← ADICIONAR AQUI
    if st.session_state.get('show_success_message', False):
        tipo = st.session_state.get('success_message_type', '')
        st.success(f"✅ Solicitação de {tipo} enviada com sucesso!")
        st.info("📋 **Acompanhe o andamento em 'Meus Resultados' no menu lateral**")
        
        # Limpar mensagem após exibir
        st.session_state.show_success_message = False

    # ======================
    # Modal de Seleção
    # ======================
    if st.session_state.get('show_viability_modal', False):
        
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 10px; margin: 20px 0;'>
            <h3 style='color: white; text-align: center; margin: 0;'>
                🏠 Qual o tipo de instalação?
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        col_modal1, col_modal2 = st.columns(2)
        
        # ===== FTTH (Casa) =====
        with col_modal1:
            st.markdown("""
            <div style='text-align: center; padding: 20px; background: white; 
                        border-radius: 10px; border: 2px solid #4CAF50;'>
                <h2 style='margin: 0;'>🏠</h2>                                        
                <p style='color: #666; margin: 0;'>FTTH - Fibra até a casa</p>
            </div>
            """, unsafe_allow_html=True)
            
            # ========================================
            # Campo Nome do Cliente (FTTH)
            # ========================================
            nome_cliente_ftth = st.text_input(
                "👤 Nome do Cliente *",
                placeholder="Nome do cliente",
                key="nome_cliente_ftth",
                help="Nome de quem solicitou a viabilização"
            )
            
            urgente_casa = st.checkbox("🔥 Cliente Presencial (Urgente)", key="urgente_casa")
            
            if st.button("Confirmar - Casa (FTTH)", type="primary", use_container_width=True, key="confirm_ftth"):
                # Validar nome do cliente
                if not nome_cliente_ftth or not nome_cliente_ftth.strip():
                    st.error("❌ Por favor, informe o nome do cliente!")
                else:
                    if create_viability_request(
                        st.session_state.user_name, 
                        st.session_state.validated_pluscode, 
                        'FTTH',
                        urgente_casa,
                        nome_cliente=nome_cliente_ftth.strip()
                    ):
                        st.session_state.show_viability_modal = False
                        st.session_state.show_success_message = True  
                        st.session_state.success_message_type = 'FTTH' 
                        # Limpar dados
                        st.session_state.validated_pluscode = None
                        st.rerun()
                    else:
                        st.error("❌ Erro ao criar solicitação. Tente novamente.")
        
        # ===== FTTA (Edifício) =====
        with col_modal2:
            st.markdown("""
            <div style='text-align: center; padding: 20px; background: white; 
                        border-radius: 10px; border: 2px solid #2196F3;'>
                <h2 style='margin: 0;'>🏢</h2>                                       
                <p style='color: #666; margin: 0;'>Prédio/Edifício</p>
            </div>
            """, unsafe_allow_html=True)
            
            # ========================================
            # Campo Nome do Cliente (Prédio)
            # ========================================
            nome_cliente_predio = st.text_input(
                "👤 Nome do Cliente *",
                placeholder="Nome do cliente",
                key="nome_cliente_predio_input",
                help="Nome de quem solicitou a viabilização"
            )

            nome_predio = st.text_input(
                "🏢 Nome do Prédio *",
                placeholder="Ex: Ed. Solar das Flores",
                key="nome_predio_ftta",
                help="Digite o nome do prédio - verificaremos se já atendemos"
            )

            # Verificação em tempo real
            if nome_predio and len(nome_predio) >= 3:               
                with st.spinner("🔍 Verificando cadastro..."):
                    predios_cadastrados = buscar_predios_cadastrados()
                    encontrado, dados_predio = verificar_predio_existente(nome_predio, predios_cadastrados)            
                    
                    if encontrado:
                        status = dados_predio['status']
                        
                        # ===== PRÉDIO ATENDIDO =====
                        if status == 'atendido':
                            tecnologia = dados_predio['tecnologia']
                            
                            if tecnologia == 'FTTA':
                                st.caption(f"🏢 **{dados_predio['nome']}**")
                                st.info("⚡ **Atendemos FTTA neste prédio!**")
                                                                
                                if dados_predio.get('observacao'):
                                    with st.expander("📋 Detalhes"):
                                        st.text(dados_predio['observacao'])                                
                            
                            elif tecnologia == 'UTP':
                                st.caption(f"🏢 **{dados_predio['nome']}**")
                                st.info("📡 **Atendemos UTP neste prédio**")                                
                                
                                if dados_predio.get('observacao'):
                                    with st.expander("📋 Detalhes"):
                                        st.text(dados_predio['observacao'])                                
                            
                            else:
                                st.caption(f"🏢 **{dados_predio['nome']}**")
                                st.info(f"✅ **Prédio estruturado ({tecnologia})**")

                                if dados_predio.get('observacao'):
                                    with st.expander("📋 Detalhes"):
                                        st.text(dados_predio['observacao'])
                                
                        
                        # ===== PRÉDIO SEM VIABILIDADE =====
                        else:
                            st.caption(f"🏢 **{dados_predio['nome']}**")
                            st.error("❌ **Prédio Sem Viabilidade**")                            
                            
                            if dados_predio.get('observacao'):
                                with st.expander("📝 Motivo da Não Viabilidade"):
                                    st.warning(dados_predio['observacao'])                            
                            
                    else:
                        # Nenhum registro encontrado
                        if len(nome_predio) >= 5:
                            st.success("🆕 **Prédio novo** - Prossiga com a solicitação")
            
            # ========================================
            # FIM DA VERIFICAÇÃO
            # ========================================
            
            urgente_edificio = st.checkbox("🔥 Cliente Presencial (Urgente)", key="urgente_edificio")
            
            if st.button("Confirmar - Edifício", type="primary", use_container_width=True, key="confirm_ftta"):
                # Validar campos
                if not nome_cliente_predio or not nome_cliente_predio.strip():
                    st.error("❌ Por favor, informe o nome do cliente!")
                elif not nome_predio or not nome_predio.strip():
                    st.error("❌ Por favor, informe o nome do prédio!")
                else:
                    if create_viability_request(
                        st.session_state.user_name, 
                        st.session_state.validated_pluscode, 
                        'Prédio',
                        urgente_edificio,
                        nome_predio=nome_predio.strip(),
                        nome_cliente=nome_cliente_predio.strip()
                    ):
                        st.session_state.show_viability_modal = False
                        st.session_state.show_success_message = True
                        st.session_state.success_message_type = 'Prédio' 
                        # Limpar dados
                        st.session_state.validated_pluscode = None
                        st.rerun()
                    else:
                        st.error("❌ Erro ao criar solicitação. Tente novamente.")
        
        # ===== Botão Cancelar =====
        col_cancel = st.columns([2, 1, 2])[1]
        with col_cancel:
            if st.button("❌ Cancelar", use_container_width=True, key="cancel_viability"):
                st.session_state.show_viability_modal = False
                st.rerun()

else:
    st.info("👆 Insira uma localização válida acima para solicitar viabilização")

# ======================
# Tabelas de Consulta
# ======================
st.markdown("---")
st.markdown("## 📊 Consulta de Prédios")

tab1, tab2 = st.tabs(["✅ Prédios Atendidos", "❌ Prédios Sem Viabilidade"])

# ===== TAB 1: Prédios Atendidos =====
with tab1:
    st.markdown("### 🏢 Prédios com Estrutura Instalada")
    
    from viability_functions import get_structured_buildings
    predios_atendidos = get_structured_buildings()
    
    if not predios_atendidos:
        st.info("📭 Nenhum prédio estruturado ainda.")
    else:
        # Busca
        search_atendidos = st.text_input(
            "🔍 Buscar Prédio Atendido",
            placeholder="Digite o nome do condomínio...",
            key="search_atendidos"
        )
        
        # Converter para DataFrame
        import pandas as pd
        df_atendidos = pd.DataFrame(predios_atendidos)
        
        # Filtrar
        if search_atendidos:
            termo_busca = re.escape(search_atendidos.lower().replace("+", "").strip())
            mask = df_atendidos.astype(str).apply(
               # lambda x: x.str.lower().str.contains(search_atendidos.lower(), na=False)
                lambda x: x.str.lower().str.replace("+", "", regex=False).str.contains(termo_busca, regex=True, na=False)
            ).any(axis=1)
            df_atendidos = df_atendidos[mask]
        
        # Selecionar e renomear colunas
        df_display = df_atendidos[['condominio', 'tecnologia', 'localizacao', 'observacao']].copy()
        df_display.columns = ['Condomínio', 'Tecnologia', 'Localização', 'Observação']
        
        st.dataframe(df_display, use_container_width=True, height=400)
        st.caption(f"Mostrando {len(df_display)} de {len(predios_atendidos)} registros")

# ===== TAB 2: Prédios Sem Viabilidade =====
with tab2:
    st.markdown("### 🚫 Prédios Sem Viabilidade")
    
    from viability_functions import get_buildings_without_viability
    predios_sem_viab = get_buildings_without_viability()
    
    if not predios_sem_viab:
        st.info("📭 Nenhum prédio registrado como sem viabilidade.")
    else:
        # Busca
        search_sem_viab = st.text_input(
            "🔍 Buscar Prédio Sem Viabilidade",
            placeholder="Digite o nome do condomínio...",
            key="search_sem_viab"
        )
        
        # Converter para DataFrame
        import pandas as pd
        df_sem_viab = pd.DataFrame(predios_sem_viab)
        
        # Filtrar
        if search_sem_viab:
            termo_busca = re.escape(search_sem_viab.lower().replace("+", "").strip())
            mask = df_sem_viab.astype(str).apply(
                lambda x: x.str.lower().str.replace("+", "", regex=False).str.contains(termo_busca, regex=True, na=False)                
            ).any(axis=1)
            df_sem_viab = df_sem_viab[mask]
        
        # Selecionar e renomear colunas
        df_display = df_sem_viab[['condominio', 'localizacao', 'observacao']].copy()
        df_display.columns = ['Condomínio', 'Localização', 'Observação']
        
        st.dataframe(df_display, use_container_width=True, height=400)
        st.caption(f"Mostrando {len(df_display)} de {len(predios_sem_viab)} registros")

st.markdown("---")
# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🏠 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
