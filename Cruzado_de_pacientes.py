# ============================================================
# PASO 1 - Cruce de pacientes: MIMIC-III Demo vs Waveform Matched Subset
# Objetivo: saber cuántos pacientes de la Demo tienen también
#           señales en el Matched Subset.
# ============================================================

import pandas as pd

# Ajustá esta ruta según dónde descomprimiste la Demo
RUTA_DEMO = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iii-clinical-database-demo-1.4\mimic-iii-clinical-database-demo-1.4\PATIENTS.csv"

# Índice público del Matched Subset en PhysioNet
URL_RECORDS = r"C:\Users\celes\Desktop\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic iii - waveform - database\RECORDS"

# --- 1. Pacientes de la Demo ---------------------------------
pacientes = pd.read_csv(RUTA_DEMO)
pacientes.columns = pacientes.columns.str.lower()   # por si vienen en mayúscula
ids_demo = set(pacientes["subject_id"])
print(f"Pacientes en la Demo: {len(ids_demo)}")


# --- 2. Pacientes del Matched Subset -------------------------
with open(URL_RECORDS) as archivo:
    lineas = archivo.read().split()

# Cada línea tiene la forma 'p00/p000020/'
# Nos quedamos con 'p000020', le sacamos la 'p' y lo pasamos a número -> 20
ids_wave = {int(linea.strip("/").split("/")[-1][1:]) for linea in lineas}
print(f"Pacientes en el Matched Subset: {len(ids_wave)}")


# --- 3. Intersección -----------------------------------------
comunes = sorted(ids_demo & ids_wave)
print(f"Pacientes en ambas bases: {len(comunes)}")
print(comunes)


# --- 4. Guardar el resultado ---------------------------------
pd.Series(comunes, name="subject_id").to_csv("pacientes_comunes.csv", index=False)
print("Lista guardada en pacientes_comunes.csv")