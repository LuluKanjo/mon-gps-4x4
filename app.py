import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
import urllib.parse
from geopy.distance import geodesic

st.set_page_config(page_title="4x4 Expedition Master", layout="wide", initial_sidebar_state="collapsed")

# --- INITIALISATION ---
if 'trace' not in st.session_state: st.session_state['trace'] = []
if 'total_dist' not in st.session_state: st.session_state['total_dist'] = 0.0
if 'manual_mode' not in st.session_state: st.session_state['manual_mode'] = False

# --- RÉCUPÉRATION GPS ---
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps_v4')

# --- FONCTION DE RÉCUPÉRATION ULTRA-LÉGÈRE ---
@st.cache_data(ttl=300)
def fetch_data_safe(lat, lon, dist):
    # On utilise un serveur qui est souvent moins chargé (le serveur français de l'asso OSM)
    url = "https://overpass.openstreetmap.fr/api/interpreter"
    
    # Requête ultra-simplifiée : uniquement les pistes (track)
    query = f"""[out:json][timeout:20];
    way["highway"="track"]["motor_vehicle"!~"no|private"](around:{dist},{lat},{lon});
    out body; >; out skel qt;"""
    
    # On change l'identité à chaque fois pour tromper le blocage IP
    headers = {'User-Agent': 'Expedition-4x4-V4-Tester'}
    
    try:
        r = requests.get(url, params={'data': query}, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json(), "OK"
        elif r.status_code == 429:
            return None, "Erreur 429 : Trop de monde sur ce serveur, attendez 1 min."
        else:
            return None, f"Erreur {r.status_code} : Le serveur fait une pause."
    except Exception as e:
        return None, "Erreur de connexion : Vérifiez votre 4G/5G."

st.title("🚜 4x4 Adventure Dash")

# --- GESTION POSITION ---
if not loc and not st.session_state['manual_mode']:
    st.info("🛰️ Recherche GPS... Si rien ne bouge, cliquez ci-dessous.")
    if st.button("📍 Forcer la position (Cournonterral)"):
        st.session_state['manual_mode'] = True
        st.rerun()

if loc or st.session_state['manual_mode']:
    lat, lon = (loc['lat'], loc['lon']) if loc else (43.5578, 3.7188)
    
    # Metrics simplifiées
    c1, c2, c3 = st.columns(3)
    c1.metric("Altitude", f"{int(loc.get('alt', 50)) if loc else 50} m")
    c2.metric("Vitesse", f"{int((loc.get('speed', 0) or 0)*3.6) if loc else 0} km/h")
    c3.metric("Distance", f"{st.session_state['total_dist']:.2f} km")

    # --- LA CARTE ---
    if st.button("🗺️ CHARGER LES PISTES (RAYON 2KM)"):
        with st.spinner("Requête en cours..."):
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)
            
            # On demande uniquement 2km pour être sûr que ça passe
            data, status = fetch_data_safe(lat, lon, 2000)
            
            if data:
                nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
                for el in data['elements']:
                    if el['type'] == 'way':
                        coords = [nodes[nid] for nid in el['nodes'] if nid in nodes]
                        folium.PolyLine(coords, color="#CCFF00", weight=5, opacity=0.9).add_to(m)
                st.success("Pistes chargées avec succès !")
            else:
                st.error(status)

            folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
            folium_static(m, width=1000, height=600)
