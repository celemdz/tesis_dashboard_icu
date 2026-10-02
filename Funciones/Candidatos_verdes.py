# ============================================================
# PASO 3 - Candidatos a cama verde
# Objetivo: entre los pacientes que NO tienen II + ABP + PLETH,
#           ver cuáles tienen al menos II + PLETH y qué les falta.
# Usa el archivo generado en el paso 2 (no necesita internet).
# ============================================================

import pandas as pd

ARTERIAL = {"ABP", "ART"}

# --- 1. Leer el detalle del paso 2 ---------------------------
detalle = pd.read_csv("detalle_grabaciones.csv")
detalle["canales"] = detalle["canales"].fillna("")

# Convertimos el texto "ABP, II, PLETH" en un conjunto {"ABP", "II", "PLETH"}
detalle["set_canales"] = detalle["canales"].apply(
    lambda texto: {c.strip() for c in texto.split(",") if c.strip()}
)

def es_completa(canales):
    return "II" in canales and "PLETH" in canales and bool(canales & ARTERIAL)

def es_verde(canales):
    return "II" in canales and "PLETH" in canales

detalle["completa"] = detalle["set_canales"].apply(es_completa)
detalle["verde"] = detalle["set_canales"].apply(es_verde)


# --- 2. Separar a los pacientes restantes y revisar cada uno --
criticos = set(detalle.loc[detalle["completa"], "subject_id"])
restantes = sorted(set(detalle["subject_id"]) - criticos)
print(f"Candidatos críticos (II + ABP + PLETH): {len(criticos)}")
print(f"Pacientes restantes a revisar: {len(restantes)}\n")

filas = []
for subject_id in restantes:
    grabaciones = detalle[detalle["subject_id"] == subject_id]
    todos_los_canales = set().union(*grabaciones["set_canales"])
    verdes = grabaciones[grabaciones["verde"]]

    # Qué le falta respecto del set completo
    falta = []
    if "II" not in todos_los_canales:
        falta.append("II")
    if "PLETH" not in todos_los_canales:
        falta.append("PLETH")
    if not (todos_los_canales & ARTERIAL):
        falta.append("ABP")

    filas.append({
        "subject_id": subject_id,
        "grabaciones": len(grabaciones),
        "con_II_y_PLETH": len(verdes),
        "duracion_max_h": verdes["duracion_h"].max() if not verdes.empty else 0,
        "le_falta": ", ".join(falta) if falta else "-",
        "canales_disponibles": ", ".join(sorted(todos_los_canales)),
    })


# --- 3. Mostrar y guardar ------------------------------------
resultado = pd.DataFrame(filas)
resultado.to_csv("candidatos_verdes.csv", index=False)

print("===== PACIENTES RESTANTES =====")
print(resultado.drop(columns="canales_disponibles").to_string(index=False))

print("\n===== CANALES DISPONIBLES POR PACIENTE =====")
for _, fila in resultado.iterrows():
    print(f"{fila['subject_id']}: {fila['canales_disponibles']}")

n_verdes = (resultado["con_II_y_PLETH"] > 0).sum()
print(f"\nPacientes con al menos una grabación con II + PLETH: {n_verdes} de {len(resultado)}")
print("Archivo guardado: candidatos_verdes.csv")