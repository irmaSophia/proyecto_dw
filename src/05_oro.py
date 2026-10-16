import duckdb
from config import DB

con = duckdb.connect(str(DB))

# ---------- dim_canal ----------
con.execute("""
CREATE OR REPLACE TABLE gold.dim_canal AS
SELECT sk_canal, nombre, es_digital
FROM silver.dim_canal
""")

# ---------- dim_tiempo (sin fecha_hora, que solo servía para el join) ----------
con.execute("""
CREATE OR REPLACE TABLE gold.dim_tiempo AS
SELECT sk_tiempo, fecha, anio, hora, trimestre, mes, nombre_mes,
       dia, dia_semana, nombre_dia, es_fin_semana, es_festivo,
       tipo_dia, franja_horaria
FROM silver.dim_tiempo
""")

# ---------- hecho_transaccion (granularidad: hora x canal) ----------
con.execute("""
CREATE OR REPLACE TABLE gold.hecho_transaccion AS
SELECT
    dt.sk_tiempo,
    dc.sk_canal,
    CAST(SUM(t.monto) AS DECIMAL(15,2))                                          AS monto_total,
    CAST(AVG(t.monto) AS DECIMAL(15,2))                                          AS monto_promedio,
    CAST(COALESCE(SUM(t.monto) FILTER (WHERE t.es_negativa), 0) AS DECIMAL(15,2))     AS monto_negativo,
    CAST(COALESCE(SUM(t.monto) FILTER (WHERE NOT t.es_negativa), 0) AS DECIMAL(15,2)) AS monto_positivo,
    CAST(COUNT(*) FILTER (WHERE NOT t.es_negativa) AS INTEGER)                   AS cantidad_transacciones_positivas,
    CAST(COUNT(*) FILTER (WHERE t.es_negativa) AS INTEGER)                       AS cantidad_transacciones_negativas,
    CAST(COUNT(*) AS INTEGER)                                                    AS total_transacciones
FROM silver.transacciones t
JOIN silver.dim_tiempo dt ON dt.fecha_hora = t.fecha_hora
JOIN silver.dim_canal  dc ON dc.nombre     = t.canal
GROUP BY dt.sk_tiempo, dc.sk_canal
""")

# ---------- Validaciones de oro ----------
r = lambda q: con.execute(q).fetchone()[0]

filas = r("SELECT count(*) FROM gold.hecho_transaccion")
total = r("SELECT sum(total_transacciones) FROM gold.hecho_transaccion")
pos_neg = r("""SELECT sum(cantidad_transacciones_positivas + cantidad_transacciones_negativas)
               FROM gold.hecho_transaccion""")
monto_oro = r("SELECT sum(monto_total) FROM gold.hecho_transaccion")
monto_plata = r("SELECT sum(monto) FROM silver.transacciones")
huerfanos_t = r("""SELECT count(*) FROM gold.hecho_transaccion h
                   LEFT JOIN gold.dim_tiempo d USING (sk_tiempo) WHERE d.sk_tiempo IS NULL""")
huerfanos_c = r("""SELECT count(*) FROM gold.hecho_transaccion h
                   LEFT JOIN gold.dim_canal d USING (sk_canal) WHERE d.sk_canal IS NULL""")

print(f"Filas en hecho_transaccion : {filas:,}")
print(f"Suma total_transacciones   : {total:,}")
print(f"Suma positivas + negativas : {pos_neg:,}")
print(f"Monto oro vs plata         : {monto_oro:,.2f} vs {monto_plata:,.2f}")
print(f"Huérfanos tiempo / canal   : {huerfanos_t} / {huerfanos_c}")

assert total == 10_000_000, "El hecho no suma 10M transacciones"
assert pos_neg == total, "positivas + negativas no cuadra con el total"
assert abs(monto_oro - monto_plata) < 1, "El monto de oro no cuadra con plata"
assert huerfanos_t == 0 and huerfanos_c == 0, "Hay llaves sin dimensión"
print("Oro OK")
con.close()