from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "data" / "raw" / "PS_20174392719_1491204439457_log.csv"
DB = RAIZ / "data" / "warehouse.duckdb"

OBJETIVO_FILAS = 10_000_000
SEMILLA = 0.42              # para setseed de DuckDB (entre -1 y 1)
FECHA_INICIO = "2024-01-01"
N_DIAS = 547                # 2024-01-01 → 2025-06-30
PAIS_FESTIVOS = "CO"        # cámbialo si tu país es otro