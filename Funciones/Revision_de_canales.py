# ============================================================
# PASO 2 - Revisión de canales de los pacientes comunes
# Objetivo: saber cuáles de los 19 pacientes tienen ondas con
#           ECG II, presión arterial (ABP) y PLETH, y cuánto duran.
# Solo se leen los headers (encabezados), no se descargan señales.
# ============================================================

import wfdb
import pandas as pd

# --- Rutas: ajustá las dos de RECORDS según dónde los guardaste ---
RUTA_COMUNES = "pacientes_comunes.csv"
RUTA_WAVE = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic iii - waveform - database\RECORDS-waveforms"
RUTA_NUM = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic iii - waveform - database\RECORDS-numerics"

BASE_PHYSIONET = "mimic3wdb-matched/1.0"
ARTERIAL = {"ABP", "ART"}   # según el monitor, la presión arterial aparece con uno u otro nombre


# --- 1. Filtrar los índices a nuestros 19 pacientes ----------
comunes = set(pd.read_csv(RUTA_COMUNES)["subject_id"])

def leer_indice(ruta):
    """Devuelve las líneas del índice que pertenecen a pacientes comunes."""
    with open(ruta) as archivo:
        lineas = archivo.read().split()
    # Línea típica: 'p00/p000020/p000020-2183-04-28-17-47'
    # El segundo tramo ('p000020') es la carpeta del paciente -> 20
    return [l for l in lineas if int(l.split("/")[1][1:]) in comunes]

registros_wave = leer_indice(RUTA_WAVE)
registros_num = leer_indice(RUTA_NUM)
print(f"Grabaciones de ondas de nuestros pacientes: {len(registros_wave)}")
print(f"Grabaciones de numéricos de nuestros pacientes: {len(registros_num)}")


# --- 2. Leer el header de cada grabación de ondas ------------
def revisar_grabacion(linea):
    """Lee el header de una grabación y devuelve sus canales y su duración en horas."""
    carpeta, nombre = linea.rsplit("/", 1)
    pn_dir = f"{BASE_PHYSIONET}/{carpeta}"
    header = wfdb.rdheader(nombre, pn_dir=pn_dir)

    if isinstance(header, wfdb.MultiRecord):
        # Grabación dividida en segmentos: los canales están en el segmento '_layout'
        layout = [s for s in header.seg_name if s.endswith("_layout")]
        if layout:
            header_canales = wfdb.rdheader(layout[0], pn_dir=pn_dir)
        else:
            primer_segmento = [s for s in header.seg_name if s != "~"][0]
            header_canales = wfdb.rdheader(primer_segmento, pn_dir=pn_dir)
        canales = set(header_canales.sig_name or [])
    else:
        canales = set(header.sig_name or [])

    duracion_h = header.sig_len / header.fs / 3600
    return canales, duracion_h

filas = []
for i, linea in enumerate(registros_wave, start=1):
    subject_id = int(linea.split("/")[1][1:])
    print(f"  [{i}/{len(registros_wave)}] Revisando {linea} ...")
    try:
        canales, duracion_h = revisar_grabacion(linea)
        filas.append({
            "subject_id": subject_id,
            "grabacion": linea,
            "canales": ", ".join(sorted(canales)),
            "tiene_II": "II" in canales,
            "tiene_ABP": bool(canales & ARTERIAL),
            "tiene_PLETH": "PLETH" in canales,
            "duracion_h": round(duracion_h, 1),
            "error": "",
        })
    except Exception as e:
        # Si una grabación falla, la anotamos y seguimos con las demás
        filas.append({"subject_id": subject_id, "grabacion": linea, "error": str(e)})

detalle = pd.DataFrame(filas)
detalle.to_csv("detalle_grabaciones.csv", index=False)


# --- 3. Tabla resumen: una fila por paciente -----------------
ids_con_numericos = {int(l.split("/")[1][1:]) for l in registros_num}

resumen = []
for subject_id in sorted(comunes):
    graba = detalle[detalle["subject_id"] == subject_id] if not detalle.empty else pd.DataFrame()
    completas = graba[graba.get("tiene_II", False) & graba.get("tiene_ABP", False)
                      & graba.get("tiene_PLETH", False)] if not graba.empty else graba
    resumen.append({
        "subject_id": subject_id,
        "tiene_ondas": not graba.empty,
        "tiene_numericos": subject_id in ids_con_numericos,
        "grabaciones_con_3_canales": len(completas),
        "duracion_max_h": completas["duracion_h"].max() if not completas.empty else 0,
    })

resumen = pd.DataFrame(resumen)
resumen.to_csv("resumen_candidatos.csv", index=False)

print("\n===== RESUMEN POR PACIENTE =====")
print(resumen.to_string(index=False))
print(f"\nPacientes con al menos una grabación con II + ABP + PLETH: "
      f"{(resumen['grabaciones_con_3_canales'] > 0).sum()} de {len(resumen)}")
print("Archivos guardados: detalle_grabaciones.csv y resumen_candidatos.csv")