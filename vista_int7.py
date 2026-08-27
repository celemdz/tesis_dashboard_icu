#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import time
import collections
import os

# ==============================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS GLOBALES (CSS CLÍNICO)
# ==============================================================================
st.set_page_config(layout="wide", page_title="Monitor UTI Central", page_icon="🫀")

st.markdown("""
<style>
    .stApp { background-color: #05060A; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: #05060A; }
    .stTabs [data-baseweb="tab"] { background-color: transparent; border-radius: 0px; padding: 10px 5px; border-bottom: 2px solid transparent; }
    .stTabs [aria-selected="true"] { border-bottom: 2px solid #00B0FF !important; background-color: transparent !important; }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 20px !important; font-weight: 300 !important; color: #A0AAB5; }
    .stTabs [aria-selected="true"] button [data-testid="stMarkdownContainer"] p { color: #ffffff !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

# RUTAS DE MIMIC-IV (VERIFICA QUE SEAN LAS CORRECTAS EN TU PC)
ruta_icu = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\icu"
ruta_hosp = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\hosp"

ruta_icustays = os.path.join(ruta_icu, "icustays.csv.gz")
ruta_chartevents = os.path.join(ruta_icu, "chartevents.csv.gz")
ruta_patients = os.path.join(ruta_hosp, "patients.csv.gz")

# ==============================================================================
# FUNCIONES DE ALARMAS INTELIGENTES Y ANÁLISIS NO LINEAL
# ==============================================================================
def evaluar_alarmas_inteligentes(datos_paciente):
    alarmas = []
    fc = datos_paciente['fc_base']
    pas = datos_paciente['pa_sistolica']
    pam = datos_paciente['pam']
    fr = datos_paciente['fr_resp']
    spo2 = datos_paciente['spo2_base']

    # 1. Tríada de Cushing (Opcional - Neuro)
    if pas > 160 and fc < 60 and fr < 12:
        alarmas.append(("CRÍTICO", f"🚨 CUSHING: Riesgo de Herniación"))

    # 2. SIRS (Opcional - Sepsis)
    if fc > 90 and fr > 20 and pas >= 90:
        alarmas.append(("ADVERTENCIA", f"⚠️ SIRS: Posible Infección"))

    # 3. Patrones Hemodinámicos Clásicos (TOTALMENTE INDEPENDIENTES)
    if fc > 100 and pas < 90:
        alarmas.append(("CRÍTICO", f"🚨 SHOCK: Inestabilidad Hemodinámica"))

    if fc > 120:
        alarmas.append(("ADVERTENCIA", f"⚠️ TAQUICARDIA: FC > 120 lpm"))

    if pam < 65:
        alarmas.append(("ADVERTENCIA", f"⚠️ HIPOPERFUSIÓN: PAM < 65 mmHg"))

    # 4. Patrón Respiratorio
    if fr > 25 and spo2 < 92:
        alarmas.append(("CRÍTICO", f"🚨 FALLA RESPIRATORIA: Hipoxemia severa"))

    # 5. Alarma del Sistema Autonómico (Barorreflejo de Pearson)
    if 'df_tendencia' in datos_paciente:
        df_tend = datos_paciente['df_tendencia']
        if 'FC' in df_tend.columns and 'PAM' in df_tend.columns:
            fc_array = df_tend['FC'].dropna().values
            pam_array = df_tend['PAM'].dropna().values
            min_len = min(len(fc_array), len(pam_array))

            if min_len >= 5: 
                fc_calc = fc_array[-min_len:]
                pam_calc = pam_array[-min_len:]
                if np.std(fc_calc) > 0 and np.std(pam_calc) > 0:
                    r = np.corrcoef(pam_calc, fc_calc)[0, 1]

                    if r > 0.3:
                        alarmas.append(("CRÍTICO", f"🚨 DESACOPLAMIENTO: Reflejo colapsado (r={r:.2f})"))
                    elif -0.3 <= r <= 0.3:
                        alarmas.append(("ADVERTENCIA", f"⚠️ REFLEJO DEPRIMIDO: Agotamiento simpático (r={r:.2f})"))

    return alarmas

def generar_diagrama_poincare(serie_fc):
    if len(serie_fc) < 5: 
        return None
    x_n = np.array(serie_fc[:-1])
    x_n1 = np.array(serie_fc[1:])
    diff = x_n - x_n1
    sd1 = float(np.sqrt(0.5 * np.var(diff)))
    sd2 = float(np.sqrt(2 * np.var(x_n) - 0.5 * np.var(diff)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_n, y=x_n1, mode='markers', marker=dict(size=6, color='#00B0FF', opacity=0.8)))
    min_v, max_v = min(serie_fc), max(serie_fc)
    fig.add_trace(go.Scatter(x=[min_v, max_v], y=[min_v, max_v], mode='lines', line=dict(color='#555555', dash='dash')))
    fig.update_layout(
        title=dict(text=f"Poincaré (SD1: {sd1:.1f} | SD2: {sd2:.1f})", font=dict(size=14, color="#A0AAB5")),
        plot_bgcolor='#0E1117', paper_bgcolor='#0E1117',
        xaxis=dict(title="FC(t)", gridcolor='#1F242D', color="#A0AAB5"),
        yaxis=dict(title="FC(t+1)", gridcolor='#1F242D', color="#A0AAB5"),
        height=220, margin=dict(t=30, b=10, l=10, r=10), showlegend=False
    )
    return fig

def generar_acoplamiento_hemodinamico(serie_fc, serie_pam):
    if len(serie_fc) < 5 or len(serie_pam) < 5: 
        return None
    min_len = min(len(serie_fc), len(serie_pam))
    fc_array = np.array(serie_fc[-min_len:])
    pam_array = np.array(serie_pam[-min_len:])

    if np.std(fc_array) == 0 or np.std(pam_array) == 0:
        correlacion = 0
    else:
        correlacion = np.corrcoef(pam_array, fc_array)[0, 1]

    if correlacion < -0.3: 
        estado_baro = "Acoplado (Sano)"
    elif correlacion > 0.3: 
        estado_baro = "Falla (Desacoplado)"
    else: 
        estado_baro = "Agotado (Neutro)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pam_array, y=fc_array, mode='markers', marker=dict(size=6, color='#E040FB', opacity=0.8)))
    if np.std(pam_array) > 0:
        m, b = np.polyfit(pam_array, fc_array, 1)
        fig.add_trace(go.Scatter(x=pam_array, y=m*pam_array + b, mode='lines', line=dict(color='#ffffff', dash='dot', width=1)))

    fig.update_layout(
        title=dict(text=f"Barorreflejo (r: {correlacion:.2f} | {estado_baro})", font=dict(size=14, color="#A0AAB5")),
        plot_bgcolor='#0E1117', paper_bgcolor='#0E1117',
        xaxis=dict(title="PAM (mmHg)", gridcolor='#1F242D', color="#A0AAB5"),
        yaxis=dict(title="FC (lpm)", gridcolor='#1F242D', color="#A0AAB5"),
        height=220, margin=dict(t=30, b=10, l=10, r=10), showlegend=False
    )
    return fig

# ==============================================================================
# 2. EXTRACCIÓN DE BASE DE DATOS (INTELIGENTE Y ALEATORIA)
# ==============================================================================
@st.cache_data
def cargar_macro():
    if not os.path.exists(ruta_icustays):
        st.error(f"❌ ERROR: No se encuentra la base de datos en: `{ruta_icustays}`")
        st.stop()
    icustays = pd.read_csv(ruta_icustays)
    patients = pd.read_csv(ruta_patients)
    icustays['intime'] = pd.to_datetime(icustays['intime'])
    return icustays, patients

icustays, patients = cargar_macro()
CONDICIONES_CAMAS = [
    "Shock Séptico", "Post-Qx Cardiovascular", "SDRA Severo", "TEC Grave / PIC", 
    "EPOC Reagudizado", "Politraumatismo", "Post-PCR", "Falla Multiorgánica", 
    "Cetoacidosis", "Shock Cardiogénico", "Neumonía Grave", "Post-Qx Neuro", 
    "Estatus Epiléptico", "Pancreatitis", "Estable / Destete"
]

@st.cache_data
def generar_perfiles_dinamicos():
    perfiles = {}
    items_vitales = {
        220045: 'FC', 220052: 'PAM', 220277: 'SpO2', 220210: 'FR', 
        223835: 'FiO2', 220050: 'PAS', 220051: 'PAD'
    }

    df_conteo = pd.read_csv(ruta_chartevents, usecols=['stay_id', 'itemid'])
    df_filtrado = df_conteo[df_conteo['itemid'].isin(items_vitales.keys())]
    stays_top_50 = df_filtrado['stay_id'].value_counts().head(50).index.tolist()
    stays_objetivo = np.random.choice(stays_top_50, 15, replace=False).tolist()

    df_vitales_lista = []
    for chunk in pd.read_csv(ruta_chartevents, usecols=['stay_id', 'itemid', 'charttime', 'valuenum'], chunksize=100000):
        filtro = chunk[chunk['stay_id'].isin(stays_objetivo) & chunk['itemid'].isin(items_vitales.keys())]
        df_vitales_lista.append(filtro)

    df_vitales = pd.concat(df_vitales_lista)
    df_vitales['charttime'] = pd.to_datetime(df_vitales['charttime'])
    df_vitales['Parametro'] = df_vitales['itemid'].map(items_vitales)

    for i, stay in enumerate(stays_objetivo):
        df_paciente = df_vitales[df_vitales['stay_id'] == stay].sort_values('charttime')
        if df_paciente.empty: 
            continue

        ultimos = df_paciente.groupby('Parametro').last()['valuenum'].to_dict()
        df_tendencia = df_paciente.pivot_table(index='charttime', columns='Parametro', values='valuenum').reset_index().ffill().bfill()

        condicion = CONDICIONES_CAMAS[i % len(CONDICIONES_CAMAS)]
        nombre_etiqueta = f"BOX {i+1:02d} | {condicion}"

        if "Shock" in condicion: 
            d_fc, d_pas, d_pad, d_pam, d_spo2, d_fr = 135.0, 80.0, 45.0, 55.0, 92.0, 26.0
        elif "SDRA" in condicion or "EPOC" in condicion or "Neumonía" in condicion: 
            d_fc, d_pas, d_pad, d_pam, d_spo2, d_fr = 115.0, 135.0, 85.0, 100.0, 86.0, 32.0
        elif "TEC" in condicion or "Neuro" in condicion: 
            d_fc, d_pas, d_pad, d_pam, d_spo2, d_fr = 55.0, 170.0, 100.0, 125.0, 98.0, 10.0
        else: 
            d_fc, d_pas, d_pad, d_pam, d_spo2, d_fr = 85.0, 120.0, 75.0, 90.0, 97.0, 16.0

        perfiles[nombre_etiqueta] = {
            'stay_id': stay, 
            'condicion': condicion,
            'fc_base': ultimos.get('FC', d_fc), 
            'pa_sistolica': ultimos.get('PAS', d_pas), 
            'pa_diastolica': ultimos.get('PAD', d_pad), 
            'pam': ultimos.get('PAM', d_pam), 
            'spo2_base': ultimos.get('SpO2', d_spo2), 
            'fr_resp': ultimos.get('FR', d_fr), 
            'fio2': ultimos.get('FiO2', 21.0), 
            'pic_base': 22.0 if "TEC" in condicion else 12.0, 
            'pao2': 95.0, 
            'gcs': 15.0, 
            'df_tendencia': df_tendencia
        }
    return perfiles

# ==============================================================================
# 3. INTERFAZ PRINCIPAL
# ==============================================================================
with st.spinner("Inicializando Módulo de Telemetría..."):
    perfiles_pacientes = generar_perfiles_dinamicos()

st.sidebar.markdown(f"<h2 style='color: #ffffff; text-align: center; margin-bottom: 20px; font-weight: 300;'>MONITOR<br><span style='color:#00B0FF; font-weight: bold;'>UTI CENTRAL</span></h2>", unsafe_allow_html=True)
paciente_global = st.sidebar.selectbox("SELECCIÓN DE BOX", list(perfiles_pacientes.keys()))
perfil = perfiles_pacientes[paciente_global]
st.sidebar.markdown("---")

tab_macro, tab_micro = st.tabs(["VISTA MACRO (Gestión)", "VISTA MICRO (Monitor)"])

# ==============================================================================
# PESTAÑA 1: VISTA MACRO (MAPA UTI CON ALARMAS INTEGRADAS)
# ==============================================================================
with tab_macro:
    st.write("")

    def obtener_estado_cama(datos_paciente):
        alarmas = evaluar_alarmas_inteligentes(datos_paciente)
        if not alarmas:
            return "#00E676", "✅ ESTABLE"

        # AQUÍ ESTÁ LA MAGIA: Extraemos todos los mensajes y los unimos con un punto separador
        textos = [msg.split(':')[0] for nivel, msg in alarmas]
        texto_unido = " • ".join(textos)

        # El color general del BOX será Rojo si hay alguna alarma crítica, sino Amarillo
        if any(nivel == "CRÍTICO" for nivel, msg in alarmas):
            return "#FF4B4B", texto_unido
        else:
            return "#F1C40F", texto_unido

    pacientes_lista = list(perfiles_pacientes.items())
    for fila in range(3):
        cols = st.columns(5)
        for col_idx in range(5):
            idx_paciente = fila * 5 + col_idx
            if idx_paciente < len(pacientes_lista):
                nombre_p, datos = pacientes_lista[idx_paciente]

                color_box, texto_alarma = obtener_estado_cama(datos)

                # Armamos la "Píldora" visual. Como ahora hay varias alarmas unidas, bajamos un poco la fuente
                if color_box == "#FF4B4B":
                    bg_alarma = "rgba(255, 75, 75, 0.15)"
                    html_alarma = f"<div style='background-color: {bg_alarma}; border: 1px solid {color_box}; border-radius: 4px; padding: 4px; margin-top: 12px; text-align: center;'><span style='color: {color_box}; font-size: 8.5px; font-weight: bold;'>{texto_alarma}</span></div>"
                elif color_box == "#F1C40F":
                    bg_alarma = "rgba(241, 196, 15, 0.15)"
                    html_alarma = f"<div style='background-color: {bg_alarma}; border: 1px solid {color_box}; border-radius: 4px; padding: 4px; margin-top: 12px; text-align: center;'><span style='color: {color_box}; font-size: 8.5px; font-weight: bold;'>{texto_alarma}</span></div>"
                else:
                    html_alarma = f"<div style='background-color: rgba(0, 230, 118, 0.05); border: 1px dashed rgba(0, 230, 118, 0.3); border-radius: 4px; padding: 4px; margin-top: 12px; text-align: center;'><span style='color: #00E676; font-size: 9px;'>{texto_alarma}</span></div>"

                with cols[col_idx]:
                    st.html(f"""
                    <div style="background-color: #0E1117; border-radius: 6px; border-top: 4px solid {color_box}; padding: 12px 15px; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1F242D; padding-bottom: 6px; margin-bottom: 10px;">
                            <h5 style="color: {color_box}; margin: 0; font-weight: 600; font-size: 12px; letter-spacing: 1px;">BOX {idx_paciente + 1:02d}</h5>
                        </div>
                        <p style="color: #A0AAB5; font-size: 11px; margin: 0 0 12px 0; font-weight: 300; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{datos['condicion']}</p>
                        <div style="display: flex; justify-content: space-between;">
                            <div style="text-align: left;">
                                <p style="color: #00E676; font-size: 10px; margin: 0; opacity: 0.8;">FC</p>
                                <h3 style="color: #00E676; font-family: 'Courier New', monospace; font-size: 18px; margin: 0; text-shadow: 0 0 5px rgba(0,230,118,0.3);">{int(datos['fc_base'])}</h3>
                            </div>
                            <div style="text-align: center;">
                                <p style="color: #FF4B4B; font-size: 10px; margin: 0; opacity: 0.8;">PAM</p>
                                <h3 style="color: #FF4B4B; font-family: 'Courier New', monospace; font-size: 18px; margin: 0; text-shadow: 0 0 5px rgba(255,75,75,0.3);">{int(datos['pam'])}</h3>
                            </div>
                            <div style="text-align: right;">
                                <p style="color: #00B0FF; font-size: 10px; margin: 0; opacity: 0.8;">SpO2</p>
                                <h3 style="color: #00B0FF; font-family: 'Courier New', monospace; font-size: 18px; margin: 0; text-shadow: 0 0 5px rgba(0,176,255,0.3);">{int(datos['spo2_base'])}</h3>
                            </div>
                        </div>
                        {html_alarma}
                    </div>
                    """)

# ==============================================================================
# PESTAÑA 2: VISTA MICRO (MONITOR, SEGUIMIENTO HISTÓRICO Y ALARMAS)
# ==============================================================================
with tab_micro:
    st.write("")

    # 1. PARÁMETROS VITALES GIGANTES
    col_fc, col_pa, col_spo2, col_fr = st.columns(4)
    with col_fc: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 8px; border-left: 4px solid #00E676; padding: 15px; display: flex; justify-content: space-between; align-items: center;"><div><p style="color: #00E676; font-size: 14px; font-weight: 700; margin: 0;">FC</p><p style="color:#5C6370; font-size:10px; margin:0;">lpm</p></div><h1 style="color: #00E676; font-family: 'Courier New', monospace; font-size: 45px; margin: 0; text-shadow: 0 0 10px rgba(0,230,118,0.4);">{int(perfil['fc_base'])}</h1></div>""")
    with col_pa: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 8px; border-left: 4px solid #FF4B4B; padding: 15px; display: flex; justify-content: space-between; align-items: center;"><div><p style="color: #FF4B4B; font-size: 14px; font-weight: 700; margin: 0;">PA</p><p style="color:#5C6370; font-size:10px; margin:0;">mmHg</p></div><div style="text-align:right;"><h2 style="color: #FF4B4B; font-family: 'Courier New', monospace; font-size: 24px; margin: 0; line-height: 1;">{int(perfil['pa_sistolica'])}/{int(perfil['pa_diastolica'])}</h2><h3 style="color: #FF4B4B; font-family: 'Courier New', monospace; font-size: 18px; margin: 0; opacity: 0.7;">({int(perfil['pam'])})</h3></div></div>""")
    with col_spo2: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 8px; border-left: 4px solid #00B0FF; padding: 15px; display: flex; justify-content: space-between; align-items: center;"><div><p style="color: #00B0FF; font-size: 14px; font-weight: 700; margin: 0;">SpO2</p><p style="color:#5C6370; font-size:10px; margin:0;">%</p></div><h1 style="color: #00B0FF; font-family: 'Courier New', monospace; font-size: 45px; margin: 0; text-shadow: 0 0 10px rgba(0,176,255,0.4);">{int(perfil['spo2_base'])}</h1></div>""")
    with col_fr: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 8px; border-left: 4px solid #F1C40F; padding: 15px; display: flex; justify-content: space-between; align-items: center;"><div><p style="color: #F1C40F; font-size: 14px; font-weight: 700; margin: 0;">RESP</p><p style="color:#5C6370; font-size:10px; margin:0;">rpm</p></div><h1 style="color: #F1C40F; font-family: 'Courier New', monospace; font-size: 45px; margin: 0; text-shadow: 0 0 10px rgba(241,196,15,0.4);">{int(perfil['fr_resp'])}</h1></div>""")

    st.write("")

    # 2. SEGUIMIENTO HISTÓRICO (TRIAGE 24Hs + SOFA)
    def calcular_triage_hist(fila):
        fr = fila.get('FR', perfil['fr_resp'])
        spo2 = fila.get('SpO2', perfil['spo2_base'])
        pas = fila.get('PAS', perfil['pa_sistolica'])
        fc = fila.get('FC', perfil['fc_base'])
        pam = fila.get('PAM', perfil['pam'])

        pts_fr = 3 if fr <= 8 else (1 if 9 <= fr <= 11 else (0 if 12 <= fr <= 20 else (2 if 21 <= fr <= 24 else 3)))
        pts_spo2 = 3 if spo2 <= 91 else (2 if 92 <= spo2 <= 93 else (1 if 94 <= spo2 <= 95 else 0))
        pts_pas = 3 if pas <= 90 else (2 if 91 <= pas <= 100 else (1 if 101 <= pas <= 110 else (0 if 111 <= pas <= 219 else 3)))
        pts_fc = 3 if fc <= 40 else (1 if 41 <= fc <= 50 else (0 if 51 <= fc <= 90 else (1 if 91 <= fc <= 110 else (2 if 111 <= fc <= 130 else 3))))
        news2 = int(pts_fr + pts_spo2 + pts_pas + pts_fc)

        if news2 >= 7 or (fc > 100 and pas < 90) or (fr > 25 and spo2 < 92):
            return pd.Series({'Score': news2, 'Color': "#FF4B4B", 'Nivel': "CRÍTICO (PR-1)"})
        elif news2 >= 5 or fc > 120 or pam < 65:
            return pd.Series({'Score': news2, 'Color': "#F1C40F", 'Nivel': "URGENTE (PR-2)"})
        else:
            return pd.Series({'Score': news2, 'Color': "#00E676", 'Nivel': "ESTABLE (PR-3)"})

    df_historial = perfil['df_tendencia'].tail(24).copy()
    if not df_historial.empty:
        df_historial = pd.concat([df_historial, df_historial.apply(calcular_triage_hist, axis=1)], axis=1)
        est_actual = df_historial.iloc[-1]
        peor_est = df_historial.loc[df_historial['Score'].idxmax()]
        hora_peor = peor_est['charttime'].strftime("%H:%M") if pd.notnull(peor_est['charttime']) else "Reciente"
    else:
        est_actual = calcular_triage_hist(pd.Series({'FR': perfil['fr_resp'], 'SpO2': perfil['spo2_base'], 'PAS': perfil['pa_sistolica'], 'FC': perfil['fc_base'], 'PAM': perfil['pam']}))
        peor_est = est_actual
        hora_peor = "Actual"

    # SOFA
    fi_dec = perfil['fio2'] / 100.0
    pa_fi = perfil['pao2'] / fi_dec if fi_dec > 0 else 400
    s_resp = 4 if pa_fi < 100 else (3 if pa_fi < 200 else (2 if pa_fi < 300 else (1 if pa_fi < 400 else 0)))
    s_cardio = 4 if perfil['pam'] < 60 else (1 if perfil['pam'] < 70 else 0)
    s_neuro = 4 if perfil['gcs'] < 6 else (3 if perfil['gcs'] <= 9 else (2 if perfil['gcs'] <= 12 else (1 if perfil['gcs'] <= 14 else 0)))
    sofa_total = int(s_resp + s_cardio + s_neuro)
    color_sofa = "#FF4B4B" if sofa_total > 6 else ("#F1C40F" if sofa_total > 3 else "#00B0FF")

    st.markdown("<p style='color: #A0AAB5; font-size: 12px; font-weight: 600; letter-spacing: 1px; margin-bottom: 5px;'>SEGUIMIENTO CLÍNICO (ÚLTIMAS 24H)</p>", unsafe_allow_html=True)
    col_tri1, col_tri2, col_sof = st.columns([1, 1, 1])
    with col_tri1: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 6px; border-top: 2px solid {est_actual['Color']}; padding: 12px;"><p style="color: #A0AAB5; font-size: 10px; margin: 0;">TRIAGE NEWS2 (ACTUAL)</p><h3 style="color: {est_actual['Color']}; margin: 5px 0;">{est_actual['Nivel']}</h3><p style="color: #5C6370; font-size: 11px; margin: 0;">Puntuación Base: {est_actual['Score']} pts</p></div>""")
    with col_tri2: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 6px; border-top: 2px dashed {peor_est['Color']}; padding: 12px;"><p style="color: #A0AAB5; font-size: 10px; margin: 0;">MAYOR RIESGO (HISTÓRICO 24H)</p><h3 style="color: {peor_est['Color']}; margin: 5px 0;">{peor_est['Nivel']}</h3><p style="color: #5C6370; font-size: 11px; margin: 0;">Pico detectado a las: {hora_peor} hs</p></div>""")
    with col_sof: 
        st.html(f"""<div style="background-color: #0E1117; border-radius: 6px; border-top: 2px solid {color_sofa}; padding: 12px;"><p style="color: #A0AAB5; font-size: 10px; margin: 0;">SCORE DE FALLA ORGÁNICA (SOFA)</p><h3 style="color: {color_sofa}; margin: 5px 0;">{sofa_total}/24 pts</h3><p style="color: #5C6370; font-size: 11px; margin: 0;">Evaluación multiorgánica.</p></div>""")

    st.write("")

  # 3. ALARMAS EXPERTAS Y GRÁFICOS NO LINEALES (POINCARÉ + ACOPLAMIENTO)
    col_alarma, col_graficos = st.columns([1.2, 1])
    with col_alarma:
        st.markdown("<p style='color: #A0AAB5; font-size: 12px; font-weight: 600; letter-spacing: 1px;'>SISTEMA DE ALARMAS INTELIGENTES</p>", unsafe_allow_html=True)
        alarmas_activas = evaluar_alarmas_inteligentes(perfil)
        if alarmas_activas:
            for nivel, msg in alarmas_activas:
                bg = "rgba(255, 75, 75, 0.15)" if nivel == "CRÍTICO" else "rgba(241, 196, 15, 0.15)"
                brd = "#FF4B4B" if nivel == "CRÍTICO" else "#F1C40F"
                st.html(f"<div style='background-color: {bg}; border-left: 3px solid {brd}; padding: 12px; margin-bottom: 8px; border-radius: 4px;'><p style='color: {brd}; font-size:14px; margin: 0; font-weight: 600;'>{msg}</p></div>")
        else:
            st.html("<div style='background-color: rgba(0, 230, 118, 0.05); border-left: 3px solid #00E676; padding: 12px; border-radius: 4px;'><p style='color: #00E676; margin: 0; font-weight: 600;'>ESTABLE: Sin patrones de riesgo inminente.</p></div>")

    with col_graficos:
        # SEPARAMOS LAS CONDICIONES: Poincaré solo depende de la FC
        if 'FC' in perfil['df_tendencia'].columns:
            serie_fc = perfil['df_tendencia']['FC'].dropna().tolist()

            # Gráfico 1: Poincaré siempre se intentará dibujar
            fig_poincare = generar_diagrama_poincare(serie_fc)
            if fig_poincare: 
                st.plotly_chart(fig_poincare, use_container_width=True)

            # Gráfico 2: Acoplamiento Hemodinámico (Solo si también existe la PAM)
            if 'PAM' in perfil['df_tendencia'].columns:
                serie_pam = perfil['df_tendencia']['PAM'].dropna().tolist()
                fig_acoplamiento = generar_acoplamiento_hemodinamico(serie_fc, serie_pam)
                if fig_acoplamiento: 
                    st.plotly_chart(fig_acoplamiento, use_container_width=True)

    # 4. TELEMETRÍA CONTINUA (ONDAS)
    st.markdown("<p style='color: #A0AAB5; font-size: 12px; font-weight: 600; letter-spacing: 1px;'>TELEMETRÍA EN TIEMPO REAL</p>", unsafe_allow_html=True)
    col_g1, col_g2 = st.columns(2)
    with col_g1: 
        espacio_pa = st.empty()
    with col_g2: 
        espacio_co2 = st.empty()

    vent = 150
    tiempos = collections.deque(maxlen=vent)
    datos_pa = collections.deque(maxlen=vent)
    datos_co2 = collections.deque(maxlen=vent)

    w_cardiaco = 2 * np.pi * (perfil['fc_base'] / 60.0)
    w_resp = 2 * np.pi * (perfil['fr_resp'] / 60.0) 
    t0 = time.time()

    # BUCLE ANIMADO
    while True:
        t_act = time.time() - t0
        t_batch = np.linspace(t_act, t_act + 0.1, 5)

        onda_pa = perfil['pa_diastolica'] + (perfil['pa_sistolica'] - perfil['pa_diastolica']) * (0.4 * np.sin(w_cardiaco * t_batch) + 0.3 * np.sin(2 * w_cardiaco * t_batch))
        f_resp = np.sin(w_resp * t_batch)
        onda_co2 = np.where(f_resp > 0, 38.0 - 2 + 2 * f_resp, 0) 

        for i in range(5):
            tiempos.append(t_batch[i])
            datos_pa.append(onda_pa[i])
            datos_co2.append(onda_co2[i])

        espacio_pa.line_chart(pd.DataFrame({"PAI (mmHg)": datos_pa}, index=tiempos), height=180, color="#FF4B4B")
        espacio_co2.line_chart(pd.DataFrame({"EtCO2 (mmHg)": datos_co2}, index=tiempos), height=180, color="#F1C40F") 
        time.sleep(0.1)

