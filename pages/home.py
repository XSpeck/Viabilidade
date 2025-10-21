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
# Header
# ======================
st.title("🏠 Solicitar Viabilização")
st.markdown(f"Bem-vindo, **{st.session_state.user_name}**!")
st.markdown("---")

# ======================
# Instruções
# ======================
st.markdown("""
### 📍 Como solicitar uma viabilização?

1. **Insira a localização** usando:
   - Plus Code (ex: `8J3G+WGV`)
   - Coordenadas (ex: `-28.695133, -49.373710`)

2. **Clique em Viabilizar**

3. **Escolha o tipo** de instalação (FTTH ou FTTA/UTP)

4. **Aguarde** a análise técnica
""")

st.markdown("---")

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
            
            urgente_casa = st.checkbox("🔥 Cliente Presencial (Urgente)", key="urgente_casa")
            
            if st.button("Confirmar - Casa (FTTH)", type="primary", use_container_width=True, key="confirm_ftth"):
                if create_viability_request(
                    st.session_state.user_name, 
                    st.session_state.validated_pluscode, 
                    'FTTH',
                    urgente_casa
                ):
                    st.session_state.show_viability_modal = False
                    st.session_state.show_success_message = True  # ← ADICIONAR
                    st.session_state.success_message_type = 'FTTH'  # ← ADICIONAR
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

            nome_predio = st.text_input(
                "🏢 Nome do Prédio *",
                placeholder="Ex: Ed. Solar das Flores",
                key="nome_predio_ftta"
            )
            
            urgente_edificio = st.checkbox("🔥 Cliente Presencial (Urgente)", key="urgente_edificio")
            
            if st.button("Confirmar - Edifício", type="primary", use_container_width=True, key="confirm_ftta"):
                if not nome_predio or nome_predio.strip() == "":
                    st.error("❌ Por favor, informe o nome do prédio!")
                else:
                    if create_viability_request(
                        st.session_state.user_name, 
                        st.session_state.validated_pluscode, 
                        'Prédio',
                        urgente_edificio,
                        nome_predio=nome_predio.strip()
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
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🏠 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
