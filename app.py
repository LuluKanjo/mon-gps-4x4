import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import streamlit_js_eval
import requests
import urllib.parse
from geopy.distance import geodesic

st.set_page_config(page_title="4x4 Expedition Master", layout="wide", initial_sidebar_state="collapsed")

# --- INITIALISATION ---
if 'trace' not in st.session_state: st.session_state['trace'] = []
if 'total_dist' not in st.session_state: st.session_state['total_dist'] = 0.0

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("🛠️ Configuration")
    dist_km = st.slider("Rayon de scan (km)", 2, 8, 3)
    mode_eco = st.toggle("🍃 Mode Économie (Carte simple)", value=False)
    num_sos = st.text_input("Numéro SOS (+33...)", "")
    st.divider()
    if st.button("🗑️ Effacer la trace rouge"):
        st.session_state['trace'] = []
        st.session_state['total_dist'] = 0.0
        st.rerun()

# --- RÉCUPÉRATION GPS ---
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps_v6')

# --- FONCTION DE RÉCUPÉRATION "TURBO" ---
@st.cache_data(ttl=600)
def fetch_pistes_turbo(lat, lon, dist_m):
    # On utilise le format "geom" qui est beaucoup plus léger et rapide que le format standard
    url = "https://overpass-api.de/api/interpreter"
    query = f"""[out:json][timeout:25];
    way["highway"="track"]["motor_vehicle"!~"no|private"](around:{dist_m},{lat},{lon});
    out geom;""" # "out geom" réduit la taille du fichier par 3
    
    headers = {'User-Agent': 'Expedition-4x4-Pro-Fast/2.0'}
    try:
        r = requests.get(url, params={'data': query}, headers=headers, timeout=15)
        if r.status_code == 200: return r.json()
        return None
    except: return None

st.title("🚜 4x4 Adventure Dash")

if loc or st.session_state.get('manual_mode'):
    lat, lon = (loc['lat'], loc['lon']) if loc else (43.5578, 3.7188)
    
    # Enregistrement trace
    if loc and st.session_state.get('recording', True):
        if not st.session_state['trace'] or st.session_state['trace'][-1] != (lat, lon):
            if st.session_state['trace']:
                st.session_state['total_dist'] += geodesic(st.session_state['trace'][-1], (lat, lon)).km
            st.session_state['trace'].append((lat, lon))

    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Altitude", f"{int(loc.get('alt', 50)) if loc else 50} m")
    c2.metric("Vitesse", f"{int((loc.get('speed', 0) or 0)*3.6) if loc else 0} km/h")
    c3.metric("Parcouru", f"{st.session_state['total_dist']:.2f} km")

    # SOS
    if num_sos:
        msg = urllib.parse.quote(f"SOS 4x4 ! Position : http://maps.google.com/maps?q={lat},{lon}")
        st.markdown(f'<a href="sms:{num_sos}?body={msg}"><button style="width:100%; background-color:#ff4b4b; color:white; border:none; padding:15px; border-radius:10px; font-weight:bold; cursor:pointer; margin-bottom:20px;">🚨 SOS SMS</button></a>', unsafe_allow_html=True)

    # Carte
    if st.button(f"🗺️ SCANNER LA ZONE ({dist_km} KM)"):
        with st.spinner("Récupération ultra-rapide..."):
            m = folium.Map(location=[lat, lon], zoom_start=14)
            
            # Mode Économie : Satellite ou Plan
            if mode_eco:
                folium.TileLayer('OpenStreetMap', name='Plan Éco').add_to(m)
            else:
                folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)
            
            data = fetch_pistes_turbo(lat, lon, dist_km * 1000)
            
            if data and 'elements' in data:
                for el in data['elements']:
                    if 'geometry' in el:
                        coords = [(pt['lat'], pt['lon']) for pt in el['geometry']]
                        folium.PolyLine(coords, color="#CCFF00", weight=5, opacity=0.9).add_to(m)
                st.success(f"Pistes affichées sur {dist_km} km")
            else:
                st.error("Serveur saturé. Réessayez dans 10 secondes avec un rayon de 3km.")

            if st.session_state['trace']:
                folium.PolyLine(st.session_state['trace'], color="red", weight=4).add_to(m)

            folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
            folium_static(m, width=1000, height=600)
else:
    if st.button("📍 Activer le GPS / Forcer Cournonterral"):
        st.session_state['manual_mode'] = True
        st.rerun()
