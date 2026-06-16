import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de página ancha (estilo Dashboard industrial según Jebraeily et al.)
st.set_page_config(layout="wide")

# TÍTULO PRINCIPAL (Siguiendo la lógica del paper de Urmia)
st.title("PROYECTO INTEGRADOR: Dashboard Clínico - Unidad de Cuidados Intensivos")
st.markdown("Dashboard Clínico para el Monitoreo de KPIs en la UTI a partir de database de MIMIC-IV")
st.markdown("---")

# CARGA DE DATOS (Tus scripts validados de MIMIC)
ruta_icustays = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\6 DE MAYO 2026\DataBase\mimic-iv-clinical-database-demo-2.2\icu\icustays.csv.gz"
ruta_patients = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\6 DE MAYO 2026\DataBase\mimic-iv-clinical-database-demo-2.2\hosp\patients.csv.gz"

@st.cache_data
def cargar_datos():
    icustays = pd.read_csv(ruta_icustays)
    patients = pd.read_csv(ruta_patients)
    icustays['intime'] = pd.to_datetime(icustays['intime'])
    return icustays, patients

icustays, patients = cargar_datos()

# CÁLCULO DE MÉTRICAS GLOBALES (Fila Superior)
total_pacientes = int(icustays['stay_id'].nunique())
estancia_promedio = float(icustays['los'].mean())
df_mortalidad = pd.merge(icustays, patients, on='subject_id', how='left')
fallecidos_totales = df_mortalidad[df_mortalidad['dod'].notna()]['stay_id'].nunique()
tasa_mortalidad = (fallecidos_totales / total_pacientes) * 100

# RENDER DE FILA SUPERIOR: TARJETAS DE KPIs
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label=" Total de Altas Analizadas (Histórico)", value=total_pacientes)
with col2:
    st.metric(label=" Duración de la Estancia (LOS Promedio)", value=f"{estancia_promedio:.2f} días")
with col3:
    st.metric(label=" Tasa de Mortalidad Bruta General", value=f"{tasa_mortalidad:.1f}%")

st.markdown("---")

# FILA CENTRAL: GRÁFICOS OPERATIVOS (Tu captura base)
st.header("Indicadores de Salida y Operativos (Outcome & Process KPIs)")
col_grafico1, col_grafico2 = st.columns(2)

with col_grafico1:
    st.subheader(" Evolución Histórica de Ingresos (Mensual)")
    icustays['mes_anio'] = icustays['intime'].dt.to_period('M').astype(str)
    df_mensual = icustays.groupby('mes_anio')['stay_id'].nunique().reset_index()
    df_mensual.columns = ['Mes', 'Cantidad de Pacientes']
    
    fig_barras = px.bar(df_mensual, x='Mes', y='Cantidad de Pacientes', 
                        text_auto=True, color_discrete_sequence=['#1f77b4'])
    fig_barras.update_layout(xaxis_title="Período Temporal", yaxis_title="Ingresos")
    st.plotly_chart(fig_barras, use_container_width=True)

with col_grafico2:
    st.subheader(" Distribución de Ocupación por Tipo de UCI")
    df_sectores = icustays['first_careunit'].value_counts().reset_index()
    df_sectores.columns = ['Tipo de Unidad', 'Total Ingresos']
    
    fig_torta = px.pie(df_sectores, names='Tipo de Unidad', values='Total Ingresos', 
                       hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_torta, use_container_width=True)

st.markdown("---")

# 🔍 NUEVA SECCIÓN ADAPTADA DEL PAPER (Demografía y Gravedad)
st.header("Análisis Demográfico y de Calidad Asistencial")
col_abajo1, col_abajo2 = st.columns(2)

with col_abajo1:
    st.subheader("Distribución de Pacientes por Edad")
    # Calculamos la edad real combinando variables de MIMIC
    df_mortalidad['edad'] = df_mortalidad['intime'].dt.year - df_mortalidad['anchor_year'] + df_mortalidad['anchor_age']
    
    fig_edad = px.histogram(df_mortalidad, x='edad', nbins=15, text_auto=True,
                            labels={'edad': 'Edad (Años)'}, color_discrete_sequence=['#2ca02c'])
    fig_edad.update_layout(xaxis_title="Rangos de Edad", yaxis_title="Cantidad de Pacientes")
    st.plotly_chart(fig_edad, use_container_width=True)

with col_abajo2:
    st.subheader(" Tasa de Mortalidad Específica por Sector")
    # Agrupamos fallecidos y admisiones por tipo de unidad asistencial
    df_mort_unidad = df_mortalidad.groupby('first_careunit').agg(
        Total=('stay_id', 'nunique'),
        Fallecidos=('dod', lambda x: x.notna().sum())
    ).reset_index()
    df_mort_unidad['% Mortalidad'] = (df_mort_unidad['Fallecidos'] / df_mort_unidad['Total']) * 100
    
    fig_mort_unidad = px.bar(df_mort_unidad, x='first_careunit', y='% Mortalidad',
                             text_auto='.1f', color_discrete_sequence=['#d62728'])
    fig_mort_unidad.update_layout(xaxis_title="Unidad del Hospital", yaxis_title="Tasa de Mortalidad (%)")
    st.plotly_chart(fig_mort_unidad, use_container_width=True)