# ============================================================
# PASO 6 (v2) - Selección final de tramos de 30 minutos
# Cambios confirmados (Informe de avance Parte 4):
#  1. ABP: solo los criterios TÉCNICOS de Sun rechazan; los FISIOLÓGICOS
#     (presión de pulso < 30 y cambios latido a latido) se registran.
#  2. Margen de 1 minuto al final de la ventana.
#  3. Se recorre toda la ventana (sin límite de candidatos).
#  4. 10045: cama crítica sin línea arterial (II + PLETH).
#  5. Control de coherencia: PAM de la curva vs. ABP Mean de los numéricos.
# Lee señales desde PhysioNet (necesita internet).
# ============================================================

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import wfdb
from scipy.signal import find_peaks

# --- Ruta: copiá la de RECORDS-numerics de los scripts anteriores ---
RUTA_NUM = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic iii - waveform - database\RECORDS-numerics"

BASE_PHYSIONET = "mimic3wdb-matched/1.0"
CARPETA_TRAMOS = "tramos_base"

# --- Estrategia de candidatos --------------------------------
DURACION_S = 30 * 60
PASO_S = 30 * 60
MARGEN_S = 60                 # margen al final de la ventana (corrección 2)
EPOCA_S = 10

# --- Umbrales técnicos (deciden el rechazo) ------------------
FALTANTES_MAX = 0.0                  # criterio propio
ESCALONES_PLANO = 2                  # criterio propio
ECG_MAX_MV = 5.0                     # criterio propio
FRACCION_LATIDOS_BUENOS_MIN = 0.95   # criterio propio
P_MIN, P_MAX = 20, 300               # Sun et al. (2006)
PAM_MIN, PAM_MAX = 30, 200           # Sun et al. (2006)
FC_MIN, FC_MAX = 20, 200             # Sun et al. (2006)

# --- Umbrales fisiológicos (solo se registran) ---------------
PP_MIN = 30
DELTA_P_MAX = 20
DELTA_PERIODO_MAX = 0.5

# --- Control de coherencia -----------------------------------
DIFERENCIA_PAM_MAX = 10       # mmHg; por encima se marca "revisar" (informativo)

ARTERIAL = ("ABP", "ART")
VARIANTES_PAM_NUM = ["ABP Mean", "ABP MEAN", "ABPMean", "ART Mean", "ART MEAN", "ARTMean"]
VARIANTES_PAP_NUM = ["PAP Mean", "PAP MEAN", "PAPMean"]

COHORTE = {
    "critico": [10045, 42075, 43798, 43827, 44083, 10013, 10061],
    "verde":   [10083, 10124, 40601, 41795, 42033, 42199, 42367, 43870],
}
SIN_ARTERIAL = {10045}        # cambio 4


# ============================================================
# Funciones de calidad
# ============================================================
def paso_cuantizacion(x):
    valores = np.unique(x[~np.isnan(x)])
    if len(valores) < 2:
        return 0.0
    diferencias = np.diff(valores)
    return diferencias[diferencias > 0].min()


def epocas_planas(x, fs):
    escalon = paso_cuantizacion(x)
    n = int(EPOCA_S * fs)
    planas = []
    for i in range(0, len(x) - n + 1, n):
        epoca = x[i:i + n]
        if np.nanmax(epoca) - np.nanmin(epoca) <= ESCALONES_PLANO * escalon:
            planas.append(i / fs)
    return planas


def latidos_abp(abp, fs):
    """Criterios de Sun separados en técnicos y fisiológicos."""
    picos, _ = find_peaks(abp, distance=int(0.3 * fs), prominence=10)
    if len(picos) < 3:
        return None

    ps, pd_, pm, periodo = [], [], [], []
    for p0, p1 in zip(picos[:-1], picos[1:]):
        ps.append(abp[p1])
        pd_.append(abp[p0:p1].min())
        pm.append(abp[p0:p1].mean())
        periodo.append((p1 - p0) / fs)
    ps, pd_, pm, periodo = map(np.array, (ps, pd_, pm, periodo))
    fc = 60 / periodo
    pp = ps - pd_

    tecnico = ((ps > P_MAX) | (pd_ < P_MIN) | (pm < PAM_MIN) | (pm > PAM_MAX) |
               (fc < FC_MIN) | (fc > FC_MAX))
    pp_bajo = pp < PP_MIN
    d_sis = np.r_[False, np.abs(np.diff(ps)) > DELTA_P_MAX]
    d_dia = np.r_[False, np.abs(np.diff(pd_)) > DELTA_P_MAX]
    d_per = np.r_[False, np.abs(np.diff(periodo)) > DELTA_PERIODO_MAX]
    sun_completo = tecnico | pp_bajo | d_sis | d_dia | d_per

    return {
        "n": len(ps),
        "frac_tecnico": 1 - tecnico.mean(),
        "frac_sun_completo": 1 - sun_completo.mean(),
        "pct_pp_bajo": pp_bajo.mean() * 100,
        "pct_cambio_sis": d_sis.mean() * 100,
        "pct_cambio_dia": d_dia.mean() * 100,
        "pct_cambio_periodo": d_per.mean() * 100,
        "pam_mediana": float(np.median(pm)),
        "segundos_malos": [picos[i + 1] / fs for i in np.where(tecnico)[0]],
    }


def evaluar_tramo(registro, canales):
    fs = registro.fs
    problemas, metricas = [], {}

    for canal in canales:
        if canal not in registro.sig_name:
            problemas.append((canal, "canal_ausente", "el canal no está en el tramo", None))
            continue
        x = registro.p_signal[:, registro.sig_name.index(canal)]

        frac_nan = np.isnan(x).mean()
        if frac_nan > FALTANTES_MAX:
            primero = np.where(np.isnan(x))[0][0] / fs
            problemas.append((canal, "dato_faltante", f"{frac_nan * 100:.2f} % de muestras vacías", primero))
            continue

        planas = epocas_planas(x, fs)
        if planas:
            problemas.append((canal, "linea_plana", f"{len(planas)} época(s) de {EPOCA_S} s sin variación", planas[0]))

        if canal == "II":
            saturadas = np.where(np.abs(x) > ECG_MAX_MV)[0]
            if len(saturadas):
                problemas.append((canal, "saturacion_ecg",
                                  f"{len(saturadas)} muestras fuera de ±{ECG_MAX_MV} mV", saturadas[0] / fs))

        if canal in ARTERIAL:
            r = latidos_abp(x, fs)
            if r is None:
                problemas.append((canal, "latidos_abp_insuficientes", "menos de 3 latidos detectados", None))
                continue
            metricas.update({
                "latidos_abp": r["n"],
                "fraccion_tecnica": round(r["frac_tecnico"], 3),
                "fraccion_sun_completo": round(r["frac_sun_completo"], 3),
                "pct_pp_bajo": round(r["pct_pp_bajo"], 1),
                "pct_cambio_sis": round(r["pct_cambio_sis"], 1),
                "pct_cambio_dia": round(r["pct_cambio_dia"], 1),
                "pct_cambio_periodo": round(r["pct_cambio_periodo"], 1),
                "pam_curva": round(r["pam_mediana"], 1),
            })
            if r["frac_tecnico"] < FRACCION_LATIDOS_BUENOS_MIN:
                problemas.append((canal, "latidos_abp_anormales_tecnicos",
                                  f"{(1 - r['frac_tecnico']) * 100:.1f} % de latidos con fallas técnicas (de {r['n']})",
                                  r["segundos_malos"][0] if r["segundos_malos"] else None))
    return problemas, metricas


def inicio_grabacion(linea):
    nombre = linea.rsplit("/", 1)[1]
    fecha = nombre.split("-", 1)[1].rstrip("n")    # los numéricos terminan en 'n'
    return datetime.strptime(fecha, "%Y-%m-%d-%H-%M")


def coherencia_numericos(subject_id, t0, t1, lineas_num):
    """Mediana de ABP Mean (y PAP Mean, si existe) de los numéricos durante el tramo."""
    propias = [l for l in lineas_num if int(l.split("/")[1][1:]) == subject_id]
    for linea in propias:
        carpeta, nombre = linea.rsplit("/", 1)
        pn_dir = f"{BASE_PHYSIONET}/{carpeta}"
        try:
            h = wfdb.rdheader(nombre, pn_dir=pn_dir)
            inicio = inicio_grabacion(linea)
            fin = inicio + timedelta(seconds=h.sig_len / h.fs)
            if not (inicio <= t0 and t1 <= fin):
                continue
            a = int((t0 - inicio).total_seconds() * h.fs)
            b = max(a + 1, int((t1 - inicio).total_seconds() * h.fs))
            reg = wfdb.rdrecord(nombre, pn_dir=pn_dir, sampfrom=a, sampto=b)
            res = {}
            for clave, variantes in (("pam_numericos", VARIANTES_PAM_NUM),
                                     ("pap_media_numericos", VARIANTES_PAP_NUM)):
                for v in variantes:
                    if v in reg.sig_name:
                        x = reg.p_signal[:, reg.sig_name.index(v)]
                        if np.any(~np.isnan(x)):
                            res[clave] = round(float(np.nanmedian(x)), 1)
                        break
            return res
        except Exception:
            continue
    return {}


# ============================================================
# Recorrido principal
# ============================================================
verificacion = pd.read_csv("verificacion_segmentos.csv")
alineacion = pd.read_csv("alineacion_temporal.csv")
detalle = pd.read_csv("detalle_grabaciones.csv")
detalle["canales"] = detalle["canales"].fillna("")
with open(RUTA_NUM) as archivo:
    lineas_num = archivo.read().split()
os.makedirs(CARPETA_TRAMOS, exist_ok=True)

seleccionados, anomalias = [], []

for rol, pacientes in COHORTE.items():
    for subject_id in pacientes:
        v = verificacion[verificacion["subject_id"] == subject_id].iloc[0]
        a = alineacion[alineacion["subject_id"] == subject_id].iloc[0]
        linea = v["mejor_grabacion"]
        carpeta, nombre = linea.rsplit("/", 1)
        pn_dir = f"{BASE_PHYSIONET}/{carpeta}"

        texto = detalle.loc[detalle["grabacion"] == linea, "canales"].iloc[0]
        canales_grabacion = {c.strip() for c in texto.split(",") if c.strip()}
        canales = ["II"]
        if rol == "critico" and subject_id not in SIN_ARTERIAL:
            canales.append(next(c for c in ARTERIAL if c in canales_grabacion))
        if "PLETH" in canales_grabacion:
            canales.append("PLETH")

        print(f"\n[{rol}] Paciente {subject_id} | canales: {', '.join(canales)}")
        fs = wfdb.rdheader(nombre, pn_dir=pn_dir).fs
        inicio_ventana = float(v["inicio_ventana_s"])
        fin_util = inicio_ventana + float(v["ventana_max_min"]) * 60 - MARGEN_S

        elegido = None
        k = 0
        while True:
            inicio = fin_util - DURACION_S - k * PASO_S
            if inicio < inicio_ventana:
                break
            print(f"   Candidato {k + 1}: desde el segundo {inicio:.0f} ...", end=" ")
            try:
                registro = wfdb.rdrecord(nombre, pn_dir=pn_dir,
                                         sampfrom=int(inicio * fs),
                                         sampto=int((inicio + DURACION_S) * fs))
            except Exception as e:
                print("error de lectura")
                anomalias.append({"subject_id": subject_id, "candidato": k + 1, "canal": "-",
                                  "tipo": "error_lectura", "detalle": str(e),
                                  "segundo_en_tramo": None, "inicio_candidato_s": round(inicio, 1)})
                k += 1
                continue

            problemas, metricas = evaluar_tramo(registro, canales)
            if not problemas:
                print("APROBADO")
                elegido = (k, inicio, registro, metricas)
                break
            print("rechazado")
            for canal, tipo, det, seg in problemas:
                anomalias.append({"subject_id": subject_id, "candidato": k + 1, "canal": canal,
                                  "tipo": tipo, "detalle": det,
                                  "segundo_en_tramo": None if seg is None else round(seg, 1),
                                  "inicio_candidato_s": round(inicio, 1)})
            k += 1

        fila = {"subject_id": subject_id, "rol": rol, "grabacion": linea,
                "canales": ", ".join(canales), "aprobado": elegido is not None,
                "candidatos_evaluados": k + 1 if elegido else k}
        if elegido:
            k, inicio, registro, metricas = elegido
            t0 = inicio_grabacion(linea) + timedelta(seconds=inicio)
            fila.update({
                "candidato": k + 1,
                "inicio_en_grabacion_s": round(inicio, 1),
                "tramo_inicio": t0,
                "horas_previas": round(float(a["horas_previas_max"]) - (MARGEN_S + k * PASO_S) / 3600, 1),
                **metricas,
            })
            # Control de coherencia (cambio 5), solo con presión invasiva
            if "pam_curva" in metricas:
                fila.update(coherencia_numericos(subject_id, t0, t0 + timedelta(seconds=DURACION_S), lineas_num))
                if "pam_numericos" in fila:
                    diferencia = abs(fila["pam_curva"] - fila["pam_numericos"])
                    fila["coherencia_pam"] = "ok" if diferencia <= DIFERENCIA_PAM_MAX else "revisar"
                else:
                    fila["coherencia_pam"] = "sin numéricos"

            idx = [registro.sig_name.index(c) for c in canales]
            wfdb.wrsamp(f"{subject_id}_tramo", fs=fs,
                        units=[registro.units[i] for i in idx],
                        sig_name=canales,
                        p_signal=registro.p_signal[:, idx],
                        fmt=["16"] * len(canales),
                        write_dir=CARPETA_TRAMOS)
        seleccionados.append(fila)


# ============================================================
# Resultados
# ============================================================
resultado = pd.DataFrame(seleccionados)
resultado.to_csv("tramos_seleccionados_v2.csv", index=False)
pd.DataFrame(anomalias).to_csv("anomalias_reales_v2.csv", index=False)

print("\n===== TRAMOS SELECCIONADOS =====")
columnas = [c for c in ["subject_id", "rol", "aprobado", "candidato", "horas_previas"] if c in resultado.columns]
print(resultado[columnas].to_string(index=False))

criticos = resultado[resultado["rol"] == "critico"]
cols_abp = [c for c in ["subject_id", "fraccion_tecnica", "fraccion_sun_completo", "pct_pp_bajo",
                        "pct_cambio_sis", "pct_cambio_dia", "pct_cambio_periodo"] if c in criticos.columns]
if len(cols_abp) > 1:
    print("\n===== PRESIÓN ARTERIAL: CRITERIOS TÉCNICOS Y FISIOLÓGICOS =====")
    print(criticos[cols_abp].dropna(subset=["fraccion_tecnica"]).to_string(index=False))

cols_coh = [c for c in ["subject_id", "pam_curva", "pam_numericos", "pap_media_numericos", "coherencia_pam"]
            if c in criticos.columns]
if len(cols_coh) > 1:
    print("\n===== CONTROL DE COHERENCIA (mmHg) =====")
    print(criticos[cols_coh].dropna(subset=["pam_curva"]).to_string(index=False))

print("\n===== RESUMEN =====")
for rol in COHORTE:
    sub = resultado[resultado["rol"] == rol]
    print(f"{rol}: aprobados {sub['aprobado'].sum()} de {len(sub)}")
if "fraccion_sun_completo" in resultado.columns:
    con_abp = resultado.dropna(subset=["fraccion_sun_completo"])
    cumplen = (con_abp["fraccion_sun_completo"] >= FRACCION_LATIDOS_BUENOS_MIN).sum()
    print(f"Tramos elegidos con presión invasiva que además cumplen Sun completo: {cumplen} de {len(con_abp)}")

if anomalias:
    print("\n===== ANOMALÍAS REALES REGISTRADAS (por tipo) =====")
    print(pd.DataFrame(anomalias)["tipo"].value_counts().to_string())

print(f"\nArchivos guardados: tramos_seleccionados_v2.csv, anomalias_reales_v2.csv y la carpeta {CARPETA_TRAMOS}/")