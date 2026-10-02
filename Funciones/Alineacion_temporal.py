# ============================================================
# PASO 5 - Alineación temporal: señales vs. estadías en UTI
# Objetivo: verificar que la ventana de señal de cada paciente
#           caiga dentro de una estadía en UTI de la Demo, y cuántas
#           horas de internación hay antes del tramo de 30 minutos.
# No necesita internet.
# ============================================================

from datetime import datetime, timedelta
import pandas as pd

# --- Rutas: ajustá la de ICUSTAYS según dónde está la Demo -----
RUTA_VERIFICACION = "verificacion_segmentos.csv"
RUTA_ICUSTAYS = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iii-clinical-database-demo-1.4\mimic-iii-clinical-database-demo-1.4\ICUSTAYS.csv"

TRAMO = timedelta(minutes=30)
HORAS_PREVIAS_MINIMAS = 24

# --- Cohorte confirmada --------------------------------------
COHORTE = {
    "critico":  [10045, 41976, 42075, 43798, 43827, 44083, 10013],
    "verde":    [10083, 10124, 40601, 41795, 42033, 42199, 42367, 43870],
    "suplente": [10061],
}


def inicio_grabacion(linea):
    """De 'p00/p000020/p000020-2183-04-28-17-47' obtiene la fecha y hora de inicio."""
    nombre = linea.rsplit("/", 1)[1]              # 'p000020-2183-04-28-17-47'
    fecha_texto = nombre.split("-", 1)[1]          # '2183-04-28-17-47'
    return datetime.strptime(fecha_texto, "%Y-%m-%d-%H-%M")


# --- Datos de entrada ----------------------------------------
verificacion = pd.read_csv(RUTA_VERIFICACION)

estadias = pd.read_csv(RUTA_ICUSTAYS)
estadias.columns = estadias.columns.str.lower()    # por si vienen en mayúscula
estadias["intime"] = pd.to_datetime(estadias["intime"])
estadias["outtime"] = pd.to_datetime(estadias["outtime"])


# --- Recorrido principal -------------------------------------
filas = []
sin_coincidencia = []

for rol, pacientes in COHORTE.items():
    for subject_id in pacientes:
        v = verificacion[verificacion["subject_id"] == subject_id].iloc[0]

        # 1. Cuándo empieza y termina la ventana de señal
        ventana_ini = inicio_grabacion(v["mejor_grabacion"]) + timedelta(seconds=float(v["inicio_ventana_s"]))
        ventana_fin = ventana_ini + timedelta(minutes=float(v["ventana_max_min"]))

        fila = {"subject_id": subject_id, "rol": rol,
                "ventana_inicio": ventana_ini, "ventana_fin": ventana_fin,
                "icustay_id": None, "dbsource": "", "unidad": "",
                "superposicion_min": 0.0, "horas_previas_max": 0.0}

        # 2. Buscar la estadía en UTI que se superpone con la ventana
        propias = estadias[estadias["subject_id"] == subject_id]
        for _, e in propias.iterrows():
            sup_ini = max(ventana_ini, e["intime"])
            sup_fin = min(ventana_fin, e["outtime"])
            superposicion = sup_fin - sup_ini
            if superposicion >= TRAMO:
                # Tramo de 30 min ubicado lo más tarde posible dentro de la superposición
                tramo_ini = sup_fin - TRAMO
                horas_previas = (tramo_ini - e["intime"]).total_seconds() / 3600
                if horas_previas > fila["horas_previas_max"]:
                    fila.update({
                        "icustay_id": e["icustay_id"],
                        "dbsource": e["dbsource"],
                        "unidad": e["first_careunit"],
                        "superposicion_min": round(superposicion.total_seconds() / 60, 1),
                        "horas_previas_max": round(horas_previas, 1),
                    })

        fila["coincide"] = fila["icustay_id"] is not None
        fila["cumple_24h"] = fila["horas_previas_max"] >= HORAS_PREVIAS_MINIMAS
        if not fila["coincide"]:
            sin_coincidencia.append((subject_id, ventana_ini, ventana_fin, propias))
        filas.append(fila)


# --- Resultados ----------------------------------------------
resultado = pd.DataFrame(filas)
resultado.to_csv("alineacion_temporal.csv", index=False)

print("===== ALINEACIÓN SEÑAL / ESTADÍA EN UTI =====")
columnas = ["subject_id", "rol", "coincide", "unidad", "dbsource",
            "superposicion_min", "horas_previas_max", "cumple_24h"]
print(resultado[columnas].to_string(index=False))

print("\n===== RESUMEN =====")
for rol in COHORTE:
    sub = resultado[resultado["rol"] == rol]
    print(f"{rol}: coinciden {sub['coincide'].sum()} de {len(sub)} | "
          f"con >= {HORAS_PREVIAS_MINIMAS} h previas: {sub['cumple_24h'].sum()}")

if sin_coincidencia:
    print("\n===== PACIENTES SIN COINCIDENCIA (para revisar) =====")
    for subject_id, ini, fin, propias in sin_coincidencia:
        print(f"\n{subject_id} | ventana: {ini} -> {fin}")
        if propias.empty:
            print("   No tiene estadías en ICUSTAYS de la Demo")
        for _, e in propias.iterrows():
            print(f"   Estadía {e['icustay_id']}: {e['intime']} -> {e['outtime']} ({e['dbsource']})")

print("\nArchivo guardado: alineacion_temporal.csv")