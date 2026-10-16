import duckdb
from config import DB, RAIZ

SALIDA = RAIZ / "data" / "resultados"
SALIDA.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB))

# Vista de apoyo: hecho + dimensiones, con nombres cortos
con.execute("""
CREATE OR REPLACE VIEW gold.v_hecho AS
SELECT h.sk_tiempo, h.sk_canal,
       h.monto_total, h.monto_negativo, h.monto_positivo,
       h.cantidad_transacciones_positivas AS positivas,
       h.cantidad_transacciones_negativas AS negativas,
       h.total_transacciones              AS total,
       t.fecha, t.anio, t.mes, t.nombre_mes, t.hora, t.nombre_dia,
       t.es_fin_semana, t.es_festivo, t.tipo_dia, t.franja_horaria,
       c.nombre AS canal, c.es_digital
FROM gold.hecho_transaccion h
JOIN gold.dim_tiempo t ON t.sk_tiempo = h.sk_tiempo
JOIN gold.dim_canal  c ON c.sk_canal  = h.sk_canal
""")

consultas = {}

# 1. Evolución del monto total por canal, mes y año
consultas["req01_monto_por_canal_mes"] = """
SELECT canal, anio, mes, sum(monto_total) AS monto_total
FROM gold.v_hecho
GROUP BY canal, anio, mes
ORDER BY canal, anio, mes"""

# 2. Ticket promedio por hora y canal (ponderado)
consultas["req02_ticket_por_hora_canal"] = """
SELECT canal, hora,
       sum(total) AS transacciones,
       round(sum(monto_total) / sum(total), 2) AS ticket_promedio
FROM gold.v_hecho
GROUP BY canal, hora
ORDER BY canal, hora"""

# 3. Horas pico: monto promedio por hora > promedio histórico de la plataforma
consultas["req03_picos_por_hora"] = """
WITH horas AS (
    SELECT t.sk_tiempo, t.hora, t.franja_horaria,
           COALESCE(sum(h.monto_total), 0) AS monto
    FROM gold.dim_tiempo t
    LEFT JOIN gold.hecho_transaccion h ON h.sk_tiempo = t.sk_tiempo
    GROUP BY t.sk_tiempo, t.hora, t.franja_horaria
),
promedio_global AS (SELECT avg(monto) AS prom FROM horas)
SELECT hora, franja_horaria,
       round(avg(monto), 2) AS monto_prom_en_esa_hora,
       round(pg.prom, 2)    AS promedio_historico_por_hora,
       avg(monto) > pg.prom AS es_pico
FROM horas CROSS JOIN promedio_global pg
GROUP BY hora, franja_horaria, pg.prom
ORDER BY hora"""

# 4. Tasa de transacciones negativas por canal
consultas["req04_tasa_negativas_canal"] = """
SELECT canal, sum(negativas) AS negativas, sum(total) AS total,
       round(100.0 * sum(negativas) / sum(total), 2) AS pct_negativas
FROM gold.v_hecho
GROUP BY canal
ORDER BY pct_negativas DESC"""

# 5. Negativas en horario nocturno y de madrugada
consultas["req05_negativas_noche_madrugada"] = """
SELECT franja_horaria, hora,
       sum(negativas) AS negativas, sum(total) AS total,
       round(100.0 * sum(negativas) / sum(total), 2) AS pct_negativas,
       round(sum(negativas) / (SELECT count(DISTINCT fecha) FROM gold.dim_tiempo), 1)
           AS negativas_prom_por_dia
FROM gold.v_hecho
WHERE franja_horaria IN ('Noche', 'Madrugada')
GROUP BY franja_horaria, hora
ORDER BY hora"""

# 6. Montos de operaciones negativas por franja vs. plataforma
consultas["req06_montos_negativas_franja"] = """
SELECT franja_horaria,
       round(100.0 * sum(negativas) / sum(total), 2)               AS pct_negativas,
       round(sum(monto_total) / sum(total), 2)                     AS ticket_franja,
       round(sum(monto_negativo) / NULLIF(sum(negativas), 0), 2)   AS ticket_negativas,
       round((SELECT sum(monto_total) / sum(total_transacciones)
              FROM gold.hecho_transaccion), 2)                     AS ticket_plataforma,
       round(100.0 * sum(monto_negativo) / sum(monto_total), 2)    AS pct_monto_negativo
FROM gold.v_hecho
GROUP BY franja_horaria
ORDER BY pct_negativas DESC"""

# 7. Ranking de canales por tasa de éxito
consultas["req07_ranking_exito_canal"] = """
SELECT rank() OVER (ORDER BY pct_exito DESC) AS ranking, canal,
       positivas, total, pct_exito
FROM (
    SELECT canal, sum(positivas) AS positivas, sum(total) AS total,
           round(100.0 * sum(positivas) / sum(total), 2) AS pct_exito
    FROM gold.v_hecho GROUP BY canal
)
ORDER BY ranking"""

# 8. Días hábiles vs fines de semana vs festivos (promedio por hora del calendario)
consultas["req08_tipo_dia"] = """
WITH horas AS (
    SELECT tipo_dia, count(*) AS horas_calendario
    FROM gold.dim_tiempo GROUP BY tipo_dia
),
agg AS (
    SELECT tipo_dia, sum(total) AS transacciones, sum(monto_total) AS monto
    FROM gold.v_hecho GROUP BY tipo_dia
)
SELECT a.tipo_dia, h.horas_calendario,
       round(a.transacciones / h.horas_calendario, 1) AS transacciones_prom_por_hora,
       round(a.monto / h.horas_calendario, 2)         AS monto_prom_por_hora
FROM agg a JOIN horas h ON h.tipo_dia = a.tipo_dia
ORDER BY transacciones_prom_por_hora DESC"""

# 9. Distribución horaria del volumen
consultas["req09_distribucion_horaria"] = """
SELECT hora, sum(total) AS transacciones,
       round(100.0 * sum(total) / sum(sum(total)) OVER (), 2) AS pct_del_total
FROM gold.v_hecho
GROUP BY hora
ORDER BY hora"""

# 10. Tendencia mensual del volumen por canal (con variación vs mes anterior)
consultas["req10_tendencia_mensual_canal"] = """
WITH m AS (
    SELECT canal, anio, mes, sum(total) AS transacciones
    FROM gold.v_hecho GROUP BY canal, anio, mes
)
SELECT canal, anio, mes, transacciones,
       round(100.0 * (transacciones - lag(transacciones) OVER w)
             / lag(transacciones) OVER w, 2) AS variacion_pct_vs_mes_anterior
FROM m
WINDOW w AS (PARTITION BY canal ORDER BY anio, mes)
ORDER BY canal, anio, mes"""

# 11. Participación de cada canal en el monto total
consultas["req11_participacion_canal"] = """
SELECT canal, sum(monto_total) AS monto_total,
       round(100.0 * sum(monto_total) / sum(sum(monto_total)) OVER (), 2) AS participacion_pct
FROM gold.v_hecho
GROUP BY canal
ORDER BY monto_total DESC"""

# 12. Promedio diario de negativas por canal
consultas["req12_promedio_diario_negativas"] = """
WITH dias AS (SELECT count(DISTINCT fecha) AS n_dias FROM gold.dim_tiempo)
SELECT canal, sum(negativas) AS negativas_totales, d.n_dias,
       round(sum(negativas) / d.n_dias, 1) AS negativas_prom_diarias
FROM gold.v_hecho CROSS JOIN dias d
GROUP BY canal, d.n_dias
ORDER BY negativas_prom_diarias DESC"""

# 13a. Web vs App por franja horaria
consultas["req13a_web_vs_app_franja"] = """
SELECT franja_horaria,
       sum(total) FILTER (WHERE canal IN ('Web','App'))            AS volumen_web_app,
       sum(positivas) FILTER (WHERE canal = 'Web')                 AS web_positivas,
       sum(negativas) FILTER (WHERE canal = 'Web')                 AS web_negativas,
       round(100.0 * sum(negativas) FILTER (WHERE canal = 'Web')
             / sum(total) FILTER (WHERE canal = 'Web'), 2)         AS web_pct_negativas,
       sum(positivas) FILTER (WHERE canal = 'App')                 AS app_positivas,
       sum(negativas) FILTER (WHERE canal = 'App')                 AS app_negativas,
       round(100.0 * sum(negativas) FILTER (WHERE canal = 'App')
             / sum(total) FILTER (WHERE canal = 'App'), 2)         AS app_pct_negativas
FROM gold.v_hecho
WHERE canal IN ('Web', 'App')
GROUP BY franja_horaria
ORDER BY volumen_web_app DESC"""

# 13b. Web vs App en las 5 horas de mayor demanda
consultas["req13b_web_vs_app_horas_pico"] = """
WITH top5 AS (
    SELECT hora FROM gold.v_hecho
    WHERE canal IN ('Web','App')
    GROUP BY hora ORDER BY sum(total) DESC LIMIT 5
)
SELECT hora, canal, sum(positivas) AS positivas, sum(negativas) AS negativas,
       sum(total) AS total,
       round(100.0 * sum(negativas) / sum(total), 2) AS pct_negativas
FROM gold.v_hecho
WHERE canal IN ('Web','App') AND hora IN (SELECT hora FROM top5)
GROUP BY hora, canal
ORDER BY hora, canal"""

for nombre, sql in consultas.items():
    print(f"\n=== {nombre} ===")
    con.sql(sql).show(max_rows=200)
    ruta = (SALIDA / f"{nombre}.csv").as_posix()
    con.execute(f"COPY ({sql}) TO '{ruta}' (HEADER, DELIMITER ',')")

print(f"\nCSV guardados en: {SALIDA}")
con.close()