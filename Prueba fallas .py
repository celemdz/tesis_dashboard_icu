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

# Configuracion de pagina ancha para diseño de tablero industrial
st.set_page_config(layout="wide")

# Rutas locales de la base de datos MIMIC-IV Clinical Demo
ruta_icustays = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\icu\icustays.csv.gz"
ruta_patients = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\hosp\patients.csv.gz"

@st.cache_data
def cargar_datos():
    # Lectura de tablas comprimidas utilizando pandas
    icustays = pd.read_csv(ruta_icustays)
    patients = pd.read_csv(ruta_patients)
    # Conversion de la columna de ingreso a formato datetime
    icustays['intime'] = pd.to_datetime(icustays['intime'])
    return icustays, patients

# Inicializacion de los dataframes globales
icustays, patients = cargar_datos()

# ESTRUCTURA DE PÁGINA: NAVEGACIÓN POR PESTAÑAS INTEGRADAS
tab_macro, tab_micro = st.tabs(["Vista Macro - Gestion Hospitalaria", "Vista Micro - Monitor de Senales"])

# ==============================================================================
# PESTAÑA 1: VISTA MACRO (GESTIÓN HOSPITALARIA)
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

    # Fila superior de gestion
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

    # Fila central de gestion
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

    # Fila inferior de gestion
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
# PESTAÑA 2: VISTA MICRO (MONITOR DE SEÑALES MULTIPARAMÉTRICO)
# ==============================================================================
with tab_micro:
    st.title("Neuromonitoring Dashboard v4.0 - Telemetría y Ventilación")
    st.markdown("Modulo Integrado para el Analisis de Senales en Alta Frecuencia (Inyección de Datos)")

    # 1. SELECCIÓN DE PACIENTE Y PERFILES
    st.sidebar.markdown("### Seleccion de Paciente (MIMIC-IV)")
    paciente_seleccionado = st.sidebar.selectbox(
        "Seleccione la cama a monitorizar:",
        ["Paciente: Juan - ID: 5676 - DX: HSA", "Paciente: Maria - ID: 7421 - DX: Trauma"]
    )

    # Perfil hemodinámico y ventilatorio combinado
    if "Juan" in paciente_seleccionado:
        # Hemodinamia
        fc_base, pa_sistolica, pa_diastolica, spo2_base, pic_base = 75.0, 120, 80, 98.0, 12.0
        # Respirador (Parámetros protectivos normales)
        fr_resp, peep_base, pip_base, fio2, vt_base = 14.0, 5.0, 18.0, 40, 450
    else:
        # Hemodinamia
        fc_base, pa_sistolica, pa_diastolica, spo2_base, pic_base = 95.0, 135, 90, 94.0, 18.0
        # Respirador (Paciente con trauma / SDRA leve)
        fr_resp, peep_base, pip_base, fio2, vt_base = 22.0, 8.0, 26.0, 60, 380

    # 2. PANELES NUMÉRICOS FRONTALES
    st.markdown("### Parámetros Hemodinámicos")
    col_fc, col_pa, col_spo2, col_pic = st.columns(4)
    with col_fc: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00E676;'><p style='color:#00E676; margin:0; font-weight:bold;'>FC (lpm)</p><h2 style='color:#ffffff; margin:0;'>{int(fc_base)}</h2></div>")
    with col_pa: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FF4B4B;'><p style='color:#FF4B4B; margin:0; font-weight:bold;'>PA (mmHg)</p><h2 style='color:#ffffff; margin:0;'>{pa_sistolica}/{pa_diastolica}</h2></div>")
    with col_spo2: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00B0FF;'><p style='color:#00B0FF; margin:0; font-weight:bold;'>SpO2 (%)</p><h2 style='color:#ffffff; margin:0;'>{int(spo2_base)}</h2></div>")
    with col_pic: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #E040FB;'><p style='color:#E040FB; margin:0; font-weight:bold;'>PIC (mmHg)</p><h2 style='color:#ffffff; margin:0;'>{pic_base}</h2></div>")

    st.markdown("### Parámetros Ventilatorios (Seteos del Equipo)")
    col_fr, col_peep, col_pip, col_vt = st.columns(4)
    with col_fr: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FFC107;'><p style='color:#FFC107; margin:0; font-weight:bold;'>FR (rpm)</p><h2 style='color:#ffffff; margin:0;'>{int(fr_resp)}</h2></div>")
    with col_peep: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FFC107;'><p style='color:#FFC107; margin:0; font-weight:bold;'>PEEP (cmH2O)</p><h2 style='color:#ffffff; margin:0;'>{peep_base}</h2></div>")
    with col_pip: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FFC107;'><p style='color:#FFC107; margin:0; font-weight:bold;'>P. Pico (cmH2O)</p><h2 style='color:#ffffff; margin:0;'>{pip_base}</h2></div>")
    with col_vt: st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FFC107;'><p style='color:#FFC107; margin:0; font-weight:bold;'>Vol. Tidal (mL)</p><h2 style='color:#ffffff; margin:0;'>{vt_base}</h2></div>")
    st.write("")

    # 3. CONFIGURACIÓN DE LAS VENTANAS DESLIZANTES (COLAS)
    ventana_maxima = 150 
    tiempos = collections.deque(maxlen=ventana_maxima)
    datos_pa = collections.deque(maxlen=ventana_maxima)
    datos_pic = collections.deque(maxlen=ventana_maxima)
    datos_paw = collections.deque(maxlen=ventana_maxima) # Nueva cola para el respirador

    # 4. CREACIÓN DE LOS CONTENEDORES DE GRÁFICOS
    st.subheader("Hemodinamia y Neuromonitoreo")
    col_graf_izq, col_graf_der = st.columns(2)
    with col_graf_izq:
        texto_tendencia_pa = st.empty()
        espacio_pa = st.empty()
    with col_graf_der:
        texto_tendencia_pic = st.empty()
        espacio_pic = st.empty()

    st.subheader("Curva de Presión de Vía Aérea (Respirador)")
    texto_tendencia_paw = st.empty()
    espacio_paw = st.empty()

    # 5. VARIABLES MATEMÁTICAS INICIALES
    omega_cardiaco = 2 * np.pi * (fc_base / 60.0)
    periodo_respiratorio = 60.0 / fr_resp # Segundos que dura un ciclo respiratorio completo
    tiempo_inspiracion = periodo_respiratorio / 3.0 # Asumimos relación I:E normal de 1:2
    tiempo_inicio = time.time()

    # 6. BUCLE DE TELEMETRÍA (INYECCIÓN CONTINUA)
    while True:
        tiempo_actual = time.time() - tiempo_inicio
        t_batch = np.linspace(tiempo_actual, tiempo_actual + 0.1, 5)

        # --- Cálculo Hemodinámico (Ondas de Fourier) ---
        onda_pa = pa_diastolica + (pa_sistolica - pa_diastolica) * (
            0.4 * np.sin(omega_cardiaco * t_batch) + 
            0.3 * np.sin(2 * omega_cardiaco * t_batch) + 
            0.15 * np.sin(3 * omega_cardiaco * t_batch)
        )
        onda_pa = np.clip(onda_pa, pa_diastolica - 5, pa_sistolica + 5)

        onda_pic = pic_base + 3 * (
            0.5 * np.sin(omega_cardiaco * t_batch) + 
            0.2 * np.sin(2 * omega_cardiaco * t_batch)
        )

        # --- Cálculo Ventilatorio (Ciclo Mecánico) ---
        onda_paw = np.zeros_like(t_batch)
        for i in range(len(t_batch)):
            t_mod = t_batch[i] % periodo_respiratorio # En qué momento del ciclo respiratorio estamos
            if t_mod < tiempo_inspiracion:
                # Fase Inspiratoria: El ventilador empuja aire, sube de PEEP a PIP (Curva senoidal)
                onda_paw[i] = peep_base + (pip_base - peep_base) * np.sin((np.pi/2) * (t_mod / tiempo_inspiracion))
            else:
                # Fase Espiratoria: La válvula se abre, la presión cae exponencialmente hacia PEEP
                onda_paw[i] = peep_base + (pip_base - peep_base) * np.exp(-3 * (t_mod - tiempo_inspiracion))

        # --- Inserción en las Colas ---
        for i in range(5):
            tiempos.append(t_batch[i])
            datos_pa.append(onda_pa[i])
            datos_pic.append(onda_pic[i])
            datos_paw.append(onda_paw[i])

        # --- Armado de DataFrames ---
        df_pa = pd.DataFrame({"PAI (mmHg)": datos_pa}, index=tiempos)
        df_pic = pd.DataFrame({"PIC (mmHg)": datos_pic}, index=tiempos)
        df_paw = pd.DataFrame({"Paw (cmH2O)": datos_paw}, index=tiempos)

        # --- Cálculos de Tendencia ---
        pam_actual = np.mean(datos_pa)
        pic_media_actual = np.mean(datos_pic)
        map_respiratoria = np.mean(datos_paw) # Mean Airway Pressure (Presión Media en Vía Aérea)

        # --- Renderizado en Interfaz ---
        texto_tendencia_pa.markdown(f"**PAM:** `{pam_actual:.1f} mmHg`")
        espacio_pa.line_chart(df_pa, height=200, color="#FF4B4B")

        texto_tendencia_pic.markdown(f"**PIC Media:** `{pic_media_actual:.1f} mmHg`")
        espacio_pic.line_chart(df_pic, height=200, color="#E040FB")

        texto_tendencia_paw.markdown(f"**Presión Media Vía Aérea (MAP):** `{map_respiratoria:.1f} cmH2O`")
        espacio_paw.line_chart(df_paw, height=200, color="#FFC107") # Amarillo clásico para respirador

        # Pausa del bucle
        time.sleep(0.1)


# In[ ]:




