import duckdb, holidays
import numpy as np
import pandas as pd
from config import *

con = duckdb.connect(str(DB))
con.execute(f"SELECT setseed({SEMILLA})")

# ---------- 1. Calendario (festivos + pesos de actividad) ----------
dias = pd.date_range(FECHA_INICIO, periods=N_DIAS)
fest = holidays.country_holidays(PAIS_FESTIVOS, years=sorted({d.year for d in dias}))
cal = pd.DataFrame({"fecha": dias.date})
cal["es_festivo"] = cal["fecha"].isin(set(fest.keys()))
cal["es_fin_semana"] = dias.dayofweek >= 5
cal["peso"] = (
    np.linspace(1.0, 1.6, N_DIAS)                    # tendencia de crecimiento
    * np.where(cal["es_fin_semana"], 0.7, 1.0)       # menos actividad en fin de semana
    * np.where(cal["es_festivo"], 0.7, 1.0)          # y en festivos
)
con.register("cal_df", cal)
con.execute("""
CREATE OR REPLACE TABLE silver.calendario AS
SELECT fecha, es_festivo, es_fin_semana,
       CASE WHEN es_festivo THEN 'Festivo'
            WHEN es_fin_semana THEN 'Fin de semana'
            ELSE 'Habil' END AS tipo_dia,
       peso,
       (SUM(peso) OVER (ORDER BY fecha) - peso) / SUM(peso) OVER () AS cum_ini
FROM cal_df
""")

# ---------- 2. Expansión a 10M (remuestreo con reemplazo) ----------
n = con.execute("SELECT count(*) FROM silver.paysim_valida").fetchone()[0]
faltan = OBJETIVO_FILAS - n
print(f"Válidas: {n:,} | a generar: {faltan:,}")

con.execute(f"""
CREATE OR REPLACE TABLE silver.tmp_muestra AS
SELECT 1 + floor(random() * {n})::BIGINT AS rn_sel,
       1 - random()                      AS u1,
       random()                          AS u2
FROM range({faltan})
""")

con.execute("""
CREATE OR REPLACE TABLE silver.tmp_expandida AS
SELECT _nro_fila, step, tipo, monto,
       cliente_origen, saldo_ini_origen, saldo_fin_origen,
       cliente_destino, saldo_ini_destino, saldo_fin_destino,
       es_fraude, es_fraude_marcado,
       'original' AS origen_registro
FROM silver.paysim_valida
UNION ALL
SELECT v._nro_fila, v.step, v.tipo,
       -- monto * lognormal(0, 0.15) usando Box-Muller
       CAST(round(v.monto * exp(0.15 * sqrt(-2 * ln(m.u1)) * cos(2 * pi() * m.u2)), 2)
            AS DECIMAL(15,2)) AS monto,
       v.cliente_origen, v.saldo_ini_origen, v.saldo_fin_origen,
       v.cliente_destino, v.saldo_ini_destino, v.saldo_fin_destino,
       v.es_fraude, v.es_fraude_marcado,
       'sintetico' AS origen_registro
FROM silver.tmp_muestra m
JOIN silver.paysim_valida v ON v.rn = m.rn_sel
""")

# ---------- 3. Números aleatorios (materializados) + fecha ----------
con.execute("""
CREATE OR REPLACE TABLE silver.tmp_azar AS
SELECT row_number() OVER () AS id_transaccion, e.*,
       random() AS u_dia, random() AS u_canal, random() AS u_fallo
FROM silver.tmp_expandida e
""")

con.execute("""
CREATE OR REPLACE TABLE silver.tmp_fecha AS
SELECT a.*, c.fecha, c.es_festivo, c.es_fin_semana, c.tipo_dia
FROM silver.tmp_azar a
ASOF JOIN silver.calendario c ON a.u_dia >= c.cum_ini
""")

# ---------- 4. Tabla final de plata ----------
con.execute("""
CREATE OR REPLACE TABLE silver.transacciones AS
WITH c AS (
    SELECT f.*,
        CAST((f.step - 1) % 24 AS SMALLINT)                           AS hora,
        CAST(f.fecha AS TIMESTAMP)
            + to_hours(CAST((f.step - 1) % 24 AS BIGINT))             AS fecha_hora,
        CASE f.tipo
          WHEN 'PAYMENT'  THEN CASE WHEN u_canal < .35 THEN 'Web'    WHEN u_canal < .80 THEN 'App'     ELSE 'POS'      END
          WHEN 'TRANSFER' THEN CASE WHEN u_canal < .40 THEN 'Web'    WHEN u_canal < .90 THEN 'App'     ELSE 'Sucursal' END
          WHEN 'CASH_OUT' THEN CASE WHEN u_canal < .50 THEN 'Cajero' WHEN u_canal < .80 THEN 'Corresp' ELSE 'Sucursal' END
          WHEN 'CASH_IN'  THEN CASE WHEN u_canal < .40 THEN 'Cajero' WHEN u_canal < .80 THEN 'Corresp' ELSE 'Sucursal' END
          WHEN 'DEBIT'    THEN CASE WHEN u_canal < .40 THEN 'Cajero' WHEN u_canal < .80 THEN 'POS'     ELSE 'Web'      END
        END AS canal
    FROM silver.tmp_fecha f
),
d AS (
    SELECT c.*,
        canal IN ('Web','App') AS es_digital,
        CASE WHEN hora <= 5  THEN 'Madrugada'
             WHEN hora <= 11 THEN 'Manana'
             WHEN hora <= 17 THEN 'Tarde'
             ELSE 'Noche' END AS franja_horaria,
        (tipo IN ('TRANSFER','CASH_OUT','PAYMENT','DEBIT')
            AND monto > saldo_ini_origen) AS saldo_insuficiente,
        (u_fallo <
            CASE canal WHEN 'Web' THEN .06 WHEN 'App' THEN .03 WHEN 'POS' THEN .04
                       WHEN 'Cajero' THEN .05 WHEN 'Corresp' THEN .05 ELSE .02 END
            + CASE WHEN hora < 6 THEN .03 ELSE 0 END
        ) AS fallo_sintetico
    FROM c
)
SELECT * EXCLUDE (u_dia, u_canal, u_fallo),
       (es_fraude OR es_fraude_marcado OR fallo_sintetico) AS es_negativa
FROM d
""")

# ---------- 5. Dimensiones de plata ----------
con.execute("""
CREATE OR REPLACE TABLE silver.dim_canal AS
SELECT CAST(row_number() OVER (ORDER BY canal) AS SMALLINT) AS sk_canal,
       canal AS nombre, es_digital
FROM (SELECT DISTINCT canal, es_digital FROM silver.transacciones)
""")

con.execute("""
CREATE OR REPLACE TABLE silver.dim_tiempo AS
SELECT CAST(row_number() OVER (ORDER BY ts) AS INTEGER) AS sk_tiempo,
       ts                                   AS fecha_hora,
       CAST(ts AS DATE)                     AS fecha,
       CAST(year(ts)    AS SMALLINT)        AS anio,
       CAST(hour(ts)    AS SMALLINT)        AS hora,
       CAST(quarter(ts) AS SMALLINT)        AS trimestre,
       CAST(month(ts)   AS SMALLINT)        AS mes,
       ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto',
        'Septiembre','Octubre','Noviembre','Diciembre'][month(ts)] AS nombre_mes,
       CAST(day(ts)     AS SMALLINT)        AS dia,
       CAST(isodow(ts)  AS SMALLINT)        AS dia_semana,
       ['Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo'][isodow(ts)] AS nombre_dia,
       es_fin_semana, es_festivo, tipo_dia,
       CASE WHEN hour(ts) <= 5  THEN 'Madrugada'
            WHEN hour(ts) <= 11 THEN 'Manana'
            WHEN hour(ts) <= 17 THEN 'Tarde'
            ELSE 'Noche' END                AS franja_horaria
FROM (
    SELECT CAST(c.fecha AS TIMESTAMP) + to_hours(h.hora) AS ts,
           c.es_fin_semana, c.es_festivo, c.tipo_dia
    FROM silver.calendario c, range(24) AS h(hora)
)
""")

# ---------- 6. Limpieza de temporales ----------
for t in ("tmp_muestra", "tmp_expandida", "tmp_azar", "tmp_fecha"):
    con.execute(f"DROP TABLE IF EXISTS silver.{t}")

print("Plata lista:", con.execute("SELECT count(*) FROM silver.transacciones").fetchone()[0])
con.close()