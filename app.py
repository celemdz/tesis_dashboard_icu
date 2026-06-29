import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import time

# Configuracion de pagina ancha para diseño de tablero industrial
st.set_page_config(layout="wide")

# Rutas locales de la base de datos MIMIC-IV Clinical Demo
ruta_icustays = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\icu\icustays.csv.gz"
ruta_patients = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\hosp\patients.csv.gz"

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
# PESTAÑA 1: VISTA MACRO (GESTIÓN HOSPITALARIA) - CODIGO ORIGINAL CONSERVADO
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
# PESTAÑA 2: VISTA MICRO (MONITOR DE SEÑALES MULTIPARAMÉTRICO)
# ==============================================================================
with tab_micro:
    st.title("Neuromonitoring Dashboard v3.0 - Simulacion Micro")
    st.markdown("Modulo Integrado para el Analisis de Senales en Alta Frecuencia")
    
    # Menu lateral especifico para la seleccion de perfiles clinicos de prueba
    st.sidebar.markdown("### Seleccion de Paciente (MIMIC-IV)")
    paciente_seleccionado = st.sidebar.selectbox(
        "Seleccione la cama a monitorizar:",
        ["Paciente: Juan - ID: 5676 - DX: HSA", "Paciente: Maria - ID: 7421 - DX: Trauma"]
    )
    
    # Asignacion de parametros fisiologicos basales segun el perfil seleccionado
    if "Juan" in paciente_seleccionado:
        fc_base = 75.0       # Frecuencia Cardiaca base (Latidos por minuto)
        pa_sistolica = 120   # Presion Arterial Sistolica (mmHg)
        pa_diastolica = 80    # Presion Arterial Diastolica (mmHg)
        spo2_base = 98.0     # Saturacion de Oxigeno (%)
        pic_base = 12.0      # Presion Intracraneal base (mmHg)
    else:
        fc_base = 95.0       # Paciente taquicardico por trauma
        pa_sistolica = 135
        pa_diastolica = 90
        spo2_base = 94.0     # Paciente con leve desaturacion
        pic_base = 18.0      # Presion Intracraneal elevada (Alerta de hipertension endocraneana)

    # Bloque estetico superior: Contenedores numericos con estilo de hardware medico
    st.markdown("### Parametros Fisiologicos Actuales")
    col_fc, col_pa, col_spo2, col_pic = st.columns(4)
    
    with col_fc:
        st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00E676;'>"
                f"<p style='color:#00E676; margin:0; font-weight:bold;'>FC (lpm)</p>"
                f"<h2 style='color:#ffffff; margin:0;'>{int(fc_base)}</h2></div>")
                
    with col_pa:
        st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #FF4B4B;'>"
                f"<p style='color:#FF4B4B; margin:0; font-weight:bold;'>PA (mmHg)</p>"
                f"<h2 style='color:#ffffff; margin:0;'>{pa_sistolica}/{pa_diastolica}</h2></div>")
                
    with col_spo2:
        st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #00B0FF;'>"
                f"<p style='color:#00B0FF; margin:0; font-weight:bold;'>SpO2 (%)</p>"
                f"<h2 style='color:#ffffff; margin:0;'>{int(spo2_base)}</h2></div>")
                
    with col_pic:
        st.html(f"<div style='background-color:#1C1E24; padding:15px; border-radius:5px; border-left: 5px solid #E040FB;'>"
                f"<p style='color:#E040FB; margin:0; font-weight:bold;'>PIC (mmHg)</p>"
                f"<h2 style='color:#ffffff; margin:0;'>{pic_base}</h2></div>")
    st.write("")
    
    # Elementos vacios de Streamlit que actuaran como placeholders para refrescar las señales
    espacio_grafico_pa = st.empty()
    espacio_grafico_pic = st.empty()
    
    # Ecuaciones de Fourier para modelar la morfologia de las ondas fisiologicas
    # Frecuencia angular calculada a partir de los latidos por minuto (FC)
    omega = 2 * np.pi * (fc_base / 60.0)
    
    # Vector de tiempo continuo para una ventana visual de 5 segundos
    tiempo = np.linspace(0, 5, 250)
    
    # Generacion matematica de la curva de Presion Arterial (Onda con muesca dicrota)
    onda_pa = pa_diastolica + (pa_sistolica - pa_diastolica) * (
        0.4 * np.sin(omega * tiempo) + 
        0.3 * np.sin(2 * omega * tiempo) + 
        0.15 * np.sin(3 * omega * tiempo)
    )
    # Suavizado para garantizar valores fisiologicos coherentes
    onda_pa = np.clip(onda_pa, pa_diastolica - 5, pa_sistolica + 5)
    
    # Generacion matematica de la Presion Intracraneal (Onda tricuspidea amortiguada)
    onda_pic = pic_base + 3 * (
        0.5 * np.sin(omega * tiempo) + 
        0.2 * np.sin(2 * omega * tiempo)
    )

   # CONFIGURACIÓN GRÁFICA INICIAL DE PLOTLY (Estética de monitor real)
    fig_pa = go.Figure()
    fig_pa.add_trace(go.Scatter(x=[], y=[], mode='lines', line=dict(color='#FF4B4B', width=3)))
    fig_pa.update_layout(
        title="Monitoreo Continuo de Presion Arterial Invasiva (PAI)",
        xaxis=dict(title="Tiempo (Segundos)", showgrid=False, zeroline=False),
        yaxis=dict(title="mmHg", showgrid=False, zeroline=False, range=[pa_diastolica - 20, pa_sistolica + 20]),
        paper_bgcolor='#0E1117',
        plot_bgcolor='#0E1117',
        font=dict(color='#ffffff'),
        height=280,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    fig_pic = go.Figure()
    fig_pic.add_trace(go.Scatter(x=[], y=[], mode='lines', line=dict(color='#E040FB', width=3)))
    fig_pic.update_layout(
        title="Monitoreo Continuo de Presion Intracraneal (PIC)",
        xaxis=dict(title="Tiempo (Segundos)", showgrid=False, zeroline=False),
        yaxis=dict(title="mmHg", showgrid=False, zeroline=False, range=[pic_base - 10, pic_base + 10]),
        paper_bgcolor='#0E1117',
        plot_bgcolor='#0E1117',
        font=dict(color='#ffffff'),
        height=280,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    # BUCLE DE REFRESCO EN TIEMPO REAL (Simulación de osciloscopio activo)
    # Iniciamos el conteo del tiempo de simulación
    tiempo_inicio = time.time()
    
    # Este ciclo mantiene las señales actualizándose de forma continua en la pantalla
    while True:
        # Calculamos el segundo actual respecto al inicio del bucle
        tiempo_actual = time.time() - tiempo_inicio
        
        # Generamos una ventana móvil de los últimos 5 segundos de señal
        ventana_tiempo = np.linspace(tiempo_actual, tiempo_actual + 5, 150)
        
        # Recalculamos las ecuaciones de Fourier adaptadas al desplazamiento temporal
        onda_pa_dinamica = pa_diastolica + (pa_sistolica - pa_diastolica) * (
            0.4 * np.sin(omega * ventana_tiempo) + 
            0.3 * np.sin(2 * omega * ventana_tiempo) + 
            0.15 * np.sin(3 * omega * ventana_tiempo)
        )
        onda_pa_dinamica = np.clip(onda_pa_dinamica, pa_diastolica - 5, pa_sistolica + 5)
        
        onda_pic_dinamica = pic_base + 3 * (
            0.5 * np.sin(omega * ventana_tiempo) + 
            0.2 * np.sin(2 * omega * ventana_tiempo)
        )
        
        # Actualizamos los datos de los trazados sin redibujar todo el layout gráfico
        fig_pa.data[0].x = ventana_tiempo
        fig_pa.data[0].y = onda_pa_dinamica
        
        fig_pic.data[0].x = ventana_tiempo
        fig_pic.data[0].y = onda_pic_dinamica
        
        # Modificamos dinámicamente los rangos del eje X para simular el desplazamiento
        fig_pa.update_layout(xaxis=dict(range=[tiempo_actual, tiempo_actual + 5]))
        fig_pic.update_layout(xaxis=dict(range=[tiempo_actual, tiempo_actual + 5]))
        
        # Inyectamos de manera síncrona los gráficos actualizados en los contenedores vacíos
        espacio_grafico_pa.plotly_chart(fig_pa, use_container_width=True, key=f"pa_{tiempo_actual}")
        espacio_grafico_pic.plotly_chart(fig_pic, use_container_width=True, key=f"pic_{tiempo_actual}")
        
        # Pausa milimétrica para emular la tasa de refresco por hardware del monitor (FPS)
        time.sleep(0.05)
