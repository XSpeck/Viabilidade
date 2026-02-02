"""
Página Home - Solicitação de Viabilização
Salve como: pages/home.py
"""

import streamlit as st
from login_system import require_authentication
from openlocationcode import openlocationcode as olc
import re
import pandas as pd
from viability_functions import create_viability_request, validate_plus_code
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
    except (ValueError, AttributeError, TypeError):
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
# Funcoes de Busca de Predios (Inteligente)
# ======================
import unicodedata
from difflib import SequenceMatcher

def normalizar_nome(nome: str) -> str:
    """
    Normaliza nome do predio removendo acentos e prefixos comuns
    'Ed. São José' -> 'sao jose'
    'Residencial Flores' -> 'flores'
    """
    if not nome:
        return ""

    # Converter para minusculas
    nome = nome.lower().strip()

    # Remover acentos
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nome if not unicodedata.combining(c))

    # Prefixos comuns para remover
    prefixos = [
        'edificio ', 'edifício ', 'ed. ', 'ed ',
        'residencial ', 'res. ', 'res ',
        'condominio ', 'condomínio ', 'cond. ', 'cond ',
        'conjunto ', 'conj. ', 'conj ',
        'bloco ', 'bl. ', 'bl ',
        'torre ', 'tr. ', 'tr ',
        'predio ', 'prédio '
    ]

    for prefixo in prefixos:
        if nome.startswith(prefixo):
            nome = nome[len(prefixo):]
            break

    return nome.strip()

def calcular_similaridade(nome1: str, nome2: str) -> float:
    """Calcula similaridade entre dois nomes (0.0 a 1.0)"""
    return SequenceMatcher(None, nome1, nome2).ratio()

@st.cache_data(ttl=300)  # Cache de 5 minutos
def buscar_predios_cadastrados():
    """Busca todos os predios cadastrados nas tabelas"""
    try:
        from supabase_config import supabase

        # Buscar predios atendidos
        atendidos = supabase.table('utps_fttas_atendidos')\
            .select('condominio, tecnologia, observacao')\
            .execute()

        # Buscar predios sem viabilidade
        sem_viab = supabase.table('predios_sem_viabilidade')\
            .select('condominio, observacao')\
            .execute()

        # Organizar dados
        predios_list = []
        nomes_adicionados = set()

        # Adicionar atendidos
        if atendidos.data:
            for p in atendidos.data:
                if not p.get('condominio'):
                    continue
                nome = p['condominio'].strip()
                nome_normalizado = normalizar_nome(nome)

                if nome_normalizado not in nomes_adicionados:
                    predios_list.append({
                        'nome': nome,
                        'nome_normalizado': nome_normalizado,
                        'status': 'atendido',
                        'tecnologia': p.get('tecnologia', 'N/A'),
                        'observacao': p.get('observacao', '')
                    })
                    nomes_adicionados.add(nome_normalizado)

        # Adicionar sem viabilidade
        if sem_viab.data:
            for p in sem_viab.data:
                if not p.get('condominio'):
                    continue
                nome = p['condominio'].strip()
                nome_normalizado = normalizar_nome(nome)

                # So adicionar se nao estiver nos atendidos
                if nome_normalizado not in nomes_adicionados:
                    predios_list.append({
                        'nome': nome,
                        'nome_normalizado': nome_normalizado,
                        'status': 'sem_viabilidade',
                        'tecnologia': None,
                        'observacao': p.get('observacao', '')
                    })
                    nomes_adicionados.add(nome_normalizado)

        return predios_list
    except Exception as e:
        logger.error(f"Erro ao buscar predios cadastrados: {e}")
        return []

def buscar_predios_similares(nome_digitado: str, predios_list: list, limite: int = 5) -> list:
    """
    Busca predios similares ao nome digitado
    Retorna lista de predios ordenados por relevancia
    """
    if not nome_digitado or len(nome_digitado) < 2:
        return []

    nome_normalizado = normalizar_nome(nome_digitado)

    if len(nome_normalizado) < 2:
        return []

    resultados = []

    for predio in predios_list:
        predio_norm = predio['nome_normalizado']

        # Calcular pontuacao de relevancia
        pontuacao = 0.0

        # 1. Match exato (normalizado)
        if nome_normalizado == predio_norm:
            pontuacao = 1.0

        # 2. Nome digitado contem o predio ou vice-versa
        elif nome_normalizado in predio_norm:
            pontuacao = 0.9
        elif predio_norm in nome_normalizado:
            pontuacao = 0.85

        # 3. Comeca com o texto digitado
        elif predio_norm.startswith(nome_normalizado):
            pontuacao = 0.8

        # 4. Alguma palavra do predio comeca com o texto
        elif any(palavra.startswith(nome_normalizado) for palavra in predio_norm.split()):
            pontuacao = 0.7

        # 5. Similaridade fuzzy (para erros de digitacao)
        else:
            similaridade = calcular_similaridade(nome_normalizado, predio_norm)
            if similaridade >= 0.5:  # Minimo 50% de similaridade
                pontuacao = similaridade * 0.6  # Maximo 0.6 para fuzzy

        if pontuacao > 0:
            resultados.append({
                **predio,
                'pontuacao': pontuacao
            })

    # Ordenar por pontuacao (maior primeiro)
    resultados.sort(key=lambda x: x['pontuacao'], reverse=True)

    return resultados[:limite]

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
            if lat is not None and lon is not None:
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
        if st.button("🎯 Viabilizar Esta Localização", type="primary", width='stretch'):
            st.session_state.show_viability_modal = True

    # ===== MENSAGEM DE SUCESSO APÓS CONFIRMAR =====
    if st.session_state.get('show_success_message', False):
        tipo = st.session_state.get('success_message_type', '')
        st.success(f"✅ Solicitação de {tipo} enviada com sucesso!")
        st.info("📋 **Acompanhe o andamento em 'Meus Resultados' no menu lateral**")

        # Botão para limpar mensagem e fazer nova solicitação
        if st.button("🔄 Nova Solicitação", key="clear_success"):
            st.session_state.show_success_message = False
            st.rerun()

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
            
            if st.button("Confirmar - Casa (FTTH)", type="primary", width='stretch', key="confirm_ftth"):
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

            col_apt1, col_apt2 = st.columns(2)
    
            with col_apt1:
                andar_predio = st.text_input(
                    "🏗️ Andar *",
                    placeholder="Ex: 3º, Térreo",
                    key="andar_predio_input",
                    help="Em qual andar o cliente mora"
                )
            
            with col_apt2:
                bloco_predio = st.text_input(
                    "🏢 Bloco (se houver)",
                    placeholder="Ex: A, B, Torre 1",
                    key="bloco_predio_input",
                    help="Deixe vazio se não houver blocos"
                )
                
            # Verificacao em tempo real (busca inteligente)
            if nome_predio and len(nome_predio) >= 3:
                predios_cadastrados = buscar_predios_cadastrados()
                resultados = buscar_predios_similares(nome_predio, predios_cadastrados, limite=5)

                if resultados:
                    # Verificar se tem match muito forte (>= 0.85)
                    melhor_match = resultados[0]

                    if melhor_match['pontuacao'] >= 0.85:
                        # Match forte - mostrar direto
                        dados_predio = melhor_match
                        status = dados_predio['status']

                        if status == 'atendido':
                            tecnologia = dados_predio['tecnologia']

                            if tecnologia == 'FTTA':
                                st.success(f"✅ **{dados_predio['nome']}** - Atendemos FTTA!")
                            elif tecnologia == 'UTP':
                                st.info(f"📡 **{dados_predio['nome']}** - Atendemos UTP")
                            else:
                                st.success(f"✅ **{dados_predio['nome']}** - Estruturado ({tecnologia})")

                            if dados_predio.get('observacao'):
                                with st.expander("📋 Detalhes"):
                                    st.text(dados_predio['observacao'])
                        else:
                            # Sem viabilidade
                            st.error(f"❌ **{dados_predio['nome']}** - Sem Viabilidade")

                            if dados_predio.get('observacao'):
                                with st.expander("📝 Motivo"):
                                    st.warning(dados_predio['observacao'])

                    else:
                        # Match parcial - mostrar sugestoes
                        st.markdown("**🔍 Predios encontrados:**")

                        for i, predio in enumerate(resultados):
                            status = predio['status']
                            nome = predio['nome']

                            if status == 'atendido':
                                tec = predio.get('tecnologia', 'N/A')
                                if tec == 'FTTA':
                                    st.markdown(f"- ✅ **{nome}** _(FTTA)_")
                                elif tec == 'UTP':
                                    st.markdown(f"- 📡 **{nome}** _(UTP)_")
                                else:
                                    st.markdown(f"- ✅ **{nome}** _({tec})_")
                            else:
                                st.markdown(f"- ❌ **{nome}** _(Sem viabilidade)_")

                        st.caption("💡 Se nenhum corresponde, continue com a solicitacao")

                else:
                    # Nenhum resultado encontrado
                    if len(nome_predio) >= 4:
                        st.success("🆕 **Predio novo** - Nao encontramos no cadastro")
            
            # ========================================
            # FIM DA VERIFICAÇÃO
            # ========================================
            
            urgente_edificio = st.checkbox("🔥 Cliente Presencial (Urgente)", key="urgente_edificio")
            
            if st.button("Confirmar - Edifício", type="primary", width='stretch', key="confirm_ftta"):
                # Validar campos
                if not nome_cliente_predio or not nome_cliente_predio.strip():
                    st.error("❌ Por favor, informe o nome do cliente!")
                elif not nome_predio or not nome_predio.strip():
                    st.error("❌ Por favor, informe o nome do prédio!")
                elif not andar_predio or not andar_predio.strip():
                    st.error("❌ Por favor, informe o andar!")
                else:
                    dados_predio_completo = {
                        'nome_predio': nome_predio.strip(),
                        'andar': andar_predio.strip(),
                        'bloco': bloco_predio.strip() if bloco_predio else None
                    }
                    
                    if create_viability_request(
                        st.session_state.user_name, 
                        st.session_state.validated_pluscode, 
                        'Prédio',
                        urgente_edificio,
                        nome_predio=nome_predio.strip(),
                        nome_cliente=nome_cliente_predio.strip(),
                        andar=andar_predio.strip(),
                        bloco=bloco_predio.strip() if bloco_predio else None 
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
            if st.button("❌ Cancelar", width='stretch', key="cancel_viability"):
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
        
        st.dataframe(df_display, width='stretch', height=400)
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
        
        st.dataframe(df_display, width='stretch', height=400)
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
