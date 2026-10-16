import duckdb
from config import DB, RAIZ

SALIDA = RAIZ / "data" / "oro_csv"
SALIDA.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB), read_only=True)
for tabla in ("dim_tiempo", "dim_canal", "hecho_transaccion"):
    ruta = (SALIDA / f"{tabla}.csv").as_posix()
    con.execute(f"COPY gold.{tabla} TO '{ruta}' (HEADER, DELIMITER ',')")
    print("Exportada:", tabla)
con.close()