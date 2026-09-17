#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import os
# Rutas exactas a tu base de datos MIMIC-IV Demo
ruta_icu = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\icu"
ruta_hosp = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\DataBase\mimic-iv-clinical-database-demo-2.2\hosp"
ruta_chartevents = os.path.join(ruta_icu, "chartevents.csv.gz")
ruta_d_items = os.path.join(ruta_icu, "d_items.csv.gz")

print("1. Cargando diccionario clínico (d_items)...")
# Cargamos el diccionario que traduce el ID a un nombre legible por humanos
d_items = pd.read_csv(ruta_d_items, usecols=['itemid', 'label', 'category'])

print("2. Escaneando la totalidad de chartevents (esto puede tardar unos segundos)...")
# Leemos solo las columnas vitales para no saturar la memoria RAM
df_chart = pd.read_csv(ruta_chartevents, usecols=['stay_id', 'itemid', 'valuenum'])

print("3. Calculando métricas de densidad y frecuencia...")
total_estadias = df_chart['stay_id'].nunique()

# Agrupamos por sensor (itemid) y contamos todo
analisis = df_chart.groupby('itemid').agg(
    Total_Registros=('stay_id', 'count'),                   # Cuántas veces sonó este sensor en total
    Pacientes_Distintos=('stay_id', 'nunique'),             # En cuántos pacientes distintos se usó
    Registros_Numericos_Validos=('valuenum', 'count')       # Cuántos de esos datos son números (no texto)
).reset_index()

# 4. Cálculo del índice de presencia (Sparsity)
analisis['%_Pacientes_Con_Dato'] = (analisis['Pacientes_Distintos'] / total_estadias) * 100

# 5. Cruzamos la matemática con los nombres reales del diccionario
reporte_final = pd.merge(analisis, d_items, on='itemid', how='left')

# Ordenamos de mayor a menor importancia (los más registrados arriba)
reporte_final = reporte_final.sort_values(by='Total_Registros', ascending=False)

# Reordenamos las columnas para que el Excel quede prolijo
columnas_orden = ['itemid', 'label', 'category', 'Total_Registros', '%_Pacientes_Con_Dato', 'Registros_Numericos_Validos']
reporte_final = reporte_final[columnas_orden]

print("\n==================================================================")
print(" TOP 20 PARÁMETROS MÁS ÚTILES EN LA UTI (MIMIC-IV DEMO) ")
print("==================================================================")
# Imprimimos los 20 mejores en consola
print(reporte_final.head(20).to_string(index=False))

# 6. Exportación para tu Tesis
ruta_exportacion = r"C:\Users\maxim\OneDrive\Escritorio\PROYECTO INTEGRADOR\SCRIPTS\Analisis_Parametros_Tesis.csv"
# Lo guardamos con separador ';' y coma decimal para que abra perfecto en Excel español
reporte_final.to_csv(ruta_exportacion, index=False, sep=';', decimal=',')

print("\n==================================================================")
print(f"✅ ¡Análisis completo guardado exitosamente en: {ruta_exportacion}!")
print("==================================================================")

