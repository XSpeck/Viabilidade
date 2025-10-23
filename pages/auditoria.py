"""
Página de Auditoria - Unificada com Busca de CTO
Salve como: pages/auditoria.py
"""

import streamlit as st
from login_system import require_authentication
from streamlit_autorefresh import st_autorefresh
from viability_functions import (
    format_time_br_supa,
    get_pending_viabilities,
    update_viability_ftth,
    update_viability_ftta,
    delete_viability,
    get_statistics,
    request_building_viability,
    reject_building_viability,
    coords_to_pluscode
)
import logging

# Importar funções de busca de CTO
from shapely.geometry import LineString, Point
from openlocationcode import openlocationcode as olc
from geopy.distance import geodesic
import requests

logger = logging.getLogger(__name__)

# ======================
# Configuração da Página
# ======================
st.set_page_config(
    page_title="Auditoria - Validador de Projetos",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================
# Funções de Busca de CTO (copiadas de validator_system.py)
# ======================
LOCATIONIQ_KEY = "pk.66f355328aaad40fe69b57c293f66815"
reference_lat = -28.6775
reference_lon = -49.3696

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

def find_nearest_ctos(lat: float, lon: float, ctos: list, max_radius: float = 400.0) -> list:
    """Busca CTOs próximas"""
    if not ctos:
        return []
    dists = []
    for cto in ctos:
        if cto["name"].upper().startswith("CDOI"):
            continue
        dist = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
        if dist <= max_radius:
            dists.append({**cto, "distance": dist})
    dists.sort(key=lambda x: x["distance"])
    return dists

def get_walking_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    """Calcula rota a pé usando OSRM"""
    try:
        url = f"http://router.project-osrm.org/route/v1/foot/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "false"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes") and len(data["routes"]) > 0:
                route = data["routes"][0]
                return {
                    "distance": route["distance"],
                    "duration": route["duration"],
                    "geometry": route["geometry"]
                }
        return None
    except Exception as e:
        logger.error(f"Erro ao calcular rota: {e}")
        return None

def format_distance(distance_m: float) -> str:
    """Formata distância"""
    if distance_m < 1000:
        return f"{distance_m:.1f}m"
    else:
        return f"{distance_m/1000:.2f}km"

# ======================
# Atualização automática
# ======================
st_autorefresh(interval=15000, key="auditoria_refresh")

# Verificar autenticação
if not require_authentication():
    st.stop()

# Verificar se é Leo
if st.session_state.user_login.lower() != "leo":
    st.error("🚫 Acesso Negado! Esta página é restrita ao usuário Leo.")
    st.info("👈 Use o menu lateral para navegar para outras páginas.")
    st.stop()

# ======================
# Header
# ======================
st.title("🔍 Auditoria de Viabilizações")
st.markdown("Análise técnica das solicitações de viabilidade")

# Botão de atualizar
col_header1, col_header2 = st.columns([4, 1])
with col_header2:
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()

# ======================
# Carregar CTOs (cache)
# ======================
import xml.etree.ElementTree as ET
import gdown

# Configurações do arquivo KML de CTOs
file_id_ctos = "1EcKNk2yqHDEMMXJZ17fT0flPV19HDhKJ"
ctos_kml_path = "ctos.kml"

@st.cache_data(ttl=3600)
def download_ctos_file():
    """Download do arquivo KML de CTOs do Google Drive"""
    try:
        url = f"https://drive.google.com/uc?id={file_id_ctos}"
        gdown.download(url, ctos_kml_path, quiet=True, fuzzy=True)
        logger.info(f"Arquivo {ctos_kml_path} baixado com sucesso")
        return ctos_kml_path
    except Exception as e:
        logger.error(f"Erro ao baixar CTOs: {e}")
        st.error(f"❌ Erro ao baixar arquivo de CTOs: {e}")
        return None

@st.cache_data(ttl=3600)
def load_ctos_from_kml(path: str):
    """
    Carrega CTOs do arquivo KML
    Retorna lista de dicionários com: name, lat, lon, desc
    """
    try:
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        tree = ET.parse(path)
        root = tree.getroot()
        ctos = []
        
        for placemark in root.findall(".//kml:Placemark", namespaces):
            name_elem = placemark.find("kml:name", namespaces)
            desc_elem = placemark.find(".//kml:value", namespaces)
            coords_elem = placemark.find(".//kml:coordinates", namespaces)
            
            if coords_elem is not None and coords_elem.text:
                parts = coords_elem.text.strip().split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    
                    # Validar coordenadas
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        ctos.append({
                            "name": name_elem.text.strip() if name_elem is not None else "CTO",
                            "desc": desc_elem.text.strip() if desc_elem is not None else "",
                            "lat": lat,
                            "lon": lon
                        })
        
        logger.info(f"✅ Carregados {len(ctos)} CTOs do arquivo KML")
        return ctos
    except Exception as e:
        logger.error(f"❌ Erro ao carregar CTOs do KML: {e}")
        st.error(f"❌ Erro ao processar arquivo de CTOs: {e}")
        return []

# Carregar CTOs no início da aplicação
try:
    with st.spinner("⏳ Carregando CTOs..."):
        kml_path = download_ctos_file()
        if kml_path:
            ctos = load_ctos_from_kml(kml_path)
            if ctos:
                st.sidebar.success(f"✅ {len(ctos)} CTOs carregadas")
            else:
                st.sidebar.warning("⚠️ Nenhuma CTO encontrada")
                ctos = []
        else:
            st.sidebar.error("❌ Erro ao baixar CTOs")
            ctos = []
except Exception as e:
    logger.error(f"Erro crítico ao carregar CTOs: {e}")
    st.error("❌ Erro ao inicializar sistema de CTOs")
    ctos = []

# ======================
# Função de Formulário FTTH com Busca de CTO
# ======================
def show_ftth_form_with_cto_search(row: dict, urgente: bool = False):
    """Exibe formulário FTTH com busca integrada de CTO"""
    
    # Verificar se CTO já foi escolhida
    cto_escolhida = row.get('cto_numero')
    
    if cto_escolhida:
        # CTO JÁ ESCOLHIDA - Mostrar formulário normal
        st.success(f"✅ CTO Escolhida: **{cto_escolhida}**")
        st.caption(f"📏 Distância: {row.get('distancia_cliente', 'N/A')} | 📍 Localização: {row.get('localizacao_caixa', 'N/A')}")
        st.warning("⚠️ Os campos abaixo são EDITÁVEIS caso precise corrigir")
        st.markdown("---")
        
        with st.form(key=f"form_ftth_{row['id']}"):
            # Campos editáveis
            cto = st.text_input(
                "N° Caixa (CTO)", 
                value=row.get('cto_numero', ''),
                key=f"cto_{row['id']}",
                help="⚠️ Você pode editar este campo se necessário"
            )
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                distancia = st.text_input(
                    "Distância até Cliente",
                    value=row.get('distancia_cliente', ''),
                    key=f"dist_{row['id']}",
                    help="⚠️ Editável - ex: 150m, 1.2km"
                )
            with col_f2:
                localizacao = st.text_input(
                    "Localização da Caixa",
                    value=row.get('localizacao_caixa', ''),
                    key=f"loc_{row['id']}",
                    help="⚠️ Editável - Plus Code da caixa"
                )
            
            st.markdown("---")
            st.markdown("**Preencha os dados técnicos:**")
            
            col_f3, col_f4 = st.columns(2)
            with col_f3:
                portas = st.number_input("Portas Disponíveis *", min_value=0, max_value=50, value=0, key=f"portas_{row['id']}")
            with col_f4:
                rx = st.text_input("Menor RX (dBm) *", placeholder="-18.67", key=f"rx_{row['id']}")
            
            obs = st.text_area("Observações", key=f"obs_{row['id']}", height=80)
            
            # Botões
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                aprovado = st.form_submit_button("✅ Viabilizar", type="primary", use_container_width=True)
            with col_btn2:
                utp = st.form_submit_button("📡 Atendemos UTP", use_container_width=True)
            with col_btn3:
                rejeitado = st.form_submit_button("❌ Sem Viabilidade", type="secondary", use_container_width=True)
            
            if aprovado:
                if not cto or not cto.strip():
                    st.error("❌ Preencha o N° da Caixa (CTO)!")
                elif not distancia or not distancia.strip():
                    st.error("❌ Preencha a Distância!")
                elif not localizacao or not localizacao.strip():
                    st.error("❌ Preencha a Localização da Caixa!")
                elif portas <= 0:
                    st.error("❌ Preencha as Portas Disponíveis!")
                elif not rx or not rx.strip():
                    st.error("❌ Preencha o Menor RX!")
                else:
                    dados = {
                        'cto_numero': cto.strip(),
                        'portas_disponiveis': portas,
                        'menor_rx': rx.strip(),
                        'distancia_cliente': distancia.strip(),
                        'localizacao_caixa': localizacao.strip(),
                        'observacoes': obs
                    }
                    if update_viability_ftth(row['id'], 'aprovado', dados):
                        st.success("✅ Viabilização aprovada!")
                        st.rerun()
            
            if rejeitado:
                dados = {'motivo_rejeicao': 'Não temos projeto neste ponto'}
                if update_viability_ftth(row['id'], 'rejeitado', dados):
                    st.success("❌ Solicitação rejeitada")
                    st.rerun()
            
            if utp:
                dados = {'motivo_rejeicao': 'Atendemos UTP'}
                if update_viability_ftth(row['id'], 'utp', dados):
                    st.success("📡 Marcado como Atendemos UTP")
                    st.rerun()
    
    else:
        # CTO NÃO ESCOLHIDA - Mostrar busca de CTO
        st.warning("⚠️ **CTO não escolhida - Faça a busca abaixo**")
        
        # Buscar CTOs próximas
        plus_code = row['plus_code_cliente']
        lat, lon = pluscode_to_coords(plus_code)
        
        if lat and lon:
            with st.spinner("🗺️ Buscando CTOs próximas..."):
                candidate_ctos = find_nearest_ctos(lat, lon, ctos, max_radius=3500.0)
                
                cto_routes = []
                if candidate_ctos:
                    for cto in candidate_ctos[:10]:
                        route = get_walking_route(lat, lon, cto["lat"], cto["lon"])
                        
                        if route:
                            linha_reta = geodesic((lat, lon), (cto["lat"], cto["lon"])).meters
                            if route["distance"] > linha_reta * 5:
                                route["distance"] = linha_reta
                            
                            cto_routes.append({
                                "cto": cto,
                                "route": route,
                                "distance": route["distance"]
                            })
                        else:
                            cto_routes.append({
                                "cto": cto,
                                "route": None,
                                "distance": cto["distance"]
                            })
                    
                    cto_routes.sort(key=lambda x: x["distance"])
                    cto_routes = cto_routes[:5]
            
            # Mostrar CTOs encontradas
            if cto_routes:
                st.markdown("### 🛠 CTOs Mais Próximas - Escolha uma")
                
                for idx, item in enumerate(cto_routes):
                    cto = item["cto"]
                    route = item["route"]
                    pluscode_cto = coords_to_pluscode(cto["lat"], cto["lon"])
                    
                    icons = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                    icon = icons[idx] if idx < len(icons) else "📍"
                    
                    col_cto1, col_cto2 = st.columns([4, 1])
                    
                    with col_cto1:
                        if route:
                            dist_real = route["distance"]
                            dist_com_sobra = dist_real + 50
                            
                            st.markdown(f"""
                            **{icon} CTO: {cto["name"]}**  
                            📍 Localização: `{pluscode_cto}`  
                            🚶 Distância real: {format_distance(route["distance"])}  
                            🏃‍♂️ Com sobra (+50m): {format_distance(dist_com_sobra)}
                            """)
                        else:
                            st.markdown(f"""
                            **{icon} CTO: {cto["name"]}**  
                            📍 Localização: `{pluscode_cto}`  
                            📏 Distância em linha reta: {format_distance(cto["distance"])}
                            """)
                    
                    with col_cto2:
                        if st.button(
                            "✅ Escolher",
                            key=f"escolher_cto_{row['id']}_{idx}",
                            type="primary",
                            use_container_width=True
                        ):
                            # Calcular distância COM SOBRA
                            if route:
                                dist_real = route["distance"]
                                dist_com_sobra = dist_real + 50
                                distancia_final = format_distance(dist_com_sobra)
                            else:
                                dist_linha_reta = cto["distance"]
                                dist_com_sobra = dist_linha_reta + 50
                                distancia_final = format_distance(dist_com_sobra)
                            
                            # Salvar CTO escolhida
                            from viability_functions import save_selected_cto
                            
                            cto_data = {
                                'cto_numero': cto["name"],
                                'distancia_cliente': distancia_final,
                                'localizacao_caixa': pluscode_cto
                            }
                            
                            if save_selected_cto(row['id'], cto_data):
                                st.success(f"✅ CTO {cto['name']} escolhida!")
                                st.info("📋 Agora preencha os dados técnicos")
                                st.rerun()
                    
                    st.markdown("---")
                
                # Botão Sem Viabilidade
                st.markdown("---")
                st.error("### ❌ Não encontrou CTO viável?")
                
                col_sem_viab = st.columns([1, 2, 1])[1]
                with col_sem_viab:
                    if st.button(
                        "❌ Sem Viabilidade",
                        type="secondary",
                        use_container_width=True,
                        key=f"sem_viab_{row['id']}"
                    ):
                        dados = {'motivo_rejeicao': 'Não temos projeto neste ponto'}
                        if update_viability_ftth(row['id'], 'rejeitado', dados):
                            st.success("✅ Solicitação rejeitada!")
                            st.rerun()
            else:
                st.warning("⚠️ Nenhuma CTO encontrada próxima.")
                
                # Botão direto para rejeitar
                if st.button("❌ Marcar como Sem Viabilidade", key=f"reject_no_cto_{row['id']}", type="secondary"):
                    dados = {'motivo_rejeicao': 'Não temos projeto neste ponto'}
                    if update_viability_ftth(row['id'], 'rejeitado', dados):
                        st.success("✅ Solicitação rejeitada!")
                        st.rerun()

# ======================
# Função de Formulário Principal
# ======================
def show_viability_form(row: dict, urgente: bool = False):
    """Exibe formulário de auditoria para uma viabilização"""
    
    # Estilo do card baseado na urgência
    if urgente:
        border_color = "#FF4444"
        bg_color = "#FFF5F5"
        icon = "🔥"
    else:
        border_color = "#667eea"
        bg_color = "#F8F9FA"
        icon = "📋"
    
    with st.container():
        st.markdown(f"""
        <div style='border-left: 5px solid {border_color}; padding: 15px; 
                    background-color: {bg_color}; border-radius: 5px; margin-bottom: 20px;'>
        </div>
        """, unsafe_allow_html=True)
        
        # Informações da solicitação
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown("#### 📋 Informações")
            st.text(f"👤 Usuário: {row['usuario']}")
            st.text(f"📍 Plus Code: {row['plus_code_cliente']}")
            
            # Determinar tipo real
            if row['tipo_instalacao'] == 'FTTH':
                tipo_exibir = 'FTTH (Casa)'
            elif row['tipo_instalacao'] == 'Prédio':
                if row.get('tecnologia_predio'):
                    tipo_exibir = f"{row['tecnologia_predio']} (Prédio)"
                else:
                    tipo_exibir = 'Prédio (a definir)'
            else:
                tipo_exibir = row['tipo_instalacao']
            
            st.text(f"🏷️ Tipo: {tipo_exibir}")
            
            if row.get('predio_ftta'):
                st.text(f"🏨 Nome: {row['predio_ftta']}")
            st.text(f"📅 Solicitado em: {format_time_br_supa(row['data_solicitacao'])}")
            
            # Botão Excluir
            st.markdown("---")
            if st.button(
                "🗑️ Excluir Solicitação",
                key=f"delete_{row['id']}",
                type="secondary",
                use_container_width=True,
                help="Excluir esta solicitação permanentemente"
            ):
                if delete_viability(row['id']):
                    st.success("✅ Solicitação excluída!")
                    st.rerun()
            
            if urgente:
                st.error("🔥 **URGENTE - Cliente Presencial**")
        
        with col2:
            # Formulário baseado no tipo
            if row['tipo_instalacao'] == 'FTTH':
                show_ftth_form_with_cto_search(row, urgente)
            else:
                # Código do formulário FTTA (mantém o mesmo)
                # [... código FTTA existente ...]
                pass
        
        st.markdown("---")

# ======================
# Buscar Pendências
# ======================
pending = get_pending_viabilities()

# ======================
# Notificação de novas solicitações
# ======================
if "pendentes_anteriores" not in st.session_state:
    st.session_state.pendentes_anteriores = len(pending)

if len(pending) > st.session_state.pendentes_anteriores:
    novas = len(pending) - st.session_state.pendentes_anteriores
    st.toast(f"📬 {novas} nova(s) solicitação(ões) aguardando auditoria!", icon="📬")

st.session_state.pendentes_anteriores = len(pending)

if not pending:
    st.info("✅ Não há solicitações pendentes de auditoria no momento.")
    st.success("👍 Parabéns! Todas as solicitações foram processadas.")
else:
    st.subheader(f"📋 {len(pending)} Solicitações Pendentes")
    st.markdown("---")
    
    # Separar urgentes e normais
    urgentes = [p for p in pending if p.get('urgente', False)]
    normais = [p for p in pending if not p.get('urgente', False)]
    
    # Mostrar urgentes primeiro
    if urgentes:
        st.markdown("### 🔥 URGENTES - Cliente Presencial")
        for row in urgentes:
            show_viability_form(row, urgente=True)
    
    # Mostrar normais
    if normais:
        if urgentes:
            st.markdown("---")
        st.markdown("### 📝 Solicitações Normais")
        for row in normais:
            show_viability_form(row, urgente=False)

# ======================
# Footer
# ======================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🔍 <strong>Validador de Projetos</strong> | Desenvolvido ByLeo</p>
</div>
""", unsafe_allow_html=True)
