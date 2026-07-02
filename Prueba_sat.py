#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import time
import collections
import os

# ==============================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y RUTAS
# ==============================================================================
st.set_page_config(layout="wide", page_title="Central de Monitoreo UCI", page_icon="🏥")

ruta_base = os.path.dirname(__file__)
ruta_icustays = os.path.join(ruta_base, "DataBase", "mimic-iv-clinical-database-demo-2.2", "mimic-iv-clinical-database-demo-2.2", "icu", "icustays.csv.gz")
ruta_patients = os.path.join(ruta_base, "DataBase", "mimic-iv-clinical-database-demo-2.2", "mimic-iv-clinical-database-demo-2.2", "hosp", "patients.csv.gz")

# ==============================================================================
# 2. CARGA DE DATOS HISTÓRICOS (FALLBACK INTEGRADO)
# ==============================================================================
@st.cache_data
def cargar_datos_hospitalarios():
    try:
        icustays = pd.read_csv(ruta_icustays)
        patients = pd.read_csv(ruta_patients)
        icustays['intime'] = pd.to_datetime(icustays['intime'])
        return icustays, patients
    except FileNotFoundError:
        df_icu_mock = pd.DataFrame({
            'stay_id': range(1000, 1150), 'subject_id': range(5000, 5150),
            'los': np.random.gamma(4, 1, 150), 'intime': pd.date_range(start="2026-01-01", periods=150, freq="D"),
            'first_careunit': np.random.choice(['Medical Intensive Care Unit (MICU)', 'Surgical Intensive Care Unit (SICU)', 'Cardiac Vascular ICU (CVICU)'], 150)
        })
        df_pat_mock = pd.DataFrame({
            'subject_id': range(5000, 5150), 'anchor_age': np.random.randint(18, 90, 150), 'anchor_year': [2026]*150,
            'dod': [None if np.random.rand() > 0.15 else "2026-03-01" for _ in range(150)]
        })
        return df_icu_mock, df_pat_mock

icustays, patients = cargar_datos_hospitalarios()

# ==============================================================================
# 3. CONTROLLER CENTRALIZADO (SELECCIÓN UNIFICADA Y FIJA)
# ==============================================================================
st.sidebar.title("Configuración Central UCI")
st.sidebar.markdown("Elija el paciente para sincronizar toda la estación de monitoreo.")

# Base de datos centralizada de perfiles fijos (MIMIC-IV Mockups)
perfiles_pacientes = {
    "Paciente: Juan - ID: 5676 - DX: HSA": {
        'fc_base': 75.0, 'pa_sistolica': 120, 'pa_diastolica': 80, 'spo2_base': 98.0, 'pic_base': 12.0,
        'fr_resp': 14.0, 'peep_base': 5.0, 'pip_base': 18.0, 'fio2': 21, 'vt_base': 450,
        'pao2': 95, 'creatinina': 0.8, 'bilirrubina': 0.5, 'plaquetas': 250,
        'vasopresores': "Ninguno", 'diuresis': 1500, 'gcs': 15,
        'pam': 80  # <-- AGREGA ESTA LÍNEA
    },
    "Paciente: Laura - ID: 7421 - DX: Trauma": {
        'fc_base': 95.0, 'pa_sistolica': 135, 'pa_diastolica': 90, 'spo2_base': 94.0, 'pic_base': 18.0,
        'fr_resp': 22.0, 'peep_base': 8.0, 'pip_base': 26.0, 'fio2': 60, 'vt_base': 380,
        'pao2': 65, 'creatinina': 3.1, 'bilirrubina': 2.8, 'plaquetas': 45,
        'vasopresores': "Dopamina > 15 o Adrenalina > 0.1 o Noradrenalina > 0.1", 'diuresis': 300, 'gcs': 11,
        'pam': 55  # <-- AGREGA ESTA LÍNEA
    }
}
# ÚNICO Selector en la barra lateral para toda la aplicación
paciente_global = st.sidebar.selectbox(
    "Seleccione Cama Clínico/Telemetría:", 
    list(perfiles_pacientes.keys())
)

perfil = perfiles_pacientes[paciente_global]

# Mostrar los datos fijos del paciente seleccionado en la barra lateral como información estática
st.sidebar.markdown("---")
st.sidebar.markdown("### Registro Fisiológico (Fijo)")
st.sidebar.info(
    f"**FC:** {int(perfil['fc_base'])} lpm\n\n"
    f"**PA:** {int(perfil['pa_sistolica'])}/{int(perfil['pa_diastolica'])} mmHg\n\n"
    f"**SpO2:** {int(perfil['spo2_base'])} %\n\n"
    f"**FiO2:** {int(perfil['fio2'])} %\n\n"
    f"**GCS (Glasgow):** {int(perfil['gcs'])}/15\n\n"
    f"**Plaquetas:** {int(perfil['plaquetas'])} x10³/µL\n\n"
    f"**Creatinina:** {perfil['creatinina']} mg/dL"
)

# ==============================================================================
# 4. DECLARACIÓN DE PESTAÑAS (ORDEN DE EJECUCIÓN)
# ==============================================================================
tab_macro, tab_sofa, tab_micro = st.tabs([
    "Vista Macro - Gestión Hospitalaria", 
    "Scores e Indicadores Clínicos",
    "Vista Micro - Monitor de Señales"
])

# ==============================================================================
# PESTAÑA 1: VISTA MACRO (GESTIÓN HOSPITALARIA)
# ==============================================================================
with tab_macro:
    st.title("Central de Monitoreo Analítico - Unidad de Cuidados Intensivos")
    st.markdown("---")

    total_pacientes = int(icustays['stay_id'].nunique())
    estancia_promedio = float(icustays['los'].mean())
    df_mortalidad = pd.merge(icustays, patients, on='subject_id', how='left')
    fallecidos_totales = df_mortalidad[df_mortalidad['dod'].notna()]['stay_id'].nunique()
    tasa_mortalidad = (fallecidos_totales / total_pacientes) * 100

    col_izq, col_der = st.columns([1, 1])
    with col_izq:
        st.metric(label="Total de Altas Analizadas (Histórico)", value=total_pacientes)
        st.write("") 
        st.metric(label="Duración de la Estancia (LOS Promedio)", value=f"{estancia_promedio:.2f} días")

    with col_der:
        df_pie_mortalidad = pd.DataFrame({'Estado': ['Fallecidos', 'Sobrevivientes'], 'Porcentaje': [tasa_mortalidad, 100 - tasa_mortalidad]})
        fig_torta_mortalidad = px.pie(df_pie_mortalidad, names='Estado', values='Porcentaje', hole=0.4, color='Estado', color_discrete_map={'Fallecidos': '#d62728', 'Sobrevivientes': '#2ca02c'})
        fig_torta_mortalidad.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200)
        st.plotly_chart(fig_torta_mortalidad, use_container_width=True)

    st.markdown("---")
    col_grafico1, col_grafico2 = st.columns(2)
    with col_grafico1:
        icustays['mes_anio'] = icustays['intime'].dt.to_period('M').astype(str)
        df_mensual = icustays.groupby('mes_anio')['stay_id'].nunique().reset_index()
        df_mensual.columns = ['Mes', 'Cantidad de Pacientes']
        fig_barras = px.bar(df_mensual, x='Mes', y='Cantidad de Pacientes', text_auto=True, color_discrete_sequence=['#1f77b4'])
        st.plotly_chart(fig_barras, use_container_width=True)
    with col_grafico2:
        df_sectores = icustays['first_careunit'].value_counts().reset_index()
        df_sectores.columns = ['Tipo de Unidad', 'Total Ingresos']
        fig_torta = px.pie(df_sectores, names='Tipo de Unidad', values='Total Ingresos', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_torta, use_container_width=True)

# ==============================================================================
# PESTAÑA 2: VISTA SOFA E INDICADORES CLÍNICOS (DATOS FIJOS AUTOCALCULADOS)
# ==============================================================================
with tab_sofa:
    st.title("Panel de Alerta Temprana y Falla Orgánica")
    st.markdown("Métricas analíticas calculadas automáticamente a partir del perfil seleccionado en el menú principal.")
    st.markdown("---")

    # Extracción matemática basada en el perfil inalterable
    fi_decimal = perfil['fio2'] / 100.0
    pa_fi_ratio = perfil['pao2'] / fi_decimal if fi_decimal > 0 else 400
    is_ventilado = True if perfil['fio2'] > 21 else False

    # Puntos SOFA
    pts_resp = 4 if pa_fi_ratio < 100 and is_ventilado else (3 if pa_fi_ratio < 200 and is_ventilado else (2 if pa_fi_ratio < 300 else (1 if pa_fi_ratio < 400 else 0)))
    pts_coag = 4 if perfil['plaquetas'] < 20 else (3 if perfil['plaquetas'] < 50 else (2 if perfil['plaquetas'] < 100 else (1 if perfil['plaquetas'] < 150 else 0)))
    pts_hep = 4 if perfil['bilirrubina'] >= 12.0 else (3 if perfil['bilirrubina'] >= 6.0 else (2 if perfil['bilirrubina'] >= 2.0 else (1 if perfil['bilirrubina'] >= 1.2 else 0)))

    pts_cardio = 0
    if perfil['vasopresores'] == "Dopamina > 15 o Adrenalina > 0.1 o Noradrenalina > 0.1": pts_cardio = 4
    elif perfil['vasopresores'] == "Dopamina > 5 o Adrenalina ≤ 0.1 o Noradrenalina ≤ 0.1": pts_cardio = 3
    elif perfil['vasopresores'] == "Dopamina ≤ 5 o Dobutamina (Cualquier dosis)": pts_cardio = 2
    elif perfil['pam'] < 70: pts_cardio = 1  # <-- ASÍ DEBE QUEDAR LA LÍNEA CORREGIDA

    pts_neuro = 4 if perfil['gcs'] < 6 else (3 if perfil['gcs'] <= 9 else (2 if perfil['gcs'] <= 12 else (1 if perfil['gcs'] <= 14 else 0)))
    pts_renal = 4 if perfil['creatinina'] >= 5.0 or perfil['diuresis'] < 200 else (3 if perfil['creatinina'] >= 3.5 or perfil['diuresis'] < 500 else (2 if perfil['creatinina'] >= 2.0 else (1 if perfil['creatinina'] >= 1.2 else 0)))

    sofa_total = pts_resp + pts_coag + pts_hep + pts_cardio + pts_neuro + pts_renal

    if sofa_total <= 6: color_sofa, estado_sofa = "#2ca02c", "RIESGO BAJO - Monitorización Estándar"
    elif sofa_total <= 9: color_sofa, estado_sofa = "#f39c12", "RIESGO MODERADO - Disfunción Orgánica"
    elif sofa_total <= 14: color_sofa, estado_sofa = "#d35400", "RIESGO ALTO - Falla Multiorgánica Severa"
    else: color_sofa, estado_sofa = "#c0392b", "RIESGO CRÍTICO - Pronóstico Reservado"

    # Índices Predictivos
    shock_index = perfil['fc_base'] / perfil['pa_sistolica']
    color_is = "#2ca02c" if shock_index < 0.7 else ("#f39c12" if shock_index <= 0.9 else "#c0392b")
    estado_is = "NORMAL" if shock_index < 0.7 else ("ALERTA - Shock Oculto" if shock_index <= 0.9 else "CRÍTICO - Inestabilidad Grave")

    rox_index = (perfil['spo2_base'] / fi_decimal) / perfil['fr_resp']
    color_rox = "#2ca02c" if rox_index > 4.88 else ("#f39c12" if rox_index >= 3.85 else "#c0392b")
    estado_rox = "ÉXITO PROBABLE" if rox_index > 4.88 else ("VIGILANCIA ESTRICTA" if rox_index >= 3.85 else "ALTO RIESGO DE FALLO")

    # Renderizado en Pantalla
    st.html(f"""
    <div style="background-color: {color_sofa}; padding: 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3); margin-bottom: 25px;">
        <div><h4 style="color: rgba(255,255,255,0.85); margin: 0; text-transform: uppercase;">Score SOFA Acumulado</h4><h2 style="color: white; margin: 8px 0 0 0; font-weight: 500;">{estado_sofa}</h2></div>
        <div style="text-align: right;"><h1 style="color: white; font-size: 65px; margin: 0; line-height: 1; font-weight: bold;">{sofa_total} <span style="font-size: 24px; color: rgba(255,255,255,0.6);">/24</span></h1></div>
    </div>
    """)

    col_is, col_rox = st.columns(2)
    with col_is:
        st.html(f"""<div style="background-color: {color_is}; padding: 22px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); height: 160px;"><h5 style="color: rgba(255,255,255,0.85); margin: 0; text-transform: uppercase;">Índice de Shock (IS)</h5><h1 style="color: white; font-size: 45px; margin: 8px 0;">{shock_index:.2f}</h1><p style="color: white; font-size: 14px; margin: 0;">{estado_is}</p></div>""")
    with col_rox:
        st.html(f"""<div style="background-color: {color_rox}; padding: 22px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); height: 160px;"><h5 style="color: rgba(255,255,255,0.85); margin: 0; text-transform: uppercase;">Índice ROX</h5><h1 style="color: white; font-size: 45px; margin: 8px 0;">{rox_index:.2f}</h1><p style="color: white; font-size: 14px; margin: 0;">{estado_rox}</p></div>""")

    st.markdown("---")
    st.subheader("Desglose Clínico por Sistemas")
    df_desglose_sofa = pd.DataFrame({
        "Sistema Evaluado": ["Respiratorio", "Coagulación", "Hepático", "Cardiovascular", "Neurológico", "Renal"],
        "Puntos": [pts_resp, pts_coag, pts_hep, pts_cardio, pts_neuro, pts_renal],
        "Marcadores de la Ventana": [f"PaO2/FiO2: {pa_fi_ratio:.1f} mmHg", f"Plaquetas: {perfil['plaquetas']} x10³/µL", f"Bilirrubina: {perfil['bilirrubina']} mg/dL", f"PAM: {perfil['pam']} mmHg / Vasopresor: {perfil['vasopresores']}", f"Glasgow: {perfil['gcs']}/15", f"Creatinina: {perfil['creatinina']} mg/dL"]
    })
    st.dataframe(df_desglose_sofa, use_container_width=True, hide_index=True)

# ==============================================================================
# PESTAÑA 3: VISTA MICRO (TELEMETRÍA DE ALTA FRECUENCIA CON BUCLE EN EL CIERRE)
# ==============================================================================
with tab_micro:
    st.title("Módulo de Telemetría Dinámica de Alta Frecuencia")
    st.markdown("Simulación continua de formas de onda fisiológicas y curvas mecánicas del respirador.")
    st.write("")

    # Extracción de variables locales para el bucle de ondas desde el perfil global unificado
    fc_base = perfil['fc_base']
    pa_sistolica = perfil['pa_sistolica']
    pa_diastolica = perfil['pa_diastolica']
    spo2_base = perfil['spo2_base']
    pic_base = perfil['pic_base']
    fr_resp = perfil['fr_resp']
    peep_base = perfil['peep_base']
    pip_base = perfil['pip_base']

    # Paneles de control numérico superiores
    col_fc, col_pa, col_spo2, col_pic = st.columns(4)
    with col_fc: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00E676;'><p style='color:#00E676; margin:0; font-weight:bold;'>FC (lpm)</p><h2 style='color:#ffffff; margin:0;'>{int(fc_base)}</h2></div>")
    with col_pa: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FF4B4B;'><p style='color:#FF4B4B; margin:0; font-weight:bold;'>PA (mmHg)</p><h2 style='color:#ffffff; margin:0;'>{int(pa_sistolica)}/{int(pa_diastolica)}</h2></div>")
    with col_spo2: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00B0FF;'><p style='color:#00B0FF; margin:0; font-weight:bold;'>SpO2 (%)</p><h2 style='color:#ffffff; margin:0;'>{int(spo2_base)}</h2></div>")
    with col_pic: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #E040FB;'><p style='color:#E040FB; margin:0; font-weight:bold;'>PIC (mmHg)</p><h2 style='color:#ffffff; margin:0;'>{pic_base}</h2></div>")

    # Inicialización de deques para el efecto barrido
    ventana_maxima = 150
    tiempos = collections.deque(maxlen=ventana_maxima)
    datos_pa = collections.deque(maxlen=ventana_maxima)
    datos_pic = collections.deque(maxlen=ventana_maxima)
    datos_paw = collections.deque(maxlen=ventana_maxima)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        texto_tendencia_pa = st.empty()
        espacio_pa = st.empty()
    with col_g2:
        texto_tendencia_pic = st.empty()
        espacio_pic = st.empty()

    st.subheader("Curva de Presión en Vía Aérea (Paw)")
    texto_tendencia_paw = st.empty()
    espacio_paw = st.empty()

    # Parámetros mecánicos
    omega_cardiaco = 2 * np.pi * (fc_base / 60.0)
    periodo_respiratorio = 60.0 / fr_resp
    tiempo_inspiracion = periodo_respiratorio / 3.0
    tiempo_inicio = time.time()

    # BUCLE DE TELEMETRÍA - AL FINAL ABSOLUTO DEL DOCUMENTO
    while True:
        tiempo_actual = time.time() - tiempo_inicio
        t_batch = np.linspace(tiempo_actual, tiempo_actual + 0.1, 5)

        # Ondas cardíacas
        onda_pa = pa_diastolica + (pa_sistolica - pa_diastolica) * (
            0.4 * np.sin(omega_cardiaco * t_batch) + 0.3 * np.sin(2 * omega_cardiaco * t_batch) + 0.15 * np.sin(3 * omega_cardiaco * t_batch)
        )
        onda_pa = np.clip(onda_pa, pa_diastolica - 5, pa_sistolica + 5)
        onda_pic = pic_base + 3 * (0.5 * np.sin(omega_cardiaco * t_batch) + 0.2 * np.sin(2 * omega_cardiaco * t_batch))

        # Onda del respirador
        onda_paw = np.zeros_like(t_batch)
        for i in range(len(t_batch)):
            t_mod = t_batch[i] % periodo_respiratorio
            if t_mod < tiempo_inspiracion:
                onda_paw[i] = peep_base + (pip_base - peep_base) * np.sin((np.pi/2) * (t_mod / tiempo_inspiracion))
            else:
                onda_paw[i] = peep_base + (pip_base - peep_base) * np.exp(-3 * (t_mod - tiempo_inspiracion))

        # Empujar datos a las colas deslizantes
        for i in range(5):
            tiempos.append(t_batch[i])
            datos_pa.append(onda_pa[i])
            datos_pic.append(onda_pic[i])
            datos_paw.append(onda_paw[i])

        df_pa = pd.DataFrame({"PAI (mmHg)": datos_pa}, index=tiempos)
        df_pic = pd.DataFrame({"PIC (mmHg)": datos_pic}, index=tiempos)
        df_paw = pd.DataFrame({"Paw (cmH2O)": datos_paw}, index=tiempos)

        # Actualización de renders en contenedores fijos
        texto_tendencia_pa.markdown(f"**PAM:** `{np.mean(datos_pa):.1f} mmHg`")
        espacio_pa.line_chart(df_pa, height=200, color="#FF4B4B")

        texto_tendencia_pic.markdown(f"**PIC Media:** `{np.mean(datos_pic):.1f} mmHg`")
        espacio_pic.line_chart(df_pic, height=200, color="#E040FB")

        texto_tendencia_paw.markdown(f"**MAP (Presión Media Vía Aérea):** `{np.mean(datos_paw):.1f} cmH2O`")
        espacio_paw.line_chart(df_paw, height=200, color="#FFC107")

        time.sleep(0.1)


# In[ ]:




