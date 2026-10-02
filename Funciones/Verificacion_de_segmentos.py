# ============================================================
# PASO 4 - Verificación por segmentos
# Objetivo: para cada paciente candidato, encontrar la ventana
#           CONTINUA más larga con todos los canales que requiere
#           su rol, y listar las variables de sus numéricos.
# Solo se leen headers (no se descargan señales).
# ============================================================

import wfdb
import pandas as pd

# --- Rutas: copiá la ruta de RECORDS-numerics del script anterior ---
RUTA_DETALLE = "detalle_grabaciones.csv"
RUTA_NUM = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic iii - waveform - database\RECORDS-numerics"

BASE_PHYSIONET = "mimic3wdb-matched/1.0"
VENTANA_MINIMA_MIN = 30
ARTERIAL = {"ABP", "ART"}

# --- Roles decididos en el paso 3 ----------------------------
ROLES = {
    "critico":  [10045, 41976, 42075, 42302, 43798, 43827, 44083],
    "verde":    [10083, 10124, 40601, 41795, 42033, 42199, 42367, 43870],
    "suplente": [10013, 10061],
}


def cumple(canales, rol):
    """True si el conjunto de canales tiene todo lo que exige el rol."""
    canales = set(canales or [])
    tiene_ii = "II" in canales
    tiene_abp = bool(canales & ARTERIAL)
    tiene_pleth = "PLETH" in canales
    if rol == "critico":
        return tiene_ii and tiene_abp and tiene_pleth
    if rol == "verde":
        return tiene_ii and tiene_pleth
    return tiene_ii and tiene_abp          # suplente


def ventana_mas_larga(linea, rol):
    """Recorre los segmentos de una grabación y devuelve
    (duración en minutos, segundo de inicio) de la ventana continua más larga."""
    carpeta, nombre = linea.rsplit("/", 1)
    pn_dir = f"{BASE_PHYSIONET}/{carpeta}"
    header = wfdb.rdheader(nombre, pn_dir=pn_dir, rd_segments=True)
    fs = header.fs

    # Grabación de un solo bloque (sin segmentos)
    if not isinstance(header, wfdb.MultiRecord):
        if cumple(header.sig_name, rol):
            return header.sig_len / fs / 60, 0.0
        return 0.0, None

    mejor_largo, mejor_inicio = 0, None
    largo_actual, inicio_actual = 0, 0
    posicion = 0   # en muestras, desde el comienzo de la grabación

    for nombre_seg, largo_seg, segmento in zip(header.seg_name, header.seg_len, header.segments):
        if nombre_seg.endswith("_layout"):
            continue   # el layout solo describe canales, no ocupa tiempo

        valido = (nombre_seg != "~" and segmento is not None
                  and cumple(segmento.sig_name, rol))

        if valido:
            if largo_actual == 0:
                inicio_actual = posicion
            largo_actual += largo_seg
            if largo_actual > mejor_largo:
                mejor_largo, mejor_inicio = largo_actual, inicio_actual
        else:
            largo_actual = 0   # hueco o canal faltante: se corta la ventana

        posicion += largo_seg

    inicio_s = mejor_inicio / fs if mejor_inicio is not None else None
    return mejor_largo / fs / 60, inicio_s


def variables_numericos(linea):
    """Devuelve el conjunto de variables de una grabación de numéricos."""
    carpeta, nombre = linea.rsplit("/", 1)
    pn_dir = f"{BASE_PHYSIONET}/{carpeta}"
    header = wfdb.rdheader(nombre, pn_dir=pn_dir)
    if isinstance(header, wfdb.MultiRecord):
        layout = [s for s in header.seg_name if s.endswith("_layout")]
        primero = layout or [s for s in header.seg_name if s != "~"][:1]
        header = wfdb.rdheader(primero[0], pn_dir=pn_dir)
    return set(header.sig_name or [])


# --- Datos de entrada ----------------------------------------
detalle = pd.read_csv(RUTA_DETALLE)
detalle["canales"] = detalle["canales"].fillna("")

with open(RUTA_NUM) as archivo:
    lineas_num = archivo.read().split()


# --- Recorrido principal -------------------------------------
filas = []
for rol, pacientes in ROLES.items():
    for subject_id in pacientes:
        print(f"\n[{rol}] Paciente {subject_id}")
        fila = {"subject_id": subject_id, "rol": rol, "mejor_grabacion": "",
                "ventana_max_min": 0.0, "inicio_ventana_s": None,
                "variables_numericos": "", "errores": ""}
        errores = []

        # Ondas: solo las grabaciones que a nivel general ya tienen los canales
        grabaciones = detalle[detalle["subject_id"] == subject_id]
        for _, g in grabaciones.iterrows():
            canales = {c.strip() for c in g["canales"].split(",") if c.strip()}
            if not cumple(canales, rol):
                continue
            print(f"   Revisando segmentos de {g['grabacion']} ...")
            try:
                minutos, inicio_s = ventana_mas_larga(g["grabacion"], rol)
                if minutos > fila["ventana_max_min"]:
                    fila["ventana_max_min"] = round(minutos, 1)
                    fila["inicio_ventana_s"] = inicio_s
                    fila["mejor_grabacion"] = g["grabacion"]
            except Exception as e:
                errores.append(f"{g['grabacion']}: {e}")

        # Numéricos: unión de variables de todas sus grabaciones
        variables = set()
        propias = [l for l in lineas_num if int(l.split("/")[1][1:]) == subject_id]
        for linea in propias:
            try:
                variables |= variables_numericos(linea)
            except Exception as e:
                errores.append(f"{linea}: {e}")
        fila["variables_numericos"] = ", ".join(sorted(variables))

        fila["cumple_30min"] = fila["ventana_max_min"] >= VENTANA_MINIMA_MIN
        fila["errores"] = " | ".join(errores)
        print(f"   Ventana continua más larga: {fila['ventana_max_min']} min")
        filas.append(fila)


# --- Resultados ----------------------------------------------
resultado = pd.DataFrame(filas)
resultado.to_csv("verificacion_segmentos.csv", index=False)

print("\n===== VENTANAS CONTINUAS =====")
print(resultado[["subject_id", "rol", "ventana_max_min", "cumple_30min"]].to_string(index=False))

print("\n===== VARIABLES DE NUMÉRICOS =====")
for _, f in resultado.iterrows():
    print(f"{f['subject_id']}: {f['variables_numericos']}")

print("\n===== CUMPLEN 30 MINUTOS =====")
for rol in ROLES:
    sub = resultado[resultado["rol"] == rol]
    print(f"{rol}: {sub['cumple_30min'].sum()} de {len(sub)}")

con_errores = resultado[resultado["errores"] != ""]
if not con_errores.empty:
    print(f"\nAtención: {len(con_errores)} paciente(s) con errores (ver verificacion_segmentos.csv)")

print("\nArchivo guardado: verificacion_segmentos.csv")