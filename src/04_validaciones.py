import duckdb
from config import DB

con = duckdb.connect(str(DB), read_only=True)
consultas = {
 "Total y origen": """SELECT origen_registro, count(*) n FROM silver.transacciones GROUP BY 1""",
 "Rango de fechas": """SELECT min(fecha_hora) AS desde, max(fecha_hora) AS hasta FROM silver.transacciones""",
 "Nulos críticos": """SELECT count(*) FILTER (WHERE canal IS NULL) canal_null,
                             count(*) FILTER (WHERE fecha_hora IS NULL) fecha_null,
                             count(*) FILTER (WHERE monto IS NULL) monto_null
                      FROM silver.transacciones""",
 "IDs duplicados": """SELECT count(*) - count(DISTINCT id_transaccion) AS duplicados FROM silver.transacciones""",
 "Tasa negativa por canal": """SELECT canal, count(*) n,
                             round(100*avg(es_negativa::INT),2) pct_negativa
                             FROM silver.transacciones GROUP BY 1 ORDER BY 3 DESC""",
 "% saldo insuficiente": """SELECT round(100*avg(saldo_insuficiente::INT),2) pct FROM silver.transacciones""",
 "Negativas por franja": """SELECT franja_horaria, count(*) n,
                             round(100*avg(es_negativa::INT),2) pct_negativa
                             FROM silver.transacciones GROUP BY 1 ORDER BY 1""",
 "Volumen por mes": """SELECT strftime(fecha_hora,'%Y-%m') mes, count(*) n
                       FROM silver.transacciones GROUP BY 1 ORDER BY 1""",
 "Tipo de día": """SELECT tipo_dia, count(*) n FROM silver.transacciones GROUP BY 1""",
 "Filas dim_tiempo (esperado 13128)": "SELECT count(*) FROM silver.dim_tiempo",
 "Canales": "SELECT * FROM silver.dim_canal ORDER BY sk_canal",
}
for titulo, sql in consultas.items():
    print(f"\n=== {titulo} ===")
    con.sql(sql).show()