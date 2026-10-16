# Data Warehouse de Transacciones Financieras

Proyecto de Data Warehouse con **arquitectura medallón** (bronce, plata y oro) construido en **DuckDB** y **Python**, sobre el dataset PaySim (Kaggle: `ealaxi/paysim1`). El warehouse contiene **10 millones de transacciones** del periodo enero 2024 a junio 2025 y está modelado como un **esquema estrella** para responder 13 requerimientos analíticos sobre canales, horarios y calidad transaccional.

## Objetivo

Analizar el comportamiento transaccional de una plataforma financiera: montos, ticket promedio, picos de actividad, tasas de éxito y de transacciones negativas por canal, franja horaria y tipo de día.

## Tecnologías

- Python 3.10+
- DuckDB (almacenamiento y transformación en SQL)
- pandas, numpy, holidays, pyarrow
- Tableau (visualización)
- Git y GitHub

## Arquitectura medallón

| Capa | Esquema | Contenido |
|---|---|---|
| Bronce | `bronze` | Datos crudos del CSV, todo como texto, con metadatos de carga (`_source_file`, `_ingest_ts`, `_batch_id`). |
| Plata | `silver` | Datos tipados, estandarizados y validados. Los registros inválidos se guardan en `silver.rechazados`. Incluye las transacciones enriquecidas (fecha-hora, canal, estado, franja horaria, festivos) y las dimensiones. |
| Oro | `gold` | Modelo estrella listo para análisis: `dim_tiempo`, `dim_canal` y `hecho_transaccion`. |

### Resultados de la carga

| Etapa | Filas |
|---|---|
| Bronce (`bronze.paysim_raw`) | 6.362.620 |
| Plata, rechazadas por calidad | 16 |
| Plata (`silver.transacciones`) | 10.000.000 |
| Oro, `dim_tiempo` | 13.128 (547 días × 24 horas) |
| Oro, `dim_canal` | 6 |
| Oro, `hecho_transaccion` | 72.813 |

## Modelo estrella

**Granularidad del hecho:** una fila por hora y por canal.

**`hecho_transaccion`**
- `sk_tiempo`, `sk_canal` (llaves foráneas)
- `monto_total`, `monto_promedio`, `monto_negativo`, `monto_positivo`
- `cantidad_transacciones_positivas`, `cantidad_transacciones_negativas`, `total_transacciones`

**`dim_tiempo`**
- `sk_tiempo`, `fecha`, `anio`, `hora`, `trimestre`, `mes`, `nombre_mes`, `dia`, `dia_semana`, `nombre_dia`
- `es_fin_semana`, `es_festivo`
- `tipo_dia` (Hábil / Fin de semana / Festivo; el festivo tiene prioridad)
- `franja_horaria` (Madrugada, Mañana, Tarde, Noche)

**`dim_canal`**
- `sk_canal`, `nombre` (App, Cajero, Corresp, POS, Sucursal, Web), `es_digital`

## Requerimientos analíticos

| # | Análisis |
|---|---|
| 1 | Evolución del monto total transaccionado por canal (mes y año) |
| 2 | Ticket promedio por franja horaria y canal |
| 3 | Picos de movimiento económico por franja horaria |
| 4 | Tasa de transacciones negativas por canal |
| 5 | Transacciones negativas en horario nocturno y de madrugada |
| 6 | Montos asociados a operaciones negativas vs. comportamiento habitual |
| 7 | Clasificación de canales según su tasa de éxito |
| 8 | Días hábiles, fines de semana y festivos |
| 9 | Distribución horaria del volumen transaccional |
| 10 | Tendencia mensual del volumen de operaciones por canal |
| 11 | Participación de cada canal en el monto total |
| 12 | Promedio diario de transacciones negativas por canal |
| 13 | Estabilidad transaccional entre Web y App por franja horaria |

Los resultados se generan como CSV en `data/resultados/` (uno por requerimiento).

## Estructura del proyecto
proyecto_dw/
├── data/
│ ├── raw/ # CSV de Kaggle (no se versiona)
│ ├── resultados/ # CSV de los 13 requerimientos
│ └── warehouse.duckdb # Base de datos (no se versiona)
├── src/
│ ├── config.py
│ ├── 01_bronce.py
│ ├── 02_plata_limpieza.py
│ ├── 03_plata_enriquecimiento.py
│ ├── 04_validaciones.py
│ ├── 05_oro.py
│ ├── 06_requerimientos.py
│ └── 07_exportar_oro.py # exporta oro a CSV para Tableau
├── requirements.txt
└── README.md


## Cómo reproducirlo

1. Clonar el repositorio y entrar a la carpeta del proyecto.
2. Crear y activar el entorno virtual:
```bash
   python -m venv .venv
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # Mac/Linux
   source .venv/bin/activate
```
3. Instalar dependencias:
```bash
   pip install -r requirements.txt
```
4. Descargar el dataset desde Kaggle (*Synthetic Financial Datasets For Fraud Detection*) y copiar el CSV a `data/raw/`. Verificar que el nombre coincida con el definido en `src/config.py`.
5. Ejecutar los scripts en orden:
```bash
   python src/01_bronce.py
   python src/02_plata_limpieza.py
   python src/03_plata_enriquecimiento.py
   python src/04_validaciones.py
   python src/05_oro.py
   python src/06_requerimientos.py
```

## Validaciones incluidas

- Conteo de filas entre origen, bronce y plata, sin pérdida de registros.
- Nulos críticos y llaves duplicadas.
- Cuadre de totales entre plata y oro (transacciones y montos).
- Integridad referencial del hecho con sus dimensiones (0 llaves huérfanas).

## Fuente de datos

Dataset PaySim, Kaggle: `ealaxi/paysim1`. Simulador: https://github.com/EdgarLopezPhD/PaySim

Los resultados se generan como CSV en `data/resultados/` (uno por requerimiento).

## Estructura del proyecto
