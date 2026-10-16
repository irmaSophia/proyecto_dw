# Data Warehouse de transacciones financieras

Proyecto de DW con arquitectura medallón (bronce, plata, oro) en DuckDB,
basado en el dataset PaySim (Kaggle: ealaxi/paysim1), ampliado a 10 M de registros.

## Cómo reproducirlo
1. `python -m venv .venv` y activar el entorno
2. `pip install -r requirements.txt`
3. Descargar el CSV de Kaggle a `data/raw/`
4. Ejecutar en orden: `src/01_bronce.py` → `02_plata_limpieza.py` →
   `03_plata_enriquecimiento.py` → `04_validaciones.py` →
   `05_oro.py` → `06_requerimientos.py`

## Decisiones de diseño
- Los registros adicionales (3,64 M) se generan por remuestreo con
  perturbación del monto y se marcan con `origen_registro = 'sintetico'`.
- El canal, el estado (negativa) y la fecha se generan sintéticamente,
  porque PaySim no los incluye.
- La baja actividad en madrugada (0,7 % del volumen) es característica del
  dataset original y no se alteró.
- `saldo_insuficiente` se descartó de `es_negativa` por estar presente en el
  56,6 % de las filas.
- Cambios al modelo estrella: `tipo_dia` en `dim_tiempo` (atributo derivado
  para el req. 8), y `monto_negativo` y `monto_positivo` en `hecho_transaccion`.
