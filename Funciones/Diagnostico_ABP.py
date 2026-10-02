# ============================================================
# PASO 6b - Diagnóstico de los rechazos por latidos de ABP
# Objetivo: ver QUÉ criterio de Sun falla en cada caso y verificar
#           visualmente si el detector de latidos marca bien los picos.
# No modifica la selección. Lee señales desde PhysioNet (internet).
# ============================================================

import os
import numpy as np
import pandas as pd
import wfdb
from scipy.signal import find_peaks
import matplotlib
matplotlib.use("Agg")            # genera imágenes sin abrir ventanas
import matplotlib.pyplot as plt

BASE_PHYSIONET = "mimic3wdb-matched/1.0"
CARPETA = "diagnostico"
DURACION_S = 30 * 60

# (subject_id, segundo de inicio del candidato, número de candidato)
CASOS = [(43798, 35130.0, 1), (43827, 3363.0, 2), (10013, 217450.2, 6)]

# Criterios de Sun, Reisner y Mark (2006)
P_MIN, P_MAX = 20, 300
PAM_MIN, PAM_MAX = 30, 200
FC_MIN, FC_MAX = 20, 200
PP_MIN = 30
DELTA_P_MAX = 20
DELTA_PERIODO_MAX = 0.5


def analizar(abp, fs):
    """Detecta latidos y evalúa cada criterio por separado."""
    picos, _ = find_peaks(abp, distance=int(0.3 * fs), prominence=10)
    valles = np.array([p0 + np.argmin(abp[p0:p1]) for p0, p1 in zip(picos[:-1], picos[1:])])
    ps = abp[picos[1:]]
    pdia = abp[valles]
    pm = np.array([abp[p0:p1].mean() for p0, p1 in zip(picos[:-1], picos[1:])])
    periodo = np.diff(picos) / fs
    fc = 60 / periodo
    pp = ps - pdia

    criterios = {
        "Presión > 300 o < 20 mmHg": (ps > P_MAX) | (pdia < P_MIN),
        "PAM fuera de 30-200 mmHg": (pm < PAM_MIN) | (pm > PAM_MAX),
        "FC fuera de 20-200 lpm": (fc < FC_MIN) | (fc > FC_MAX),
        "Presión de pulso < 30 mmHg": pp < PP_MIN,
        "Cambio de sistólica > 20 mmHg": np.r_[False, np.abs(np.diff(ps)) > DELTA_P_MAX],
        "Cambio de diastólica > 20 mmHg": np.r_[False, np.abs(np.diff(pdia)) > DELTA_P_MAX],
        "Cambio de período > 0,5 s": np.r_[False, np.abs(np.diff(periodo)) > DELTA_PERIODO_MAX],
    }
    malo = np.zeros(len(ps), dtype=bool)
    for c in criterios.values():
        malo |= c

    return {"picos": picos[1:], "valles": valles, "ps": ps, "pd": pdia, "pm": pm,
            "pp": pp, "fc": fc, "criterios": criterios, "malo": malo}


os.makedirs(CARPETA, exist_ok=True)
verificacion = pd.read_csv("verificacion_segmentos.csv")
detalle = pd.read_csv("detalle_grabaciones.csv")
detalle["canales"] = detalle["canales"].fillna("")

for subject_id, inicio, candidato in CASOS:
    linea = verificacion.loc[verificacion["subject_id"] == subject_id, "mejor_grabacion"].iloc[0]
    carpeta, nombre = linea.rsplit("/", 1)
    pn_dir = f"{BASE_PHYSIONET}/{carpeta}"
    texto = detalle.loc[detalle["grabacion"] == linea, "canales"].iloc[0]
    canal = "ABP" if "ABP" in texto else "ART"

    fs = wfdb.rdheader(nombre, pn_dir=pn_dir).fs
    registro = wfdb.rdrecord(nombre, pn_dir=pn_dir,
                             sampfrom=int(inicio * fs), sampto=int((inicio + DURACION_S) * fs))
    abp = registro.p_signal[:, registro.sig_name.index(canal)]
    abp = np.nan_to_num(abp, nan=np.nanmedian(abp))   # por si queda algún hueco suelto

    r = analizar(abp, fs)
    n = len(r["malo"])

    # --- Desglose en texto ---
    print(f"\n===== Paciente {subject_id} (candidato {candidato}, canal {canal}) =====")
    print(f"Latidos detectados: {n} | anormales: {r['malo'].sum()} ({r['malo'].mean() * 100:.1f} %)")
    print("Latidos que fallan cada criterio:")
    for nombre_crit, mascara in r["criterios"].items():
        print(f"   {nombre_crit:<34} {mascara.sum():>5}  ({mascara.mean() * 100:5.1f} %)")
    print("Valores típicos (mediana):")
    print(f"   Sistólica {np.median(r['ps']):.0f} | Diastólica {np.median(r['pd']):.0f} | "
          f"Presión de pulso {np.median(r['pp']):.0f} | PAM {np.median(r['pm']):.0f} mmHg | "
          f"FC {np.median(r['fc']):.0f} lpm")

    # --- Gráfico ---
    t = np.arange(len(abp)) / fs
    t_malo = r["picos"][r["malo"]] / fs
    t0 = max(0.0, (t_malo[0] - 2) if len(t_malo) else 0.0)
    t0 = min(t0, t[-1] - 10)
    ventana = (t >= t0) & (t <= t0 + 10)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))
    ax1.plot(t[ventana], abp[ventana], color="black", linewidth=0.8)
    for p, malo in zip(r["picos"], r["malo"]):
        if t0 <= p / fs <= t0 + 10:
            ax1.plot(p / fs, abp[p], "o", color="red" if malo else "green", markersize=6)
    for v in r["valles"]:
        if t0 <= v / fs <= t0 + 10:
            ax1.plot(v / fs, abp[v], "x", color="blue", markersize=6)
    ax1.set_title(f"Paciente {subject_id}: 10 s de {canal} (verde = latido normal, rojo = anormal, x azul = valle)")
    ax1.set_xlabel("Tiempo dentro del tramo (s)")
    ax1.set_ylabel("mmHg")

    ax2.scatter(r["picos"] / fs / 60, r["pp"], s=4,
                c=np.where(r["malo"], "red", "green"))
    ax2.axhline(PP_MIN, color="gray", linestyle="--", label="Umbral de Sun (30 mmHg)")
    ax2.set_title("Presión de pulso de cada latido a lo largo del tramo")
    ax2.set_xlabel("Tiempo dentro del tramo (min)")
    ax2.set_ylabel("Presión de pulso (mmHg)")
    ax2.legend()

    fig.tight_layout()
    ruta = os.path.join(CARPETA, f"diagnostico_{subject_id}.png")
    fig.savefig(ruta, dpi=120)
    plt.close(fig)
    print(f"Gráfico guardado: {ruta}")