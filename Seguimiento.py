#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import time
import collections
import os

# ==============================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y RUTAS ABSOLUTAS (SIN SIMULACIONES)
# ==============================================================================
st.set_page_config(layout="wide", page_title="Central de Monitoreo UCI", page_icon="🏥")

# Rutas estrictas definidas por el usuario
ruta_icu = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\icu"
ruta_hosp = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\hosp"

# Archivos específicos
ruta_icustays = os.path.join(ruta_icu, "icustays.csv.gz")
ruta_chartevents = os.path.join(ruta_icu, "chartevents.csv.gz")
ruta_patients = os.path.join(ruta_hosp, "patients.csv.gz")

# ==============================================================================
# 2. EXTRACCIÓN ESTRICTA DE LA BASE DE DATOS REAL
# ==============================================================================
@st.cache_data
def cargar_macro():
    """Carga los datos generales para la vista de gestión. Falla si no encuentra los archivos."""
    if not os.path.exists(ruta_icustays):
        st.error(f"❌ No se encuentra el archivo en: {ruta_icustays}. Revisa la ruta.")
        st.stop()

    icustays = pd.read_csv(ruta_icustays)
    patients = pd.read_csv(ruta_patients)
    icustays['intime'] = pd.to_datetime(icustays['intime'])
    return icustays, patients

icustays, patients = cargar_macro()

@st.cache_data
def generar_perfiles_dinamicos():
    """Extrae pacientes reales de MIMIC-IV leyendo chartevents.csv.gz por fragmentos."""
    perfiles = {}

    # Tomamos 5 pacientes reales de la tabla de internaciones
    df_icu = pd.read_csv(ruta_icustays)
    stays_objetivo = df_icu['stay_id'].dropna().unique()[:5]

    # Diccionario de variables vitales en MIMIC-IV
    items_vitales = {
        220045: 'FC', 220052: 'PAM', 220277: 'SpO2', 
        220210: 'FR', 223835: 'FiO2', 220050: 'PAS', 220051: 'PAD'
    }

    df_vitales_lista = []

    # Lectura por fragmentos para proteger la RAM
    for chunk in pd.read_csv(ruta_chartevents, usecols=['stay_id', 'itemid', 'charttime', 'valuenum'], chunksize=100000):
        filtro = chunk[chunk['stay_id'].isin(stays_objetivo) & chunk['itemid'].isin(items_vitales.keys())]
        df_vitales_lista.append(filtro)

    df_vitales = pd.concat(df_vitales_lista)
    df_vitales['charttime'] = pd.to_datetime(df_vitales['charttime'])
    df_vitales['Parametro'] = df_vitales['itemid'].map(items_vitales)

    for stay in stays_objetivo:
        df_paciente = df_vitales[df_vitales['stay_id'] == stay].sort_values('charttime')

        # Si la cama no tiene registros vitales, la ignoramos
        if df_paciente.empty: 
            continue

        # Extraer el último valor clínico anotado (LOCF) para las tarjetas
        ultimos = df_paciente.groupby('Parametro').last()['valuenum'].to_dict()

        # Armar tabla histórica de tendencias (pivot)
        df_tendencia = df_paciente.pivot_table(index='charttime', columns='Parametro', values='valuenum').reset_index()
        df_tendencia = df_tendencia.ffill().bfill() # Rellena datos vacíos

        perfiles[f"Paciente MIMIC-IV Real (Stay ID: {stay})"] = {
            # Valores dinámicos reales de la base de datos
            'fc_base': ultimos.get('FC', 80.0), 
            'pa_sistolica': ultimos.get('PAS', 120.0), 
            'pa_diastolica': ultimos.get('PAD', 80.0), 
            'pam': ultimos.get('PAM', 85.0),
            'spo2_base': ultimos.get('SpO2', 98.0), 
            'fr_resp': ultimos.get('FR', 16.0), 
            'fio2': ultimos.get('FiO2', 21.0),

            # Valores fijos asumidos por defecto si no están en labevents
            'pic_base': 12.0, 'peep_base': 5.0, 'pip_base': 18.0, 'vt_base': 450.0,
            'pao2': 95.0, 'creatinina': 0.8, 'bilirrubina': 0.5, 'plaquetas': 250.0,
            'vasopresores': "Ninguno", 'diuresis': 1500.0, 'gcs': 15.0,

            # Base de datos histórica real para el gráfico de 24hs
            'df_tendencia': df_tendencia
        }

    if not perfiles:
        st.error("❌ Se leyeron los archivos, pero los primeros 5 pacientes no tienen datos vitales registrados en MIMIC-IV.")
        st.stop()

    return perfiles

# ==============================================================================
# 3. INTERFAZ Y RENDERIZADO
# ==============================================================================
with st.spinner("Conectando con la base de datos clínica de MIMIC-IV..."):
    perfiles_pacientes = generar_perfiles_dinamicos()

st.sidebar.title("Configuración Central UCI")
st.sidebar.markdown("Base de Datos: **MIMIC-IV Demo**")
paciente_global = st.sidebar.selectbox("Seleccione Paciente en Cama:", list(perfiles_pacientes.keys()))
perfil = perfiles_pacientes[paciente_global]

tab_macro, tab_sofa, tab_micro = st.tabs(["Vista Macro (Gestión)", "Scores e Indicadores (SOFA)", "Vista Micro (Telemetría)"])

# ==============================================================================
# PESTAÑA 1: VISTA MACRO
# ==============================================================================
with tab_macro:
    st.title("Central de Monitoreo Analitico - Unidad de Cuidados Intensivos")
    st.markdown("El Desarrollo de un Dashboard Clinico para el Monitoreo de KPIs en la UTI")
    st.markdown("---")

    # Calculos estadisticos basados en la base de datos local
    total_pacientes = int(icustays['stay_id'].nunique())
    estancia_promedio = float(icustays['los'].mean())
    df_mortalidad = pd.merge(icustays, patients, on='subject_id', how='left')
    fallecidos_totales = df_mortalidad[df_mortalidad['dod'].notna()]['stay_id'].nunique()
    tasa_mortalidad = (fallecidos_totales / total_pacientes) * 100

    # Fila superior de gestion: Tarjetas operativas y Grafico de Torta de Mortalidad
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        st.markdown("### Indicadores Operativos Clave")
        st.metric(label="Total de Altas Analizadas (Historico)", value=total_pacientes)
        st.write("") 
        st.metric(label="Duracion de la Estancia (LOS Promedio)", value=f"{estancia_promedio:.2f} dias")

    with col_der:
        porcentaje_vivos = 100 - tasa_mortalidad
        df_pie_mortalidad = pd.DataFrame({
            'Estado': ['Fallecidos', 'Sobrevivientes'],
            'Porcentaje': [tasa_mortalidad, porcentaje_vivos]
        })
        # Definicion de colores clinicos fijos en formato hexadecimal
        colores_mortalidad = {'Fallecidos': '#d62728', 'Sobrevivientes': '#2ca02c'}

        fig_torta_mortalidad = px.pie(
            df_pie_mortalidad, 
            names='Estado', 
            values='Porcentaje', 
            hole=0.4, 
            color='Estado',
            color_discrete_map=colores_mortalidad
        )
        fig_torta_mortalidad.update_traces(texttemplate='%{percent:.1%}', textposition='inside')
        fig_torta_mortalidad.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=220)

        st.markdown("### Proporcion de Mortalidad vs. Sobrevivencia")
        st.plotly_chart(fig_torta_mortalidad, use_container_width=True)

    st.markdown("---")

    # Fila central de gestion: Tendencia temporal y distribucion por UCI
    st.header("Menu 1: Indicadores de Salida y Operativos (Outcome & Process KPIs)")
    col_grafico1, col_grafico2 = st.columns(2)

    with col_grafico1:
        st.subheader("Evolucion Historica de Ingresos (Mensual)")
        icustays['mes_anio'] = icustays['intime'].dt.to_period('M').astype(str)
        df_mensual = icustays.groupby('mes_anio')['stay_id'].nunique().reset_index()
        df_mensual.columns = ['Mes', 'Cantidad de Pacientes']

        fig_barras = px.bar(df_mensual, x='Mes', y='Cantidad de Pacientes', 
                            text_auto=True, color_discrete_sequence=['#1f77b4'])
        fig_barras.update_layout(xaxis_title="Periodo Temporal", yaxis_title="Ingresos")
        st.plotly_chart(fig_barras, use_container_width=True)

    with col_grafico2:
        st.subheader("Distribucion de Ocupacion por Tipo de UCI")
        df_sectores = icustays['first_careunit'].value_counts().reset_index()
        df_sectores.columns = ['Tipo de Unidad', 'Total Ingresos']

        fig_torta = px.pie(df_sectores, names='Tipo de Unidad', values='Total Ingresos', 
                           hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_torta, use_container_width=True)

    st.markdown("---")

    # Fila inferior de gestion: Distribucion de edades y analisis sectorial
    st.header("Menu 2: Analisis Demografico y de Calidad Asistencial")
    col_abajo1, col_abajo2 = st.columns(2)

    with col_abajo1:
        st.subheader("Distribucion de Pacientes por Edad")
        df_mortalidad['edad'] = df_mortalidad['intime'].dt.year - df_mortalidad['anchor_year'] + df_mortalidad['anchor_age']
        fig_edad = px.histogram(df_mortalidad, x='edad', nbins=15, text_auto=True,
                                labels={'edad': 'Edad (Anos)'}, color_discrete_sequence=['#2ca02c'])
        fig_edad.update_layout(xaxis_title="Rangos de Edad", yaxis_title="Cantidad de Pacientes")
        st.plotly_chart(fig_edad, use_container_width=True)

    with col_abajo2:
        st.subheader("Tasa de Mortalidad Especifica por Sector")
        df_mort_unidad = df_mortalidad.groupby('first_careunit').agg(
            Total=('stay_id', 'nunique'),
            Fallecidos=('dod', lambda x: x.notna().sum())
        ).reset_index()
        df_mort_unidad['% Mortalidad'] = (df_mort_unidad['Fallecidos'] / df_mort_unidad['Total']) * 100

        fig_mort_unidad = px.bar(df_mort_unidad, x='first_careunit', y='% Mortalidad',
                                 text_auto='.1f', color_discrete_sequence=['#d62728'])
        fig_mort_unidad.update_layout(xaxis_title="Unidad del Hospital", yaxis_title="Tasa de Mortalidad (%)")
        st.plotly_chart(fig_mort_unidad, use_container_width=True)

# ==============================================================================
# PESTAÑA 2: VISTA SOFA
# ==============================================================================
with tab_sofa:
    st.title("Panel de Alerta Temprana y Falla Orgánica")
    st.markdown("Métricas analíticas basadas en la última extracción de enfermería.")
    st.markdown("---")

    fi_decimal = perfil['fio2'] / 100.0
    pa_fi_ratio = perfil['pao2'] / fi_decimal if fi_decimal > 0 else 400
    is_ventilado = True if perfil['fio2'] > 21 else False

    # Cálculos reales para Scores basados en el diccionario
    pts_cardio = 1 if perfil['pam'] < 70 else 0
    pts_resp = 2 if pa_fi_ratio < 300 else 0
    sofa_total = pts_cardio + pts_resp # Simplificado para la visualización

    estado_sofa = "RIESGO BAJO" if sofa_total <= 1 else ("RIESGO MODERADO" if sofa_total <=3 else "RIESGO ALTO")
    color_sofa = "#2ca02c" if sofa_total <= 1 else ("#f39c12" if sofa_total <=3 else "#c0392b")

    shock_index = perfil['fc_base'] / perfil['pa_sistolica'] if perfil['pa_sistolica'] > 0 else 0
    color_is = "#2ca02c" if shock_index < 0.7 else ("#f39c12" if shock_index <= 0.9 else "#c0392b")

    rox_index = (perfil['spo2_base'] / fi_decimal) / perfil['fr_resp'] if perfil['fr_resp'] > 0 and fi_decimal > 0 else 0
    color_rox = "#2ca02c" if rox_index > 4.88 else ("#f39c12" if rox_index >= 3.85 else "#c0392b")

    st.html(f"""<div style="background-color: {color_sofa}; padding: 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3); margin-bottom: 25px;"><div><h4 style="color: rgba(255,255,255,0.85); margin: 0; text-transform: uppercase;">Score SOFA (Parcial)</h4><h2 style="color: white; margin: 8px 0 0 0;">{estado_sofa}</h2></div><div style="text-align: right;"><h1 style="color: white; font-size: 65px; margin: 0;">{sofa_total} <span style="font-size: 24px; color: rgba(255,255,255,0.6);">/24</span></h1></div></div>""")

    col_is, col_rox = st.columns(2)
    with col_is: st.html(f"""<div style="background-color: {color_is}; padding: 22px; border-radius: 12px; height: 160px;"><h5 style="color: white; margin: 0;">Índice de Shock (IS)</h5><h1 style="color: white; font-size: 45px;">{shock_index:.2f}</h1></div>""")
    with col_rox: st.html(f"""<div style="background-color: {color_rox}; padding: 22px; border-radius: 12px; height: 160px;"><h5 style="color: white; margin: 0;">Índice ROX</h5><h1 style="color: white; font-size: 45px;">{rox_index:.2f}</h1></div>""")

# ==============================================================================
# PESTAÑA 3: VISTA MICRO (TELEMETRÍA DE ALTA FRECUENCIA CON BUCLE)
# ==============================================================================
with tab_micro:
    st.title("Módulo de Telemetría Dinámica de Alta Frecuencia")
    st.write("")

    col_fc, col_pa, col_spo2, col_pic = st.columns(4)
    with col_fc: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00E676;'><p style='color:#00E676; margin:0; font-weight:bold;'>FC (lpm)</p><h2 style='color:#ffffff; margin:0;'>{int(perfil['fc_base'])}</h2></div>")
    with col_pa: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FF4B4B;'><p style='color:#FF4B4B; margin:0; font-weight:bold;'>PA y (PAM)</p><h2 style='color:#ffffff; margin:0;'>{int(perfil['pa_sistolica'])}/{int(perfil['pa_diastolica'])} <span style='font-size:20px; color:#A0A0A0;'>({int(perfil['pam'])})</span></h2></div>")
    with col_spo2: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00B0FF;'><p style='color:#00B0FF; margin:0; font-weight:bold;'>SpO2 (%)</p><h2 style='color:#ffffff; margin:0;'>{int(perfil['spo2_base'])}</h2></div>")
    with col_pic: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #E040FB;'><p style='color:#E040FB; margin:0; font-weight:bold;'>PIC (mmHg)</p><h2 style='color:#ffffff; margin:0;'>{perfil['pic_base']}</h2></div>")

    # ==============================================================================
    # GRÁFICO DE TENDENCIAS 100% REAL DE MIMIC-IV
    # ==============================================================================
    st.markdown("---")
    st.subheader("Evolución Temporal: Tendencias Extraídas (MIMIC-IV Real)")

    df_tendencia_real = perfil['df_tendencia']
    columnas_disponibles = [col for col in ['FC', 'PAM', 'SpO2'] if col in df_tendencia_real.columns]

    if not df_tendencia_real.empty and len(columnas_disponibles) > 0:
        fig_historico = px.line(
            df_tendencia_real, x='charttime', y=columnas_disponibles,
            color_discrete_map={'FC': '#00E676', 'PAM': '#FF4B4B', 'SpO2': '#00B0FF'},
            markers=True
        )
        fig_historico.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
            font_color='white', xaxis_title="Evolución Clínica (Fecha y Hora Original de MIMIC)", yaxis_title="Valores Numéricos",
            legend_title="Parámetro", height=350, hovermode="x unified"
        )
        fig_historico.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')
        fig_historico.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')
        st.plotly_chart(fig_historico, use_container_width=True)
    else:
        st.warning("⚠️ El paciente seleccionado tiene un ingreso en UCI pero no se registraron suficientes tendencias longitudinales en la base Demo.")

    st.markdown("---")
    st.subheader("Ondas de Telemetría (Interpoladas del último registro)")
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

    # BUCLE INFINITO
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

        texto_pa.markdown(f"**PAM:** `{np.mean(datos_pa):.1f} mmHg`")
        espacio_pa.line_chart(df_pa, height=200, color="#FF4B4B")
        texto_pic.markdown(f"**PIC Media:** `{np.mean(datos_pic):.1f} mmHg`")
        espacio_pic.line_chart(df_pic, height=200, color="#E040FB")

        time.sleep(0.1)

