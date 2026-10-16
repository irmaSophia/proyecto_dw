import duckdb
from config import CSV, DB

con = duckdb.connect(str(DB))
for esquema in ("bronze", "silver", "gold"):
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {esquema}")

con.execute("DROP TABLE IF EXISTS bronze.paysim_raw")
con.execute(f"""
    CREATE TABLE bronze.paysim_raw AS
    SELECT
        row_number() OVER () AS _nro_fila,
        * EXCLUDE (filename),
        filename             AS _source_file,
        now()                AS _ingest_ts,
        'batch_001'          AS _batch_id
    FROM read_csv('{CSV.as_posix()}',
                  header = true,
                  all_varchar = true,   -- todo como texto: no se limpia nada
                  filename = true)
""")

n = con.execute("SELECT count(*) FROM bronze.paysim_raw").fetchone()[0]
print(f"Filas en bronce: {n:,}")
assert n == 6_362_620, "El conteo no coincide con el esperado de PaySim"
print("Bronce OK")
con.close()