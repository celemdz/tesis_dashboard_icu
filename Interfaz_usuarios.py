#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import time
import json
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN Y ESTILOS CLÍNICOS ESTRICTOS
# ==============================================================================
st.set_page_config(layout="wide", page_title="Sistema Central UTI", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0A0A0A; color: #D4D4D4; font-family: 'Segoe UI', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { background-color: #121212; border-bottom: 1px solid #2A2A2A; }
    .stTabs [data-baseweb="tab"] { background-color: #1A1A1A; padding: 10px 20px; border: 1px solid #2A2A2A; border-bottom: none; }
    .stTabs [aria-selected="true"] { background-color: #222 !important; border-top: 3px solid #3498DB !important; }
    .stTabs [data-baseweb="tab-list"] button p { font-size: 12px !important; font-weight: 600 !important; color: #777; letter-spacing: 1px; }
    .stTabs [aria-selected="true"] button p { color: #FFF !important; }
    .metric-box { background-color: #121212; border-left: 3px solid; padding: 12px; border-radius: 2px; }
    .lcd-val { font-family: 'Consolas', monospace; font-size: 26px; font-weight: bold; margin: 0; }
    .lcd-lbl { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# INICIALIZACIÓN DE SESIÓN Y AUTENTICACIÓN
# ==============================================================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<br><br><br><h2 style='text-align: center; color: #FFF; font-weight: 300; letter-spacing: 2px;'>MIMIC-CENTRAL UTI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888; font-size: 12px; letter-spacing: 1px;'>ACCESO RESTRINGIDO A PERSONAL AUTORIZADO</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2:
        with st.form("login_form"):
            profesional_sel = st.selectbox(
                "SELECCIONE OPERADOR", 
                [
                    "ING. GOMEZ, MAXIMO (BIOMEDICA)", 
                    "ING. MENDEZ QUIROGA, CELESTE (SOPORTE)", 
                    "DR. OLMOS, CARLOS (JEFATURA)", 
                    "LIC. ENFERMERIA (TURNO)"
                ]
            )
            clave = st.text_input("CLAVE DE ACCESO", type="password")
            submit = st.form_submit_button("INGRESAR AL SISTEMA", use_container_width=True)

            if submit:
                if clave == "123":
                    st.session_state.autenticado = True
                    st.session_state.profesional_activo = profesional_sel
                    st.rerun()
                else:
                    st.error("CREDENCIAL INVALIDA")
    st.stop()

# ==============================================================================
# LÓGICA CLÍNICA Y DE ANÁLISIS
# ==============================================================================
def evaluar_alarmas(datos, umbrales):
    alarmas = []
    if datos['fc'] > umbrales['fc_max'] and datos['pas'] < umbrales['pas_min']:
        alarmas.append("[CRITICO] SHOCK HEMODINAMICO")
    elif datos['pam'] < umbrales['pam_min']:
        alarmas.append("[ALERTA] HIPOTENSION")
    if datos['fr'] > umbrales['fr_max'] and datos['spo2'] < umbrales['spo2_min']:
        alarmas.append("[CRITICO] FALLA RESPIRATORIA")
    return alarmas

@st.cache_data
def generar_diagrama_poincare(serie_fc):
    if len(serie_fc) < 5: return None
    x_n, x_n1 = np.array(serie_fc[:-1]), np.array(serie_fc[1:])
    sd1 = float(np.sqrt(0.5 * np.var(x_n - x_n1)))
    sd2 = float(np.sqrt(2 * np.var(x_n) - 0.5 * np.var(x_n - x_n1)))

    fig = go.Figure(go.Scatter(x=x_n, y=x_n1, mode='markers', marker=dict(size=3, color='#3498DB', opacity=0.7)))
    fig.update_layout(
        title=dict(text=f"ESPACIO DE FASE (SD1: {sd1:.1f}ms | SD2: {sd2:.1f}ms)", font=dict(color="#888", size=11)),
        plot_bgcolor='#121212', paper_bgcolor='#121212',
        xaxis=dict(title="RR [n]", gridcolor='#222', color="#888", showline=True, linewidth=1, linecolor='#444'),
        yaxis=dict(title="RR [n+1]", gridcolor='#222', color="#888", showline=True, linewidth=1, linecolor='#444'),
        height=200, margin=dict(t=30, b=10, l=10, r=10)
    )
    return fig

# ==============================================================================
# INICIALIZACIÓN DE BASES DE DATOS
# ==============================================================================
if 'dataset_uti' not in st.session_state:
    camas = {}
    PERFILES = ["SHOCK SEPTICO", "POST-QX CARDIO", "SDRA SEVERO", "ESTABLE / DESTETE"]
    for i in range(15):
        perfil = PERFILES[i % 4]
        box_id = f"BOX-{i+1:02d}"

        if i >= 13:
            camas[box_id] = {'estado': 'LIBRE'}
        else:
            fc = 115 if "SHOCK" in perfil else (80 if "ESTABLE" in perfil else 95)
            pam = 58 if "SHOCK" in perfil else 90
            spo2 = 88 if "SDRA" in perfil else 97

            camas[box_id] = {
                'estado': 'OCUPADA', 'diagnostico': perfil, 
                'fc': fc, 'pas': 85 if "SHOCK" in perfil else 120, 'pad': 45 if "SHOCK" in perfil else 75, 'pam': pam,
                'spo2': spo2, 'fr': 28 if "SDRA" in perfil else 16,
                'fio2': 50.0 if "SDRA" in perfil else 21.0, 'gcs': 11 if "SHOCK" in perfil else 15,
                'tendencia_fc': np.random.normal(fc, 4, 150).tolist(),
                'peor_fc': fc + np.random.randint(5, 15), 
                'peor_pam': pam - np.random.randint(2, 8), 
                'peor_spo2': spo2 - np.random.randint(1, 4),
                'historial_alarmas': ["[CRITICO] SHOCK HEMODINAMICO"] if "SHOCK" in perfil else []
            }
    st.session_state.dataset_uti = camas

if 'gestion_rrhh' not in st.session_state:
    st.session_state.gestion_rrhh = {'enfermeros': 8, 'medicos': 2, 'kinesiologos': 2, 'horas_turno': 8.5}

if 'inventario_equipos' not in st.session_state:
    inventario = {}
    fecha_alta = datetime.now().strftime('%d/%m/%Y %H:%M')

    for i in range(1, 16):
        box_id = f"BOX-{i:02d}"
        id_vent = f"Ventilador-{i:02d}-UTI1"
        id_mon = f"Monitor-{i:02d}-UTI1"
        inventario[id_vent] = {'tipo': 'Ventilador Mecánico', 'marca': 'TECME', 'modelo': 'Neumovent Advance', 'sn': f"TM-{1000+i}", 'ubicacion': box_id, 'historial': [f"{fecha_alta} | ALTA INICIAL | Asignado a {box_id}"]}
        inventario[id_mon] = {'tipo': 'Monitor Multiparamétrico', 'marca': 'Mindray', 'modelo': 'BeneVision N15', 'sn': f"MD-{5000+i}", 'ubicacion': box_id, 'historial': [f"{fecha_alta} | ALTA INICIAL | Asignado a {box_id}"]}

    for i in range(1, 4):
        id_vent_b = f"Ventilador-SOPORTE{i}-UTI1"
        id_mon_b = f"Monitor-SOPORTE{i}-UTI1"
        inventario[id_vent_b] = {'tipo': 'Ventilador Mecánico', 'marca': 'TECME', 'modelo': 'Neumovent Advance', 'sn': f"TM-SOP{i}", 'ubicacion': "DEPOSITO", 'historial': [f"{fecha_alta} | ALTA INICIAL | Ingreso a DEPOSITO"]}
        inventario[id_mon_b] = {'tipo': 'Monitor Multiparamétrico', 'marca': 'Mindray', 'modelo': 'BeneVision N15', 'sn': f"MD-SOP{i}", 'ubicacion': "DEPOSITO", 'historial': [f"{fecha_alta} | ALTA INICIAL | Ingreso a DEPOSITO"]}

    st.session_state.inventario_equipos = inventario

datos_uti = st.session_state.dataset_uti
datos_rrhh = st.session_state.gestion_rrhh
inv_equipos = st.session_state.inventario_equipos

# ==============================================================================
# EVALUACIÓN DE ROLES DE USUARIO
# ==============================================================================
perfil_actual = st.session_state.profesional_activo
es_jefatura = "JEFATURA" in perfil_actual
es_bioingenieria = "BIOMEDICA" in perfil_actual or "SOPORTE" in perfil_actual or es_jefatura

# ==============================================================================
# BARRA LATERAL (CONTROL DE SESIÓN Y ENRUTAMIENTO)
# ==============================================================================
st.sidebar.markdown("<h2 style='color: #FFF; font-weight: 300; letter-spacing: 1px;'>SISTEMA CENTRAL</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='color:#888; font-size:10px; font-weight:bold;'>SESION ACTIVA</p>", unsafe_allow_html=True)
st.sidebar.info(perfil_actual)

if st.sidebar.button("CERRAR SESION OPERATIVA", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.profesional_activo = ""
    st.rerun()

st.sidebar.markdown("---")
modo_vista = st.sidebar.radio("MODO DE OPERACION", ["MONITOREO CLINICO", "GESTION DE CAMAS (ADT)", "INDICADORES DE GESTION"])

st.sidebar.markdown("---")
st.sidebar.markdown("<p style='color:#888; font-size:10px; font-weight:bold;'>UMBRALES DE ALARMA</p>", unsafe_allow_html=True)
umbrales = {
    'fc_max': st.sidebar.slider("Límite Superior FC", 100, 150, 120),
    'pam_min': st.sidebar.slider("Límite Inferior PAM", 50, 80, 65),
    'spo2_min': 92, 'fr_max': 25, 'pas_min': 90
}

# ==============================================================================
# MODO: GESTIÓN DE CAMAS (ADT)
# ==============================================================================
if modo_vista == "GESTION DE CAMAS (ADT)":
    st.markdown("<h3 style='color: #FFF; font-weight: 300;'>GESTION DE INGRESOS, EGRESOS Y TRASLADOS (ADT)</h3>", unsafe_allow_html=True)
    col_adm, col_estado = st.columns([1.5, 1])

    with col_adm:
        st.markdown("<p style='color:#888; font-size:12px; font-weight:bold;'>MODIFICACION DE ESTADO DEL PACIENTE</p>", unsafe_allow_html=True)
        camas_libres = [k for k, v in datos_uti.items() if v.get('estado') == 'LIBRE']
        camas_ocupadas = [k for k, v in datos_uti.items() if v.get('estado') == 'OCUPADA']

        accion = st.radio("TIPO DE ORDEN HIS", ["INGRESAR NUEVO PACIENTE", "LIBERAR CAMA (ALTA/OBITO)"], horizontal=True)
        st.markdown("<hr style='border-color: #222; margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)

        if accion == "INGRESAR NUEVO PACIENTE":
            if len(camas_libres) > 0:
                with st.form("form_ingreso"):
                    cama_sel = st.selectbox("Seleccionar Box Disponible", camas_libres)
                    fuente_datos = st.radio("Origen de Datos del Nuevo Ingreso", ["Simulación Manual", "Importar desde Benchmark MIMIC-III Demo"])
                    diag_nuevo = st.text_input("Diagnóstico de Ingreso (Solo para Simulación Manual)")
                    pam_ingreso = st.number_input("PAM Base (Ingreso)", value=90, min_value=0, max_value=200)
                    mimic_id = st.selectbox("ID de Paciente (MIMIC-III)", ["10013 (Crítico - Hemodinamia)", "42075 (Crítico - ST)", "10083 (Verde - Estable)", "40601 (Verde - PVC)"])

                    if st.form_submit_button("EJECUTAR INGRESO"):
                        if fuente_datos == "Importar desde Benchmark MIMIC-III Demo":
                            if "10013" in mimic_id:
                                st.session_state.dataset_uti[cama_sel] = {
                                    'estado': 'OCUPADA', 'diagnostico': 'SHOCK (ID: 10013)', 'fc': 78, 'pas': 58, 'pad': 26, 'pam': 34, 
                                    'spo2': 94, 'fr': 22, 'fio2': 40.0, 'gcs': 11, 'tendencia_fc': np.random.normal(78, 2, 100).tolist(),
                                    'peor_fc': 78, 'peor_pam': 34, 'peor_spo2': 94, 'historial_alarmas': []
                                }
                            else:
                                st.session_state.dataset_uti[cama_sel] = {
                                    'estado': 'OCUPADA', 'diagnostico': f'ESTABLE (ID: {mimic_id[:5]})', 'fc': 82, 'pas': 120, 'pad': 75, 'pam': 90, 
                                    'spo2': 98, 'fr': 16, 'fio2': 21.0, 'gcs': 15, 'tendencia_fc': np.random.normal(82, 2, 100).tolist(),
                                    'peor_fc': 82, 'peor_pam': 90, 'peor_spo2': 98, 'historial_alarmas': []
                                }
                        else:
                            st.session_state.dataset_uti[cama_sel] = {
                                'estado': 'OCUPADA', 'diagnostico': diag_nuevo.upper() if diag_nuevo else "SIN DIAGNOSTICO",
                                'fc': 80, 'pas': pam_ingreso + 30, 'pad': pam_ingreso - 15, 'pam': pam_ingreso, 'spo2': 98, 'fr': 16, 
                                'fio2': 21.0, 'gcs': 15, 'tendencia_fc': np.random.normal(80, 2, 100).tolist(),
                                'peor_fc': 80, 'peor_pam': pam_ingreso, 'peor_spo2': 98, 'historial_alarmas': []
                            }
                        st.success(f"ORDEN EJECUTADA: Ingreso registrado en {cama_sel}.")
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("ALERTA DE CAPACIDAD: La Unidad se encuentra con 100% de ocupación.")

        elif accion == "LIBERAR CAMA (ALTA/OBITO)":
            if len(camas_ocupadas) > 0:
                with st.form("form_egreso"):
                    cama_sel = st.selectbox("Seleccionar Box Ocupado", camas_ocupadas)
                    if st.form_submit_button("EJECUTAR ALTA / EGRESO"):
                        st.session_state.dataset_uti[cama_sel] = {'estado': 'LIBRE'}
                        st.success(f"ORDEN EJECUTADA: {cama_sel} liberada correctamente.")
                        time.sleep(1)
                        st.rerun()
            else:
                st.info("La Unidad se encuentra actualmente sin pacientes activos.")

    with col_estado:
        st.markdown("<p style='color:#888; font-size:12px; font-weight:bold;'>ESTADO ACTUAL DE OCUPACION</p>", unsafe_allow_html=True)
        st.metric("CAMAS DISPONIBLES", f"{len(camas_libres)} / 15")
        st.code("[ PROTOCOLO HIGIENE ]\nCama liberada requiere\n120 min de desinfección\nantes de nuevo ingreso.", language="yaml")

# ==============================================================================
# MODO: INDICADORES DE GESTIÓN (RRHH Y ACTIVOS) CON RBAC
# ==============================================================================
elif modo_vista == "INDICADORES DE GESTION":
    st.markdown("<h3 style='color: #FFF; font-weight: 300;'>PANEL GERENCIAL DE UNIDAD</h3>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("MORTALIDAD (30D)", "14.2%", "-1.1% vs Mes Anterior")
    c2.metric("LOS (ESTANCIA MEDIA)", "6.8 Días", "0.2 Días")
    c3.metric("ROTACION CAMAS", "4.1 pac/cama", "Estable")
    st.markdown("<hr style='border-color: #222;'>", unsafe_allow_html=True)

    # Visibilidad dinámica de pestañas basada en roles
    if es_jefatura:
        tab_rrhh, tab_equipos = st.tabs(["[1] RECURSOS HUMANOS Y PERSONAL", "[2] TRAZABILIDAD DE EQUIPAMIENTO"])

        with tab_rrhh:
            col_form, col_log = st.columns(2)
            with col_form:
                st.markdown("<p style='color:#888; font-size:12px; font-weight:bold;'>ACTUALIZAR PARAMETROS DE DOTACION</p>", unsafe_allow_html=True)
                with st.form("form_rrhh"):
                    enf = st.number_input("Enfermeros de Turno", value=datos_rrhh['enfermeros'], min_value=1, max_value=20)
                    med = st.number_input("Médicos Intensivistas", value=datos_rrhh['medicos'], min_value=1, max_value=10)
                    kin = st.number_input("Kinesiólogos", value=datos_rrhh['kinesiologos'], min_value=0, max_value=10)
                    hs = st.number_input("Horas Promedio del Turno", value=datos_rrhh['horas_turno'], format="%.1f")

                    if st.form_submit_button("ACTUALIZAR BASE DE DATOS RRHH"):
                        st.session_state.gestion_rrhh = {'enfermeros': enf, 'medicos': med, 'kinesiologos': kin, 'horas_turno': hs}
                        st.success("SISTEMA ACTUALIZADO")
                        time.sleep(1)
                        st.rerun()

            with col_log:
                st.markdown("<p style='color:#888; font-size:12px; font-weight:bold;'>ESTADO ACTUAL RRHH</p>", unsafe_allow_html=True)
                pacientes_activos = sum(1 for d in datos_uti.values() if d.get('estado') == 'OCUPADA')
                ratio_enf = pacientes_activos / datos_rrhh['enfermeros'] if datos_rrhh['enfermeros'] > 0 else 0
                st.code(f"""
                [ DOTACION DECLARADA ]
                Enfermeros : {datos_rrhh['enfermeros']} (Ratio 1:{ratio_enf:.1f})
                Médicos    : {datos_rrhh['medicos']}
                Kinesio.   : {datos_rrhh['kinesiologos']}
                Turno (hs) : {datos_rrhh['horas_turno']}

                [ COMPLIANCE NORMATIVO ]
                Ratio Enfermería : {'OPTIMO' if ratio_enf <= 2.0 else 'SOBRECARGA DETECTADA'}
                """, language="yaml")
    else:
        # Si no es jefatura, la pestaña de RRHH ni siquiera se crea
        tab_equipos, = st.tabs(["[1] TRAZABILIDAD DE EQUIPAMIENTO"])

    with tab_equipos:
        col_act1, col_act2 = st.columns([1.5, 1])
        with col_act1:
            st.markdown("<p style='color:#888; font-size:12px; font-weight:bold;'>TRASLADO DE EQUIPAMIENTO</p>", unsafe_allow_html=True)

            # Bloqueo de formulario basado en roles
            if es_bioingenieria:
                with st.form("form_activos"):
                    eq_id = st.selectbox("Seleccionar ID del Equipo", list(inv_equipos.keys()))
                    nueva_ub = st.selectbox("Destino del Traslado", ["DEPOSITO", "BIOINGENIERIA"] + [f"BOX-{i:02d}" for i in range(1, 16)])
                    obs = st.text_input("Observación / Motivo (Obligatorio si salida a Depósito/Bioingeniería)")

                    if st.form_submit_button("REGISTRAR MOVIMIENTO"):
                        if nueva_ub in ["DEPOSITO", "BIOINGENIERIA"] and not obs:
                            st.error("ERROR: Debe ingresar el motivo.")
                        else:
                            ubi_anterior = st.session_state.inventario_equipos[eq_id]['ubicacion']
                            st.session_state.inventario_equipos[eq_id]['ubicacion'] = nueva_ub
                            fecha_str = datetime.now().strftime('%d/%m/%Y %H:%M')
                            nota = obs if obs else "Reasignación operativa"
                            st.session_state.inventario_equipos[eq_id]['historial'].append(f"{fecha_str} | TRASLADO | De {ubi_anterior} a {nueva_ub}. Obs: {nota}")
                            st.success(f"MOVIMIENTO REGISTRADO: {eq_id} trasladado.")
                            time.sleep(1)
                            st.rerun()
            else:
                st.warning("ACCESO RESTRINGIDO: Solo el personal de Bioingeniería o Jefatura puede registrar movimientos de equipamiento.")

            st.markdown("<p style='color:#888; font-size:12px; font-weight:bold; margin-top:20px;'>TRAZABILIDAD HISTORICA DEL EQUIPO</p>", unsafe_allow_html=True)
            eq_hist_sel = st.selectbox("Consultar hoja de vida técnica de:", list(inv_equipos.keys()), label_visibility="collapsed")
            historial_texto = "\n".join(reversed(inv_equipos[eq_hist_sel]['historial']))
            st.code(historial_texto, language="yaml")

        with col_act2:
            st.markdown("<p style='color:#888; font-size:12px; font-weight:bold;'>MAPA DE ACTIVOS POR UBICACION</p>", unsafe_allow_html=True)
            filtro_ub = st.selectbox("Filtrar inventario por:", ["DEPOSITO", "BIOINGENIERIA"] + [f"BOX-{i:02d}" for i in range(1, 16)])
            equipos_filtrados = {k: v for k, v in inv_equipos.items() if v['ubicacion'] == filtro_ub}
            if equipos_filtrados:
                for k, v in equipos_filtrados.items():
                    color_bg = "#121212"
                    borde = "#3498DB" if "Monitor" in v['tipo'] else "#2ECC71"
                    st.markdown(f"""
                    <div style="background-color: {color_bg}; border-left: 3px solid {borde}; padding: 10px; margin-bottom: 8px;">
                        <span style="color:#FFF; font-size:12px; font-weight:bold;">{k}</span><br>
                        <span style="color:#888; font-size:10px;">{v['marca']} {v['modelo']} | SN: {v['sn']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info(f"No hay equipos en {filtro_ub}.")

# ==============================================================================
# MODO: MONITOREO CLÍNICO
# ==============================================================================
else:
    pacientes_disponibles = [k for k, v in datos_uti.items() if v.get('estado') == 'OCUPADA']
    paciente_sel = st.sidebar.selectbox("PACIENTE EN FOCO (VISTA MICRO)", pacientes_disponibles if pacientes_disponibles else ["SIN PACIENTES"])
    datos_foco = datos_uti.get(paciente_sel, None) if paciente_sel != "SIN PACIENTES" else None

    tab_macro, tab_micro = st.tabs(["[1] VISION GENERAL DE LA UNIDAD", "[2] ANALISIS DETALLADO (VISTA MICRO)"])

    with tab_macro:
        st.write("")
        cajas = list(datos_uti.items())
        for fila in range(3):
            cols = st.columns(5)
            for col_idx in range(5):
                idx = fila * 5 + col_idx
                if idx < len(cajas):
                    bid, p_data = cajas[idx]
                    if p_data.get('estado') == 'LIBRE':
                        cols[col_idx].markdown(f"""
                        <div style="background-color: #0A0A0A; border: 1px dashed #333; padding: 12px; border-radius: 4px; height: 120px; display: flex; align-items: center; justify-content: center;">
                            <span style="color:#444; font-size:12px; font-weight:bold;">{bid} - DESOCUPADA</span>
                        </div>
                        """, unsafe_allow_html=True)
                        continue

                    alarmas_activas = evaluar_alarmas(p_data, umbrales)
                    color_border = "#E74C3C" if alarmas_activas else "#2A2A2A"
                    txt_alarma = alarmas_activas[0] if alarmas_activas else "PARAMETROS EN RANGO"

                    if alarmas_activas and txt_alarma not in p_data['historial_alarmas']:
                        p_data['historial_alarmas'].append(txt_alarma)

                    cols[col_idx].markdown(f"""
                    <div style="background-color: #121212; border: 1px solid {color_border}; border-top: 3px solid {color_border}; padding: 10px; border-radius: 2px;">
                        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #222; padding-bottom: 5px;">
                            <span style="font-weight:bold; color:#D4D4D4; font-size:11px;">{bid}</span>
                            <span style="color:#777; font-size:9px;">{p_data['diagnostico'][:15]}</span>
                        </div>
                        <div style="margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
                            <div><span style="color:#2ECC71; font-size:9px;">HR</span><br><span class="lcd-text" style="color:#2ECC71; font-size:16px;">{int(p_data['fc'])}</span></div>
                            <div><span style="color:#E74C3C; font-size:9px;">ABP</span><br><span class="lcd-text" style="color:#E74C3C; font-size:16px;">{int(p_data['pam'])}</span></div>
                            <div><span style="color:#3498DB; font-size:9px;">SpO2</span><br><span class="lcd-text" style="color:#3498DB; font-size:16px;">{int(p_data['spo2'])}</span></div>
                            <div><span style="color:#F1C40F; font-size:9px;">RESP</span><br><span class="lcd-text" style="color:#F1C40F; font-size:16px;">{int(p_data['fr'])}</span></div>
                        </div>
                        <div style="margin-top: 6px; font-size: 9px; font-weight: bold; color: {color_border}; text-align: center;">{txt_alarma}</div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_micro:
        if datos_foco:
            st.markdown(f"<h3 style='color:#FFF; font-weight:300; font-size: 16px;'>MONITOR INDIVIDUAL | <span style='color:#3498DB;'>{paciente_sel}</span> | {datos_foco['diagnostico']}</h3>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-box' style='border-color: #2ECC71;'><p class='lcd-lbl'>Heart Rate</p><p class='lcd-val' style='color:#2ECC71;'>{datos_foco['fc']}</p><p style='margin:0; font-size:9px; color:#777;'>Máx Turno: {datos_foco['peor_fc']}</p></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box' style='border-color: #E74C3C;'><p class='lcd-lbl'>ABP [Mean]</p><p class='lcd-val' style='color:#E74C3C;'>{datos_foco['pas']}/{datos_foco['pad']} <span style='font-size:16px;color:#A0A0A0;'>[{datos_foco['pam']}]</span></p><p style='margin:0; font-size:9px; color:#777;'>Mín Turno: {datos_foco['peor_pam']}</p></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric-box' style='border-color: #3498DB;'><p class='lcd-lbl'>SpO2</p><p class='lcd-val' style='color:#3498DB;'>{datos_foco['spo2']}</p><p style='margin:0; font-size:9px; color:#777;'>Mín Turno: {datos_foco['peor_spo2']}</p></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='metric-box' style='border-color: #F1C40F;'><p class='lcd-lbl'>Resp Rate</p><p class='lcd-val' style='color:#F1C40F;'>{datos_foco['fr']}</p></div>", unsafe_allow_html=True)

            st.markdown("<hr style='border-color: #222;'>", unsafe_allow_html=True)
            col_ondas, col_indices = st.columns([2, 1])
            with col_ondas:
                st.markdown("<span style='color:#888; font-size:11px; font-weight:bold;'>MORFOLOGIA CONTINUA (125 Hz)</span>", unsafe_allow_html=True)
                t = np.linspace(0, 4, 150)
                onda_abp = datos_foco['pad'] + (datos_foco['pas'] - datos_foco['pad']) * np.abs(np.sin(2 * np.pi * (datos_foco['fc']/60) * t))
                st.line_chart(pd.DataFrame({"ABP (mmHg)": onda_abp}), height=140, color="#E74C3C")
            with col_indices:
                st.markdown("<span style='color:#888; font-size:11px; font-weight:bold;'>ESPACIO DE FASE</span>", unsafe_allow_html=True)
                fig_poincare = generar_diagrama_poincare(datos_foco['tendencia_fc'])
                if fig_poincare: st.plotly_chart(fig_poincare, use_container_width=True)

