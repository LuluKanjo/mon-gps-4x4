import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
import urllib.parse
from geopy.distance import geodesic

# Configuration de la page
st.set_page_config(page_title="4x4 Expedition Master", layout="wide", initial_sidebar_state="collapsed")

# Initialisation du stockage de la trace et de la distance
if 'trace' not in st.session_state: st.session_state['trace'] = []
if 'total_dist' not in st.session_state: st.session_state['total_dist'] = 0.0

# --- BARRE LATÉRALE : RÉGLAGES ---
with st.sidebar:
    st.title("⚙️ Paramètres Road Trip")
    dest_input = st.text_input("Destination", "Lafrançaise, France")
    num_urgence = st.text_input("📞 Numéro SOS (+336...)", "")
    scan_dist = st.slider("🔍 Rayon de scan pistes (m)", 1000, 10000, 5000)
    
    st.divider()
    recording = st.toggle("🛰️ Enregistrer ma trace rouge", value=False)
    
    if st.button("🗑️ Réinitialiser l'étape"):
        st.session_state['trace'] = []
        st.session_state['total_dist'] = 0.0
        st.rerun()
    
    if len(st.session_state['trace']) > 1:
        df = pd.DataFrame(st.session_state['trace'], columns=['lat', 'lon'])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter ma trace (CSV)", data=csv, file_name="parcours_4x4.csv")

# --- RÉCUPÉRATION GPS RÉEL ---
# Cette fonction interroge la puce GPS de ton smartphone via le navigateur
loc = streamlit_js_eval(js_expressions='navigator.geolocation.getCurrentPosition(pos => {return {lat: pos.coords.latitude, lon: pos.coords.longitude, alt: pos.coords.altitude, speed: pos.coords.speed}})', key='gps')

# --- LOGIQUE TECHNIQUE ---
def get_route_liaison(s_lat, s_lon, destination):
    """Calcule l'itinéraire routier (bitume) via OSRM"""
    geo_url = f"https://nominatim.openstreetmap.org/search?q={destination}&format=json&limit=1"
    try:
        dest_data = requests.get(geo_url, headers={'User-Agent': 'GPS_4x4_App'}).json()
        if not dest_data: return None, None
        d_lat, d_lon = float(dest_data[0]['lat']), float(dest_data[0]['lon'])
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{s_lon},{s_lat};{d_lon},{d_lat}?overview=full&geometries=geojson"
        route_data = requests.get(osrm_url).json()
        return route_data['routes'][0]['geometry']['coordinates'], (d_lat, d_lon)
    except: return None, None

def get_pistes_and_pois(lat, lon, dist):
    """Récupère les pistes (Overpass) et les points d'intérêt"""
    query = f"""
    [out:json];
    (
      way["highway"~"track|unclassified"]["motor_vehicle"!~"no|private"]["access"!~"no|private"](around:{dist},{lat},{lon});
      node["amenity"~"fuel|drinking_water"](around:{dist},{lat},{lon});
      node["tourism"~"camp_site|picnic_site"](around:{dist},{lat},{lon});
    );
    out body; >; out skel qt;
    """
    try: return requests.get("http://overpass-api.de/api/interpreter", params={'data': query}, timeout=10).json()
    except: return None

# --- INTERFACE PRINCIPALE ---
st.title("🚜 4x4 Adventure Dash")

if loc:
    lat, lon = loc['lat'], loc['lon']
    alt = loc.get('alt', 0)
    vitesse = (loc.get('speed', 0) or 0) * 3.6
    
    # Enregistrement de la trace
    if recording:
        if not st.session_state['trace'] or st.session_state['trace'][-1] != (lat, lon):
            if st.session_state['trace']:
                st.session_state['total_dist'] += geodesic(st.session_state['trace'][-1], (lat, lon)).km
            st.session_state['trace'].append((lat, lon))

    # Tableau de bord Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Altitude", f"{int(alt) if alt else '--'} m")
    c2.metric("Vitesse", f"{int(vitesse)} km/h")
    c3.metric("Distance Trace", f"{st.session_state['total_dist']:.2f} km")
    try:
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true").json()
        c4.metric("Météo", f"{w['current_weather']['temperature']} °C")
    except: c4.metric("Météo", "--")

    # Bouton SOS
    if num_urgence:
        g_maps = f"https://www.google.com/maps?q={lat},{lon}"
        encoded_msg = urllib.parse.quote(f"SOS 4x4 ! Position : {g_maps}")
        st.markdown(f'<a href="sms:{num_urgence}?body={encoded_msg}"><button style="width:100%; background-color:#ff4b4b; color:white; border:none; padding:15px; border-radius:10px; font-weight:bold; cursor:pointer; margin-bottom:20px;">🚨 ENVOYER POSITION SOS PAR SMS</button></a>', unsafe_allow_html=True)

    # Bouton de rafraîchissement
    if st.button("🗺️ CALCULER L'ÉTAPE & SCANNER LES PISTES"):
        with st.spinner("Analyse du terrain en cours..."):
            m = folium.Map(location=[lat, lon], zoom_start=14)
            
            # Fonds de carte : Satellite et Plan
            folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Vue Satellite').add_to(m)
            folium.TileLayer('OpenStreetMap', name='Plan Routier').add_to(m)

            # 1. Liaison Bitume (Pointillé blanc)
            route_coords, final_dest = get_route_liaison(lat, lon, dest_input)
            if route_coords:
                folium.PolyLine([[c[1], c[0]] for c in route_coords], color="white", weight=3, opacity=0.6, dash_array='5, 10', name="Route").add_to(m)
                folium.Marker(final_dest, icon=folium.Icon(color='black', icon='flag-checkered', prefix='fa')).add_to(m)

            # 2. Scan des Pistes (Jaune Fluo)
            data = get_pistes_and_pois(lat, lon, scan_dist)
            if data and 'elements' in data:
                nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
                for el in data['elements']:
                    if el['type'] == 'way':
                        coords = [nodes[nid] for nid in el['nodes'] if nid in nodes]
                        folium.PolyLine(coords, color="#CCFF00", weight=6, opacity=0.9).add_to(m)
                    if el['type'] == 'node':
                        tags = el.get('tags', {})
                        if 'fuel' in tags.values(): icon, color = 'gas-pump', 'orange'
                        elif 'drinking_water' in tags.values(): icon, color = 'tint', 'blue'
                        else: icon, color = 'bed', 'green' # Bivouac/Camping
                        folium.Marker([el['lat'], el['lon']], icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(m)

            # 3. Ma Trace (Rouge)
            if len(st.session_state['trace']) > 1:
                folium.PolyLine(st.session_state['trace'], color="red", weight=4, opacity=1).add_to(m)

            # 4. Ma Position
            folium.Marker([lat, lon], icon=folium.Icon(color='red', icon='car', prefix='fa')).add_to(m)
            
            folium.LayerControl().add_to(m)
            folium_static(m, width=1000, height=600)
else:
    st.warning("📡 En attente du signal GPS... Vérifiez que la localisation est activée sur votre téléphone et que vous êtes à l'extérieur.")
    # Petit rappel pour Cournonterral si le GPS est capricieux au départ
    st.info("Note : Si vous êtes à Cournonterral, assurez-vous de bien accepter l'autorisation 'Localisation' du navigateur.")
