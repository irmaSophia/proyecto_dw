import duckdb
from config import DB

con = duckdb.connect(str(DB))

# 1) Tipar y renombrar a español
con.execute("""
CREATE OR REPLACE TABLE silver.paysim_tipada AS
SELECT
    _nro_fila,
    TRY_CAST(step AS INTEGER)                  AS step,
    upper(trim(type))                          AS tipo,
    TRY_CAST(amount AS DECIMAL(15,2))          AS monto,
    nameorig                                   AS cliente_origen,
    TRY_CAST(oldbalanceorg  AS DECIMAL(15,2))  AS saldo_ini_origen,
    TRY_CAST(newbalanceorig AS DECIMAL(15,2))  AS saldo_fin_origen,
    namedest                                   AS cliente_destino,
    TRY_CAST(oldbalancedest AS DECIMAL(15,2))  AS saldo_ini_destino,
    TRY_CAST(newbalancedest AS DECIMAL(15,2))  AS saldo_fin_destino,
    TRY_CAST(isfraud AS INTEGER) = 1           AS es_fraude,
    TRY_CAST(isflaggedfraud AS INTEGER) = 1    AS es_fraude_marcado
FROM bronze.paysim_raw
""")

# 2) Reglas de calidad: marcar el motivo de rechazo
con.execute("""
CREATE OR REPLACE TABLE silver.paysim_evaluada AS
SELECT *,
    CASE
        WHEN step IS NULL OR step NOT BETWEEN 1 AND 743           THEN 'step invalido'
        WHEN monto IS NULL OR monto <= 0                          THEN 'monto invalido'
        WHEN tipo NOT IN ('PAYMENT','TRANSFER','CASH_OUT','CASH_IN','DEBIT')
                                                                  THEN 'tipo fuera de catalogo'
        WHEN cliente_origen IS NULL OR cliente_destino IS NULL    THEN 'cliente nulo'
    END AS motivo_rechazo
FROM silver.paysim_tipada
""")

# 3) Separar rechazados (se guardan, no se borran) y válidos
con.execute("""
CREATE OR REPLACE TABLE silver.rechazados AS
SELECT * FROM silver.paysim_evaluada WHERE motivo_rechazo IS NOT NULL
""")
con.execute("""
CREATE OR REPLACE TABLE silver.paysim_valida AS
SELECT * EXCLUDE (motivo_rechazo),
       row_number() OVER () AS rn
FROM silver.paysim_evaluada WHERE motivo_rechazo IS NULL
""")
con.execute("DROP TABLE silver.paysim_tipada")
con.execute("DROP TABLE silver.paysim_evaluada")

print("Válidas   :", con.execute("SELECT count(*) FROM silver.paysim_valida").fetchone()[0])
print("Rechazadas:", con.execute("SELECT count(*) FROM silver.rechazados").fetchone()[0])
print(con.execute("SELECT motivo_rechazo, count(*) FROM silver.rechazados GROUP BY 1").fetchall())
con.close()