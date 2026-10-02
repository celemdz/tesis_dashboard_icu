# ============================================================
# PASO 5b - Revisión del paciente 41976
# Objetivo: encontrar TODAS sus ventanas continuas >= 30 min con
#           II + ABP + PLETH y ver si alguna cae dentro de una
#           estadía en UTI de la Demo.
# Lee headers desde PhysioNet (necesita internet).
# ============================================================

from datetime import datetime, timedelta
import wfdb
import pandas as pd

# --- Rutas: copiá la de ICUSTAYS del script del paso 5 --------
RUTA_DETALLE = "detalle_grabaciones.csv"
RUTA_ICUSTAYS = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iii-clinical-database-demo-1.4\mimic-iii-clinical-database-demo-1.4\ICUSTAYS.csv"

SUBJECT_ID = 41976
BASE_PHYSIONET = "mimic3wdb-matched/1.0"
VENTANA_MINIMA = timedelta(minutes=30)
ARTERIAL = {"ABP", "ART"}


def cumple(canales):
    canales = set(canales or [])
    return "II" in canales and "PLETH" in canales and bool(canales & ARTERIAL)


def inicio_grabacion(linea):
    nombre = linea.rsplit("/", 1)[1]
    return datetime.strptime(nombre.split("-", 1)[1], "%Y-%m-%d-%H-%M")


def todas_las_ventanas(linea):
    """Devuelve una lista de (inicio_s, duracion_s) con todas las ventanas continuas válidas."""
    carpeta, nombre = linea.rsplit("/", 1)
    pn_dir = f"{BASE_PHYSIONET}/{carpeta}"
    header = wfdb.rdheader(nombre, pn_dir=pn_dir, rd_segments=True)
    fs = header.fs

    if not isinstance(header, wfdb.MultiRecord):
        return [(0.0, header.sig_len / fs)] if cumple(header.sig_name) else []

    ventanas = []
    largo_actual, inicio_actual, posicion = 0, 0, 0
    for nombre_seg, largo_seg, segmento in zip(header.seg_name, header.seg_len, header.segments):
        if nombre_seg.endswith("_layout"):
            continue
        valido = nombre_seg != "~" and segmento is not None and cumple(segmento.sig_name)
        if valido:
            if largo_actual == 0:
                inicio_actual = posicion
            largo_actual += largo_seg
        else:
            if largo_actual > 0:
                ventanas.append((inicio_actual / fs, largo_actual / fs))
            largo_actual = 0
        posicion += largo_seg
    if largo_actual > 0:   # la última ventana, si la grabación termina en una
        ventanas.append((inicio_actual / fs, largo_actual / fs))

    return [v for v in ventanas if v[1] >= VENTANA_MINIMA.total_seconds()]


# --- Datos de entrada ----------------------------------------
detalle = pd.read_csv(RUTA_DETALLE)
detalle["canales"] = detalle["canales"].fillna("")
grabaciones = detalle[detalle["subject_id"] == SUBJECT_ID]

estadias = pd.read_csv(RUTA_ICUSTAYS)
estadias.columns = estadias.columns.str.lower()
estadias = estadias[estadias["subject_id"] == SUBJECT_ID].copy()
estadias["intime"] = pd.to_datetime(estadias["intime"])
estadias["outtime"] = pd.to_datetime(estadias["outtime"])


# --- Recorrido -----------------------------------------------
filas = []
for _, g in grabaciones.iterrows():
    canales = {c.strip() for c in g["canales"].split(",") if c.strip()}
    if not cumple(canales):
        continue
    print(f"Revisando segmentos de {g['grabacion']} ...")
    base = inicio_grabacion(g["grabacion"])

    for inicio_s, duracion_s in todas_las_ventanas(g["grabacion"]):
        v_ini = base + timedelta(seconds=inicio_s)
        v_fin = v_ini + timedelta(seconds=duracion_s)
        fila = {"grabacion": g["grabacion"].rsplit("/", 1)[1],
                "ventana_inicio": v_ini.strftime("%Y-%m-%d %H:%M"),
                "ventana_fin": v_fin.strftime("%Y-%m-%d %H:%M"),
                "duracion_min": round(duracion_s / 60, 1),
                "icustay_id": None, "horas_previas_max": 0.0}

        for _, e in estadias.iterrows():
            sup_ini, sup_fin = max(v_ini, e["intime"]), min(v_fin, e["outtime"])
            if sup_fin - sup_ini >= VENTANA_MINIMA:
                tramo_ini = sup_fin - VENTANA_MINIMA
                horas = (tramo_ini - e["intime"]).total_seconds() / 3600
                if horas > fila["horas_previas_max"]:
                    fila["icustay_id"] = e["icustay_id"]
                    fila["horas_previas_max"] = round(horas, 1)

        fila["coincide"] = fila["icustay_id"] is not None
        filas.append(fila)


# --- Resultados ----------------------------------------------
resultado = pd.DataFrame(filas)
print(f"\n===== VENTANAS DE {SUBJECT_ID} (>= 30 min con II + ABP + PLETH) =====")
if resultado.empty:
    print("No se encontraron ventanas válidas.")
else:
    print(resultado.to_string(index=False))
    resultado.to_csv("revision_41976.csv", index=False)
    n = resultado["coincide"].sum()
    print(f"\nVentanas que coinciden con una estadía en UTI: {n} de {len(resultado)}")
    print("Archivo guardado: revision_41976.csv")