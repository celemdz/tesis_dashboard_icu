import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import time
import collections
import os

# ==============================================================================
# 1. CONFIGURACION DE LA PAGINA Y RUTAS ABSOLUTAS
# ==============================================================================
st.set_page_config(layout="wide", page_title="Central de Monitoreo UCI")

# Rutas estrictas definidas por el usuario
ruta_icu = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\icu"
ruta_hosp = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\hosp"

ruta_icustays = os.path.join(ruta_icu, "icustays.csv.gz")
ruta_chartevents = os.path.join(ruta_icu, "chartevents.csv.gz")
ruta_patients = os.path.join(ruta_hosp, "patients.csv.gz")

# ==============================================================================
# 2. EXTRACCION ESTRICTA DE LA BASE DE DATOS REAL
# ==============================================================================
@st.cache_data
def cargar_macro():
    if not os.path.exists(ruta_icustays):
        st.error(f"No se encuentra el archivo en: {ruta_icustays}. Revisa la ruta.")
        st.stop()

    icustays = pd.read_csv(ruta_icustays)
    patients = pd.read_csv(ruta_patients)
    icustays['intime'] = pd.to_datetime(icustays['intime'])
    return icustays, patients

icustays, patients = cargar_macro()

@st.cache_data
def generar_perfiles_dinamicos():
    perfiles = {}
    df_icu = pd.read_csv(ruta_icustays)
    stays_objetivo = df_icu['stay_id'].dropna().unique()[:15]

    items_vitales = {
        220045: 'FC', 220052: 'PAM', 220277: 'SpO2', 
        220210: 'FR', 223835: 'FiO2', 220050: 'PAS', 220051: 'PAD'
    }

    df_vitales_lista = []
    for chunk in pd.read_csv(ruta_chartevents, usecols=['stay_id', 'itemid', 'charttime', 'valuenum'], chunksize=100000):
        filtro = chunk[chunk['stay_id'].isin(stays_objetivo) & chunk['itemid'].isin(items_vitales.keys())]
        df_vitales_lista.append(filtro)

    df_vitales = pd.concat(df_vitales_lista)
    df_vitales['charttime'] = pd.to_datetime(df_vitales['charttime'])
    df_vitales['Parametro'] = df_vitales['itemid'].map(items_vitales)

    for stay in stays_objetivo:
        df_paciente = df_vitales[df_vitales['stay_id'] == stay].sort_values('charttime')
        if df_paciente.empty: 
            continue

        ultimos = df_paciente.groupby('Parametro').last()['valuenum'].to_dict()
        df_tendencia = df_paciente.pivot_table(index='charttime', columns='Parametro', values='valuenum').reset_index()
        df_tendencia = df_tendencia.ffill().bfill()

        perfiles[f"Paciente MIMIC-IV Real (Stay ID: {stay})"] = {
            'fc_base': ultimos.get('FC', 80.0), 
            'pa_sistolica': ultimos.get('PAS', 120.0), 
            'pa_diastolica': ultimos.get('PAD', 80.0), 
            'pam': ultimos.get('PAM', 85.0),
            'spo2_base': ultimos.get('SpO2', 98.0), 
            'fr_resp': ultimos.get('FR', 16.0), 
            'fio2': ultimos.get('FiO2', 21.0),
            'pic_base': 12.0, 'peep_base': 5.0, 'pip_base': 18.0, 'vt_base': 450.0,
            'pao2': 95.0, 'creatinina': 0.8, 'bilirrubina': 0.5, 'plaquetas': 250.0,
            'vasopresores': "Ninguno", 'diuresis': 1500.0, 'gcs': 15.0,
            'df_tendencia': df_tendencia
        }

    if not perfiles:
        st.error("Se leyeron los archivos, pero los primeros 5 pacientes no tienen datos vitales registrados en MIMIC-IV.")
        st.stop()
    return perfiles

# ==============================================================================
# 3. INTERFAZ Y RENDERIZADO
# ==============================================================================
with st.spinner("Conectando con la base de datos clinica de MIMIC-IV..."):
    perfiles_pacientes = generar_perfiles_dinamicos()

st.sidebar.title("Configuracion Central UCI")
st.sidebar.markdown("Base de Datos: **MIMIC-IV Demo**")
paciente_global = st.sidebar.selectbox("Seleccione Paciente en Cama:", list(perfiles_pacientes.keys()))
perfil = perfiles_pacientes[paciente_global]

# Reestructuracion en 2 pestañas principales
tab_macro, tab_micro = st.tabs(["Vista Macro (Gestion Hospitalaria)", "Vista Micro (Monitor Integral)"])

# ==============================================================================
# PESTAÑA 1: VISTA MACRO (GESTION)
# ==============================================================================
with tab_macro:
    st.title("Estacion Central de Enfermeria")
    sub_tab_camas, sub_tab_kpis = st.tabs(["Layout UTI (Tiempo Real)", "Metricas y KPIs (Historico)"])
    
    with sub_tab_camas:
        # Generar 3 filas de 5 columnas (15 camas en total)
        for fila in range(3):
            cols = st.columns(5)
            for col_idx in range(5):
                idx_paciente = fila * 5 + col_idx
                if idx_paciente < len(pacientes_lista):
                    nombre_p, datos = pacientes_lista[idx_paciente]
                    color_box = obtener_color_cama(datos)
                    with cols[col_idx]:
                        st.html(f"""
                        <div style="background-color: #1C1E24; border: 2px solid {color_box}; border-radius: 10px; padding: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); margin-bottom: 20px;">
                            <div style="background-color: {color_box}; padding: 5px; border-radius: 5px; margin-bottom: 10px; text-align: center;">
                                <h4 style="color: white; margin: 0;">Box {idx_paciente + 1}</h4>
                            </div>
                            <p style="color: #a4b0be; font-size: 11px; margin: 0 0 15px 0; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{nombre_p}</p>
                            <div style="display: flex; justify-content: space-around;">
                                <div style="text-align: center;"><p style="color: #00E676; margin: 0; font-size: 12px; font-weight: bold;">FC</p><h3 style="color: white; margin: 0;">{int(datos['fc_base'])}</h3></div>
                                <div style="text-align: center;"><p style="color: #FF4B4B; margin: 0; font-size: 12px; font-weight: bold;">PAM</p><h3 style="color: white; margin: 0;">{int(datos['pam'])}</h3></div>
                                <div style="text-align: center;"><p style="color: #00B0FF; margin: 0; font-size: 12px; font-weight: bold;">SpO2</p><h3 style="color: white; margin: 0;">{int(datos['spo2_base'])}</h3></div>
                            </div>
                        </div>
                        """)
    with sub_tab_kpis:
        st.markdown("### El Desarrollo de un Dashboard Clinico para el Monitoreo de KPIs")
        total_pacientes = int(icustays['stay_id'].nunique())
        estancia_promedio = float(icustays['los'].mean())
        df_mortalidad = pd.merge(icustays, patients, on='subject_id', how='left')
        fallecidos_totales = df_mortalidad[df_mortalidad['dod'].notna()]['stay_id'].nunique()
        tasa_mortalidad = (fallecidos_totales / total_pacientes) * 100

        col_izq, col_der = st.columns([1, 1])
        with col_izq:
            st.markdown("#### Indicadores Operativos Clave")
            st.metric(label="Total de Altas", value=total_pacientes)
            st.metric(label="LOS Promedio", value=f"{estancia_promedio:.2f} dias")

        with col_der:
            df_pie_mortalidad = pd.DataFrame({'Estado': ['Fallecidos', 'Sobrevivientes'], 'Porcentaje': [tasa_mortalidad, 100 - tasa_mortalidad]})
            colores_mortalidad = {'Fallecidos': '#d62728', 'Sobrevivientes': '#2ca02c'}
            fig_torta = px.pie(df_pie_mortalidad, names='Estado', values='Porcentaje', hole=0.4, color='Estado', color_discrete_map=colores_mortalidad)
            fig_torta.update_traces(texttemplate='%{percent:.1%}', textposition='inside')
            fig_torta.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=220)
            st.plotly_chart(fig_torta, use_container_width=True)

        st.markdown("---")
        col_grafico1, col_grafico2 = st.columns(2)
        with col_grafico1:
            icustays['mes_anio'] = icustays['intime'].dt.to_period('M').astype(str)
            df_mensual = icustays.groupby('mes_anio')['stay_id'].nunique().reset_index()
            df_mensual.columns = ['Mes', 'Cantidad']
            fig_barras = px.bar(df_mensual, x='Mes', y='Cantidad', text_auto=True, color_discrete_sequence=['#1f77b4'])
            st.plotly_chart(fig_barras, use_container_width=True)
        with col_grafico2:
            df_sectores = icustays['first_careunit'].value_counts().reset_index()
            df_sectores.columns = ['Unidad', 'Total']
            fig_sectores = px.pie(df_sectores, names='Unidad', values='Total', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_sectores, use_container_width=True)

# ==============================================================================
# PESTAÑA 2: VISTA MICRO (MONITOR INTEGRAL)
# ==============================================================================
with tab_micro:
    st.title(f"Monitorizacion Continua: {paciente_global}")
    st.write("")

    # 1. PARAMETROS VITALES ACTUALES
    col_fc, col_pa, col_spo2, col_pic = st.columns(4)
    with col_fc: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00E676;'><p style='color:#00E676; margin:0; font-weight:bold;'>FC (lpm)</p><h2 style='color:#ffffff; margin:0;'>{int(perfil['fc_base'])}</h2></div>")
    with col_pa: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FF4B4B;'><p style='color:#FF4B4B; margin:0; font-weight:bold;'>PA y (PAM)</p><h2 style='color:#ffffff; margin:0;'>{int(perfil['pa_sistolica'])}/{int(perfil['pa_diastolica'])} <span style='font-size:20px; color:#A0A0A0;'>({int(perfil['pam'])})</span></h2></div>")
    with col_spo2: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00B0FF;'><p style='color:#00B0FF; margin:0; font-weight:bold;'>SpO2 (%)</p><h2 style='color:#ffffff; margin:0;'>{int(perfil['spo2_base'])}</h2></div>")
    with col_pic: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #E040FB;'><p style='color:#E040FB; margin:0; font-weight:bold;'>PIC (mmHg)</p><h2 style='color:#ffffff; margin:0;'>{perfil['pic_base']}</h2></div>")

    st.markdown("---")

    # 2. SCORES CLINICOS PARA ENFERMERIA Y MEDICO
    fr, spo2, fio2, pas, fc, gcs = perfil['fr_resp'], perfil['spo2_base'], perfil['fio2'], perfil['pa_sistolica'], perfil['fc_base'], perfil['gcs']
    
    pts_fr = 3 if fr <= 8 else (1 if 9 <= fr <= 11 else (0 if 12 <= fr <= 20 else (2 if 21 <= fr <= 24 else 3)))
    pts_spo2 = 3 if spo2 <= 91 else (2 if 92 <= spo2 <= 93 else (1 if 94 <= spo2 <= 95 else 0))
    pts_o2 = 2 if fio2 > 21 else 0
    pts_pas = 3 if pas <= 90 else (2 if 91 <= pas <= 100 else (1 if 101 <= pas <= 110 else (0 if 111 <= pas <= 219 else 3)))
    pts_fc = 3 if fc <= 40 else (1 if 41 <= fc <= 50 else (0 if 51 <= fc <= 90 else (1 if 91 <= fc <= 110 else (2 if 111 <= fc <= 130 else 3))))
    pts_gcs = 3 if gcs < 15 else 0

    news2_total = int(pts_fr + pts_spo2 + pts_o2 + pts_pas + pts_fc + pts_gcs)
    parametro_extremo = any(p == 3 for p in [pts_fr, pts_spo2, pts_pas, pts_fc, pts_gcs])

    if news2_total >= 7: color_triage, nivel_triage, accion_triage = "#c0392b", "PRIORIDAD 1", "Respuesta Rapida."
    elif news2_total >= 5 or parametro_extremo: color_triage, nivel_triage, accion_triage = "#f39c12", "PRIORIDAD 2", "Evaluacion Urgente."
    else: color_triage, nivel_triage, accion_triage = "#2ca02c", "PRIORIDAD 3", "Monitorizacion Estandar."

    fi_decimal = fio2 / 100.0
    pa_fi_ratio = perfil['pao2'] / fi_decimal if fi_decimal > 0 else 400
    s_resp = 4 if pa_fi_ratio < 100 else (3 if pa_fi_ratio < 200 else (2 if pa_fi_ratio < 300 else (1 if pa_fi_ratio < 400 else 0)))
    s_cardio = 4 if perfil['pam'] < 60 else (1 if perfil['pam'] < 70 else 0)
    s_neuro = 4 if gcs < 6 else (3 if gcs <= 9 else (2 if gcs <= 12 else (1 if gcs <= 14 else 0)))
    sofa_total = int(s_resp + s_cardio + s_neuro) 
    estado_sofa = "BAJO" if sofa_total <= 3 else ("MODERADO" if sofa_total <= 6 else "SEVERO")

    shock_index = fc / pas if pas > 0 else 0
    rox_index = (spo2 / fi_decimal) / fr if fr > 0 and fi_decimal > 0 else 0

    col_tri, col_sof, col_ind = st.columns([1.5, 1.5, 1])
    with col_tri:
        st.html(f"""<div style="background-color: {color_triage}; padding: 15px; border-radius: 8px; height: 120px;">
        <h5 style="color: white; margin: 0;">Triage (NEWS2): {nivel_triage}</h5>
        <h2 style="color: white; margin: 5px 0;">{news2_total} pts</h2>
        <p style="color: white; font-size: 12px; margin: 0;">Accion: {accion_triage}</p></div>""")
    with col_sof:
        st.html(f"""<div style="background-color: #203a43; padding: 15px; border-radius: 8px; height: 120px; border-left: 8px solid {'#c0392b' if sofa_total > 6 else '#f39c12' if sofa_total > 3 else '#2ca02c'};">
        <h5 style="color: white; margin: 0;">Falla Organica (SOFA): {estado_sofa}</h5>
        <h2 style="color: white; margin: 5px 0;">{sofa_total}/24 pts</h2>
        <p style="color: #a4b0be; font-size: 12px; margin: 0;">Riesgo de mortalidad.</p></div>""")
    with col_ind:
        st.html(f"""<div style="background-color: #1e272e; padding: 10px; border-radius: 8px; margin-bottom: 8px;"><p style="color: #a4b0be; font-size: 11px; margin: 0;">Indice Shock</p><h4 style="color: white; margin: 0;">{shock_index:.2f}</h4></div>""")
        st.html(f"""<div style="background-color: #1e272e; padding: 10px; border-radius: 8px;"><p style="color: #a4b0be; font-size: 11px; margin: 0;">Indice ROX</p><h4 style="color: white; margin: 0;">{rox_index:.2f}</h4></div>""")

    st.markdown("---")

    # 3. GRAFICOS AVANZADOS (MEDICOS)
    st.subheader("Telemetria y Tendencias Historicas")
    df_tendencia_real = perfil['df_tendencia']
    columnas_disponibles = [col for col in ['FC', 'PAM', 'SpO2'] if col in df_tendencia_real.columns]

    if not df_tendencia_real.empty and len(columnas_disponibles) > 0:
        fig_historico = px.line(df_tendencia_real, x='charttime', y=columnas_disponibles, color_discrete_map={'FC': '#00E676', 'PAM': '#FF4B4B', 'SpO2': '#00B0FF'}, markers=True)
        fig_historico.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=250, margin=dict(t=10, b=10))
        st.plotly_chart(fig_historico, use_container_width=True)
    else:
        st.info("Sin registros longitudinales.")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        texto_pa = st.empty()
        espacio_pa = st.empty()
    with col_g2:
        texto_pic = st.empty()
        espacio_pic = st.empty()

    ventana_maxima = 150
    tiempos = collections.deque(maxlen=ventana_maxima)
    datos_pa = collections.deque(maxlen=ventana_maxima)
    datos_pic = collections.deque(maxlen=ventana_maxima)
    omega_cardiaco = 2 * np.pi * (perfil['fc_base'] / 60.0)
    tiempo_inicio = time.time()

    while True:
        tiempo_actual = time.time() - tiempo_inicio
        t_batch = np.linspace(tiempo_actual, tiempo_actual + 0.1, 5)

        onda_pa = perfil['pa_diastolica'] + (perfil['pa_sistolica'] - perfil['pa_diastolica']) * (0.4 * np.sin(omega_cardiaco * t_batch) + 0.3 * np.sin(2 * omega_cardiaco * t_batch))
        onda_pic = perfil['pic_base'] + 3 * (0.5 * np.sin(omega_cardiaco * t_batch))

        for i in range(5):
            tiempos.append(t_batch[i])
            datos_pa.append(onda_pa[i])
            datos_pic.append(onda_pic[i])

        df_pa = pd.DataFrame({"PAI (mmHg)": datos_pa}, index=tiempos)
        df_pic = pd.DataFrame({"PIC (mmHg)": datos_pic}, index=tiempos)

        texto_pa.markdown(f"**PAM Continua:** `{np.mean(datos_pa):.1f} mmHg`")
        espacio_pa.line_chart(df_pa, height=150, color="#FF4B4B")
        texto_pic.markdown(f"**PIC Continua:** `{np.mean(datos_pic):.1f} mmHg`")
        espacio_pic.line_chart(df_pic, height=150, color="#E040FB")

        time.sleep(0.1)