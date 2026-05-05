"""
===============================================================================
SCRIPT: 01_preparar_fuentes_dashboard.py
===============================================================================
DESCRIPCIÓN
-----------
Prepara y alinea las fuentes base del cuadro de mando para el proyecto final de
Cívica, dejando listas las tablas intermedias que servirán para:

1) Seleccionar el subconjunto final de productos del dashboard.
2) Construir la fact table final.
3) Filtrar posteriormente la dimensión de producto.

FLUJO DEL PIPELINE
------------------
1. Cargar el catálogo enriquecido para obtener el universo válido de Product_ID.
2. Cargar el histórico de ventas/demanda ya preparado para ML.
3. Eliminar el año 2022 del histórico.
4. Renombrar el histórico:
      - 2023 -> 2024
      - 2024 -> 2025
5. Cargar las predicciones de 2025 (base, optimista y pesimista).
6. Renombrar la previsión:
      - 2025 -> 2026
7. Excluir los productos presentes en históricos/predicciones pero ausentes del
   catálogo enriquecido.
8. Guardar:
      - histórico preparado 2024-2025
      - forecast preparado 2026 con escenarios en columnas
      - listado de Product_ID válidos
      - listado de Product_ID excluidos
      - resumen de preparación

INPUT ESPERADO (data/raw)
-------------------------
- dataset_ml_ready.parquet
- predicciones_2025_estacional.parquet
- predicciones_2025_optimista.parquet
- predicciones_2025_pesimista.parquet
- catalog_items_enriquecido.csv

OUTPUT ESPERADO (data/interim)
------------------------------
- ventas_2024_2025_preparadas.parquet
- forecast_2026_preparado.parquet
- product_ids_validos_catalogo.csv
- product_ids_excluidos_catalogo.csv
- resumen_preparacion_fuentes.csv

DEPENDENCIAS
------------
- pandas
- pyarrow
- openpyxl
- numpy

INSTALACIÓN RÁPIDA
------------------
pip install pandas pyarrow openpyxl numpy

NOTAS
-----
- Este script NO construye todavía la fact final semanal.
- Este script NO selecciona todavía los productos finales del dashboard.
- La selección de productos se hará en un script posterior.
===============================================================================
"""

# =============================================================================
# 0. CONFIG
# =============================================================================

from pathlib import Path

# -------------------------------------------------------------------------
# IMPORTANTE:
# Se fija explícitamente la raíz del proyecto para evitar que el script tome
# por error la ruta de .venv u otras carpetas de ejecución.
# -------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"

HIST_FILE = RAW_DIR / "dataset_ml_ready.parquet"
FORECAST_BASE_FILE = RAW_DIR / "predicciones_2025_estacional.parquet"
FORECAST_OPT_FILE = RAW_DIR / "predicciones_2025_optimista.parquet"
FORECAST_PES_FILE = RAW_DIR / "predicciones_2025_pesimista.parquet"
CATALOG_ENRICHED_FILE = RAW_DIR / "catalog_items_enriquecido.csv"

OUT_HIST_FILE = INTERIM_DIR / "ventas_2024_2025_preparadas.parquet"
OUT_FORECAST_FILE = INTERIM_DIR / "forecast_2026_preparado.parquet"
OUT_VALID_IDS_FILE = INTERIM_DIR / "product_ids_validos_catalogo.csv"
OUT_EXCLUDED_IDS_FILE = INTERIM_DIR / "product_ids_excluidos_catalogo.csv"
OUT_SUMMARY_FILE = INTERIM_DIR / "resumen_preparacion_fuentes.csv"

HIST_YEARS_TO_KEEP = [2023, 2024]
HIST_YEAR_SHIFT = 1
FORECAST_YEAR_SHIFT = 1

HIST_KEEP_COLS = [
    "product_id",
    "date",
    "cluster_id",
    "sales_quantity",
    "precio_medio",
    "is_outlier",
]

FORECAST_VALUE_COL_BASE = "y_pred_estacional"


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import logging
import sys
from typing import Iterable, Tuple

import pandas as pd

try:
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover
    pq = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# 2. UTILIDADES
# =============================================================================

def ensure_directories() -> None:
    """Crea las carpetas necesarias si no existen."""
    for path in [RAW_DIR, INTERIM_DIR, PROCESSED_DIR, OUTPUTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def check_input_files() -> None:
    """Verifica que existan todos los archivos de entrada requeridos."""
    required_files = [
        HIST_FILE,
        FORECAST_BASE_FILE,
        FORECAST_OPT_FILE,
        FORECAST_PES_FILE,
        CATALOG_ENRICHED_FILE,
    ]

    missing = [str(file_path) for file_path in required_files if not file_path.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan archivos de entrada en data/raw:\n- " + "\n- ".join(missing)
        )


def safe_read_parquet(path: Path) -> pd.DataFrame:
    """
    Lee un parquet de forma robusta.
    """
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        logger.warning(
            "Lectura estándar con pandas falló para %s. Se intentará con pyarrow. "
            "Detalle: %s",
            path.name,
            exc,
        )

        if pq is None:
            raise

        table = pq.read_table(path)
        return table.to_pandas(ignore_metadata=True)


def normalizar_product_id(series: pd.Series) -> pd.Series:
    """
    Normaliza Product_ID / product_id a string homogéneo.
    """
    s = series.copy()

    numeric = pd.to_numeric(s, errors="coerce")
    result = pd.Series(pd.NA, index=s.index, dtype="string")

    mask_num = numeric.notna()
    if mask_num.any():
        result.loc[mask_num] = numeric.loc[mask_num].astype("Int64").astype("string")

    mask_non_num = ~mask_num
    if mask_non_num.any():
        temp = s.loc[mask_non_num].astype("string").str.strip()
        temp = temp.replace(
            {
                "": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "NaN": pd.NA,
                "<NA>": pd.NA,
            }
        )
        temp = temp.str.replace(r"\.0$", "", regex=True)
        result.loc[mask_non_num] = temp

    return result


def shift_years_in_date_column(
    df: pd.DataFrame,
    date_col: str,
    years: int,
) -> pd.DataFrame:
    """Desplaza una fecha un número entero de años."""
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col]) + pd.DateOffset(years=years)
    return out


def filtrar_years(df: pd.DataFrame, date_col: str, years_to_keep: Iterable[int]) -> pd.DataFrame:
    """Filtra un DataFrame por años concretos."""
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out = out[out[date_col].dt.year.isin(years_to_keep)].copy()
    return out


def validar_duplicados(
    df: pd.DataFrame,
    key_cols: list[str],
    dataset_name: str,
) -> None:
    """Valida que no existan duplicados por clave natural."""
    dup_count = df.duplicated(subset=key_cols).sum()
    if dup_count > 0:
        raise ValueError(
            f"Se han detectado {dup_count} duplicados en {dataset_name} "
            f"para la clave {key_cols}."
        )


def export_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Exporta un DataFrame según la extensión del archivo."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    else:
        raise ValueError(f"Extensión no soportada para exportación: {path.suffix}")


def resumen_basico_fuente(
    df: pd.DataFrame,
    dataset_name: str,
    product_col: str,
    date_col: str,
) -> dict:
    """Devuelve un resumen sencillo y útil del dataset."""
    return {
        "dataset": dataset_name,
        "n_filas": int(len(df)),
        "n_productos": int(df[product_col].nunique(dropna=True)),
        "fecha_min": pd.to_datetime(df[date_col]).min(),
        "fecha_max": pd.to_datetime(df[date_col]).max(),
    }


# =============================================================================
# 3. LÓGICA PRINCIPAL
# =============================================================================

def cargar_product_ids_validos_catalogo(path_catalog: Path) -> set[str]:
    """
    Carga el catálogo enriquecido y devuelve el set de Product_ID válidos.
    """
    logger.info("Cargando catálogo enriquecido: %s", path_catalog.name)
    catalog = pd.read_csv(path_catalog)

    if "Product_ID" not in catalog.columns:
        raise KeyError("El catálogo enriquecido no contiene la columna 'Product_ID'.")

    catalog["Product_ID"] = normalizar_product_id(catalog["Product_ID"])
    catalog = catalog.dropna(subset=["Product_ID"]).copy()

    valid_ids = set(catalog["Product_ID"].unique())

    logger.info("Product_ID válidos en catálogo enriquecido: %s", len(valid_ids))
    return valid_ids


def preparar_historico(
    hist_path: Path,
    valid_ids: set[str],
) -> Tuple[pd.DataFrame, set[str]]:
    """
    Prepara el histórico:
    - elimina 2022
    - renombra 2023 -> 2024
    - renombra 2024 -> 2025
    - filtra Product_ID válidos
    - elimina 29/02/2024 para evitar duplicados artificiales al desplazar fechas
    """
    logger.info("Cargando histórico: %s", hist_path.name)
    hist = safe_read_parquet(hist_path)

    required_cols = {"product_id", "date", "sales_quantity", "precio_medio", "cluster_id"}
    missing = required_cols - set(hist.columns)
    if missing:
        raise KeyError(f"Faltan columnas obligatorias en histórico: {missing}")

    hist["product_id"] = normalizar_product_id(hist["product_id"])
    hist["date"] = pd.to_datetime(hist["date"])

    # 1) Mantener solo 2023 y 2024
    hist = filtrar_years(hist, date_col="date", years_to_keep=HIST_YEARS_TO_KEEP)

    # 2) Mantener solo columnas útiles para el dashboard / selección
    keep_cols = [col for col in HIST_KEEP_COLS if col in hist.columns]
    hist = hist[keep_cols].copy()

    # 3) Filtrar solo productos presentes en catálogo enriquecido
    hist_ids_before = set(hist["product_id"].dropna().unique())
    hist = hist[hist["product_id"].isin(valid_ids)].copy()
    hist_ids_after = set(hist["product_id"].dropna().unique())
    excluded_ids = hist_ids_before - hist_ids_after

    # 4) Ajuste por año bisiesto:
    # al desplazar 2024 -> 2025, el 29/02/2024 colisiona con 28/02/2025.
    # Para evitar duplicados artificiales por product_id + date, eliminamos
    # el 29/02/2024 antes del renombrado temporal.
    mask_leap_day = (
        (hist["date"].dt.year == 2024) &
        (hist["date"].dt.month == 2) &
        (hist["date"].dt.day == 29)
    )

    n_leap_rows = int(mask_leap_day.sum())
    if n_leap_rows > 0:
        logger.warning(
            "Se eliminan %s filas correspondientes al 29/02/2024 para evitar "
            "duplicados artificiales al renombrar 2024 -> 2025.",
            n_leap_rows
        )
        hist = hist.loc[~mask_leap_day].copy()

    # 5) Renombrado temporal
    hist = shift_years_in_date_column(hist, date_col="date", years=HIST_YEAR_SHIFT)

    # 6) Limpieza final
    hist = hist.dropna(subset=["product_id", "date"]).copy()
    hist = hist.sort_values(["product_id", "date"]).reset_index(drop=True)

    # 7) Validación final de duplicados
    dup_count = hist.duplicated(subset=["product_id", "date"]).sum()
    if dup_count > 0:
        dup_sample = (
            hist.loc[hist.duplicated(subset=["product_id", "date"], keep=False),
                     ["product_id", "date"]]
            .sort_values(["product_id", "date"])
            .head(10)
        )
        logger.error("Muestra de duplicados detectados en histórico:\n%s", dup_sample)
        raise ValueError(
            f"Se han detectado {dup_count} duplicados en histórico preparado para la clave "
            f"['product_id', 'date']."
        )

    logger.info(
        "Histórico preparado | filas=%s | productos=%s | rango=%s -> %s",
        len(hist),
        hist["product_id"].nunique(),
        hist["date"].min().date(),
        hist["date"].max().date(),
    )

    return hist, excluded_ids


def preparar_forecast_escenario(
    forecast_path: Path,
    valid_ids: set[str],
    output_value_col: str,
) -> Tuple[pd.DataFrame, set[str]]:
    """
    Prepara un escenario de forecast.
    """
    logger.info("Cargando forecast: %s", forecast_path.name)
    fc = safe_read_parquet(forecast_path)

    required_cols = {"product_id", "date", "cluster_id", FORECAST_VALUE_COL_BASE}
    missing = required_cols - set(fc.columns)
    if missing:
        raise KeyError(f"Faltan columnas obligatorias en forecast {forecast_path.name}: {missing}")

    fc["product_id"] = normalizar_product_id(fc["product_id"])
    fc["date"] = pd.to_datetime(fc["date"])

    fc = fc[["product_id", "date", "cluster_id", FORECAST_VALUE_COL_BASE]].copy()
    fc = fc.rename(columns={FORECAST_VALUE_COL_BASE: output_value_col})

    fc_ids_before = set(fc["product_id"].dropna().unique())
    fc = fc[fc["product_id"].isin(valid_ids)].copy()
    fc_ids_after = set(fc["product_id"].dropna().unique())
    excluded_ids = fc_ids_before - fc_ids_after

    fc = shift_years_in_date_column(fc, date_col="date", years=FORECAST_YEAR_SHIFT)

    fc = fc.dropna(subset=["product_id", "date"]).copy()
    fc = fc.sort_values(["product_id", "date"]).reset_index(drop=True)

    validar_duplicados(fc, key_cols=["product_id", "date"], dataset_name=f"forecast {output_value_col}")

    logger.info(
        "Forecast %s preparado | filas=%s | productos=%s | rango=%s -> %s",
        output_value_col,
        len(fc),
        fc["product_id"].nunique(),
        fc["date"].min().date(),
        fc["date"].max().date(),
    )

    return fc, excluded_ids


def construir_forecast_combinado(
    forecast_base: pd.DataFrame,
    forecast_opt: pd.DataFrame,
    forecast_pes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combina los tres escenarios de forecast en una sola tabla.
    """
    logger.info("Combinando escenarios de forecast en una única tabla...")

    forecast = forecast_base.copy()

    forecast_opt_merge = forecast_opt[["product_id", "date", "forecast_optimista"]].copy()
    forecast_pes_merge = forecast_pes[["product_id", "date", "forecast_pesimista"]].copy()

    forecast = forecast.merge(
        forecast_opt_merge,
        on=["product_id", "date"],
        how="left",
        validate="one_to_one",
    )

    forecast = forecast.merge(
        forecast_pes_merge,
        on=["product_id", "date"],
        how="left",
        validate="one_to_one",
    )

    forecast = forecast.sort_values(["product_id", "date"]).reset_index(drop=True)

    validar_duplicados(
        forecast,
        key_cols=["product_id", "date"],
        dataset_name="forecast combinado",
    )

    return forecast


def construir_resumen(
    hist_prepared: pd.DataFrame,
    forecast_prepared: pd.DataFrame,
    valid_ids: set[str],
    excluded_ids_total: set[str],
) -> pd.DataFrame:
    """Construye una tabla resumen de la preparación."""
    summary_rows = [
        {
            **resumen_basico_fuente(
                hist_prepared,
                dataset_name="ventas_2024_2025_preparadas",
                product_col="product_id",
                date_col="date",
            ),
            "universo_catalogo_valido": len(valid_ids),
            "n_productos_excluidos_por_catalogo": len(excluded_ids_total),
        },
        {
            **resumen_basico_fuente(
                forecast_prepared,
                dataset_name="forecast_2026_preparado",
                product_col="product_id",
                date_col="date",
            ),
            "universo_catalogo_valido": len(valid_ids),
            "n_productos_excluidos_por_catalogo": len(excluded_ids_total),
        },
    ]
    return pd.DataFrame(summary_rows)


# =============================================================================
# 4. EXPORTACIÓN / I/O
# =============================================================================

def guardar_outputs(
    hist_prepared: pd.DataFrame,
    forecast_prepared: pd.DataFrame,
    valid_ids: set[str],
    excluded_ids_total: set[str],
) -> None:
    """Guarda todos los outputs del script."""
    logger.info("Exportando outputs intermedios...")

    valid_ids_df = pd.DataFrame({"product_id": sorted(valid_ids)})
    excluded_ids_df = pd.DataFrame({"product_id": sorted(excluded_ids_total)})

    summary_df = construir_resumen(
        hist_prepared=hist_prepared,
        forecast_prepared=forecast_prepared,
        valid_ids=valid_ids,
        excluded_ids_total=excluded_ids_total,
    )

    export_dataframe(hist_prepared, OUT_HIST_FILE)
    export_dataframe(forecast_prepared, OUT_FORECAST_FILE)
    export_dataframe(valid_ids_df, OUT_VALID_IDS_FILE)
    export_dataframe(excluded_ids_df, OUT_EXCLUDED_IDS_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_HIST_FILE.name)
    logger.info("Archivo exportado: %s", OUT_FORECAST_FILE.name)
    logger.info("Archivo exportado: %s", OUT_VALID_IDS_FILE.name)
    logger.info("Archivo exportado: %s", OUT_EXCLUDED_IDS_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 5. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta el flujo completo de preparación de fuentes."""
    logger.info("==== INICIO | Preparación de fuentes para dashboard ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    valid_ids = cargar_product_ids_validos_catalogo(CATALOG_ENRICHED_FILE)

    hist_prepared, excluded_hist = preparar_historico(
        hist_path=HIST_FILE,
        valid_ids=valid_ids,
    )

    forecast_base, excluded_base = preparar_forecast_escenario(
        forecast_path=FORECAST_BASE_FILE,
        valid_ids=valid_ids,
        output_value_col="forecast_base",
    )

    forecast_opt, excluded_opt = preparar_forecast_escenario(
        forecast_path=FORECAST_OPT_FILE,
        valid_ids=valid_ids,
        output_value_col="forecast_optimista",
    )

    forecast_pes, excluded_pes = preparar_forecast_escenario(
        forecast_path=FORECAST_PES_FILE,
        valid_ids=valid_ids,
        output_value_col="forecast_pesimista",
    )

    forecast_prepared = construir_forecast_combinado(
        forecast_base=forecast_base,
        forecast_opt=forecast_opt,
        forecast_pes=forecast_pes,
    )

    excluded_ids_total = set().union(excluded_hist, excluded_base, excluded_opt, excluded_pes)

    logger.info(
        "Product_ID excluidos por no existir en catálogo enriquecido: %s",
        len(excluded_ids_total),
    )

    guardar_outputs(
        hist_prepared=hist_prepared,
        forecast_prepared=forecast_prepared,
        valid_ids=valid_ids,
        excluded_ids_total=excluded_ids_total,
    )

    logger.info("==== FIN | Preparación de fuentes completada ====")


if __name__ == "__main__":
    main()