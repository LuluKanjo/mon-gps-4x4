import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
import urllib.parse
from geopy.distance import geodesic

st.set_page_config(page_title="4x4 Dash Pro", layout="wide", initial_sidebar_state="collapsed")

# Initialisation des variables de session
if 'trace' not in st.session_state: st.session_state['trace'] = []
if 'total_dist' not in st.session_state: st.session_state['total_dist'] = 0.0

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("⚙️ Réglages Expédition")
    num_urgence = st.text_input("📞 Numéro SOS (+336...)", "")
    scan_dist = st.slider("🔍 Scan des pistes (m)", 1000, 10000, 5000)
    
    st.divider()
    recording = st.toggle("🛰️ Enregistrer ma trace", value=False)
    if st.button("🗑️ Reset l'étape / Effacer trace"):
        st.session_state['trace'] = []
        st.session_state['total_dist'] = 0.0
        st.rerun()
    
    if len(st.session_state['trace']) > 1:
        df_trace = pd.DataFrame(st.session_state['trace'], columns=['lat', 'lon'])
        csv = df_trace.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Télécharger ma trace (CSV)", data=csv, file_name="parcours_4x4.csv")

# --- RÉCUPÉRATION GPS ---
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps')

st.title("🚜 4x4 Adventure Dash Pro")

if loc:
    lat, lon = loc['lat'], loc['lon']
    alt = loc.get('alt', 0)
    vitesse = (loc.get('speed', 0) or 0) * 3.6
    
    if recording:
        if not st.session_state['trace'] or st.session_state['trace'][-1] != (lat, lon):
            if st.session_state['trace']:
                st.session_state['total_dist'] += geodesic(st.session_state['trace'][-1], (lat, lon)).km
            st.session_state['trace'].append((lat, lon))

    # --- WIDGETS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Altitude", f"{int(alt) if alt else '--'} m")
    c2.metric("Vitesse", f"{int(vitesse)} km/h")
    c3.metric("Distance Trace", f"{st.session_state['total_dist']:.2f} km")
    try:
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true").json()
        c4.metric("Météo", f"{w['current_weather']['temperature']} °C")
    except: c4.metric("Météo", "--")

    # --- BOUTON SOS ---
    if num_urgence:
        g_link = f"https://www.google.com/maps?q={lat},{lon}"
        msg = urllib.parse.quote(f"SOS 4x4 ! Je suis bloqué ici : {g_link}")
        sms_link = f"sms:{num_urgence}?body={msg}"
        st.markdown(f'<a href="{sms_link}"><button style="width:100%; background-color:#ff4b4b; color:white; border:none; padding:12px; border-radius:10px; font-weight:bold; cursor:pointer;">🚨 ENVOYER POSITION SOS</button></a>', unsafe_allow_html=True)

    # --- CARTE ---
    if st.button("🗺️ ACTUALISER LA ZONE"):
        m = folium.Map(location=[lat, lon], zoom_start=15)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satellite').add_to(m)
        
        if len(st.session_state['trace']) > 1:
            folium.PolyLine(st.session_state['trace'], color="red", weight=4).add_to(m)

        # Overpass (Pistes)
        query = f"""[out:json];(way["highway"~"track|unclassified"]["motor_vehicle"!~"no|private"]["access"!~"no|private"](around:{scan_dist},{lat},{lon});node["amenity"~"fuel|drinking_water"](around:{scan_dist},{lat},{lon});node["tourism"~"camp_site|picnic_site"](around:{scan_dist},{lat},{lon}););out body;>;out skel qt;"""
        try:
            data = requests.get("http://overpass-api.de/api/interpreter", params={'data': query}).json()
            nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
            for el in data['elements']:
                if el['type'] == 'way':
                    coords = [nodes[nid] for nid in el['nodes'] if nid in nodes]
                    folium.PolyLine(coords, color="#CCFF00", weight=5).add_to(m)
                if el['type'] == 'node':
                    tags = el.get('tags', {})
                    if 'fuel' in tags.values(): icon = 'orange'
                    elif 'drinking_water' in tags.values(): icon = 'blue'
                    else: icon = 'green'
                    folium.Marker([el['lat'], el['lon']], icon=folium.Icon(color=icon, icon='info-sign')).add_to(m)
        except: pass

        folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
        folium_static(m, width=1000, height=600)
else:
    st.info("Recherche GPS... Activez la localisation sur votre appareil.")
