"""
===============================================================================
SCRIPT: 03_construir_fact_base_semanal.py
===============================================================================
DESCRIPCIÓN
-----------
Construye la fact base semanal del dashboard a partir del subconjunto final de
productos seleccionado.

Granularidad:
    1 fila = 1 producto + 1 semana de negocio

La tabla resultante incluye:
- claves de dimensión (producto + semana)
- métricas reales de ventas y forecast
- precio de referencia
- métricas derivadas de valor estimado
- métricas ajustadas para semanas parciales, pensadas para comparativas visuales

IMPORTANTE
----------
Para evitar que una misma semana mezcle datos de años distintos, las semanas se
recortan en los límites anuales:
- la primera semana del año puede ser parcial
- la última semana del año puede ser parcial

Además:
- se conserva la métrica real semanal
- y se crea una métrica ajustada únicamente para comparaciones visuales entre
  semanas parciales y completas

INPUT ESPERADO
--------------
- data/interim/ventas_2024_2025_preparadas.parquet
- data/interim/forecast_2026_preparado.parquet
- data/processed/productos_seleccionados_dashboard.csv
- data/processed/metricas_producto_dashboard.csv

OUTPUT ESPERADO
---------------
- data/processed/fact_base_semanal.csv
- data/processed/resumen_fact_base_semanal.csv

DEPENDENCIAS
------------
- pandas
- numpy
- pyarrow

INSTALACIÓN RÁPIDA
------------------
pip install pandas numpy pyarrow
===============================================================================
"""

# =============================================================================
# 0. CONFIG
# =============================================================================

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT_DIR / "data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"

SALES_FILE = INTERIM_DIR / "ventas_2024_2025_preparadas.parquet"
FORECAST_FILE = INTERIM_DIR / "forecast_2026_preparado.parquet"
SELECTED_PRODUCTS_FILE = PROCESSED_DIR / "productos_seleccionados_dashboard.csv"
PRODUCT_METRICS_FILE = PROCESSED_DIR / "metricas_producto_dashboard.csv"

OUT_FACT_FILE = PROCESSED_DIR / "fact_base_semanal.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_fact_base_semanal.csv"

EPSILON = 1e-9


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import logging
import sys

import numpy as np
import pandas as pd

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
    """Crea carpetas de salida si no existen."""
    for path in [PROCESSED_DIR, OUTPUTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def check_input_files() -> None:
    """Valida que existan los archivos de entrada."""
    required_files = [
        SALES_FILE,
        FORECAST_FILE,
        SELECTED_PRODUCTS_FILE,
        PRODUCT_METRICS_FILE,
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan archivos de entrada:\n- " + "\n- ".join(missing)
        )


def normalizar_product_id(series: pd.Series) -> pd.Series:
    """Normaliza el identificador de producto a string homogéneo."""
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


def export_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Exporta un DataFrame según la extensión."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    else:
        raise ValueError(f"Extensión no soportada: {path.suffix}")


def get_week_start_monday(date_series: pd.Series) -> pd.Series:
    """Devuelve el lunes de la semana natural."""
    date_series = pd.to_datetime(date_series)
    return date_series - pd.to_timedelta(date_series.dt.weekday, unit="D")


def get_week_end_sunday(date_series: pd.Series) -> pd.Series:
    """Devuelve el domingo de la semana natural."""
    return get_week_start_monday(date_series) + pd.Timedelta(days=6)


def build_business_week_fields(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """
    Construye campos de semana de negocio recortados al año natural.
    """
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])

    natural_week_start = get_week_start_monday(out[date_col])
    natural_week_end = get_week_end_sunday(out[date_col])

    year_label = out[date_col].dt.year
    year_start = pd.to_datetime(year_label.astype(str) + "-01-01")
    year_end = pd.to_datetime(year_label.astype(str) + "-12-31")

    business_week_start = natural_week_start.where(natural_week_start >= year_start, year_start)
    business_week_end = natural_week_end.where(natural_week_end <= year_end, year_end)

    out["year_label"] = year_label
    out["week_start_date"] = business_week_start
    out["week_end_date"] = business_week_end

    return out


def add_business_week_number(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade número de semana de negocio dentro de cada año.
    """
    out = df.copy()

    week_index = (
        out[["year_label", "week_start_date"]]
        .drop_duplicates()
        .sort_values(["year_label", "week_start_date"])
        .copy()
    )

    week_index["week_number_business"] = (
        week_index.groupby("year_label").cumcount() + 1
    )

    out = out.merge(
        week_index,
        on=["year_label", "week_start_date"],
        how="left",
        validate="many_to_one",
    )

    out["year_week_key"] = (
        out["year_label"].astype(int).astype(str)
        + "_W"
        + out["week_number_business"].astype(int).astype(str).str.zfill(2)
    )

    out["week_label"] = (
        out["week_start_date"].dt.strftime("%d/%m/%Y")
        + " - "
        + out["week_end_date"].dt.strftime("%d/%m/%Y")
    )

    return out


def add_partial_week_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade:
    - n_days_week
    - is_partial_week

    La semana parcial se define como una semana con menos de 7 días.
    """
    out = df.copy()
    out["n_days_week"] = (
        (pd.to_datetime(out["week_end_date"]) - pd.to_datetime(out["week_start_date"])).dt.days + 1
    )
    out["is_partial_week"] = out["n_days_week"] < 7
    return out


def add_adjusted_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Crea métricas ajustadas para comparar semanas parciales con semanas completas.

    Regla:
    - si la semana tiene 7 días, el valor ajustado coincide con el real
    - si la semana tiene menos de 7 días, se reescala a equivalente semanal
    """
    out = df.copy()

    out["sales_units_adjusted"] = out["sales_units"] * 7 / out["n_days_week"]
    out["forecast_base_units_adjusted"] = out["forecast_base_units"] * 7 / out["n_days_week"]
    out["forecast_optimista_units_adjusted"] = out["forecast_optimista_units"] * 7 / out["n_days_week"]
    out["forecast_pesimista_units_adjusted"] = out["forecast_pesimista_units"] * 7 / out["n_days_week"]

    out["sales_value_estimated_adjusted"] = (
        out["sales_units_adjusted"] * out["price_unit_reference"]
    )
    out["forecast_base_value_estimated_adjusted"] = (
        out["forecast_base_units_adjusted"] * out["price_unit_reference"]
    )
    out["forecast_optimista_value_estimated_adjusted"] = (
        out["forecast_optimista_units_adjusted"] * out["price_unit_reference"]
    )
    out["forecast_pesimista_value_estimated_adjusted"] = (
        out["forecast_pesimista_units_adjusted"] * out["price_unit_reference"]
    )

    return out


# =============================================================================
# 3. CARGA DE DATOS
# =============================================================================

def load_selected_products() -> pd.DataFrame:
    """Carga el subconjunto final de productos seleccionados."""
    logger.info("Cargando productos seleccionados...")
    df = pd.read_csv(SELECTED_PRODUCTS_FILE)

    if "product_id" not in df.columns:
        raise KeyError("El archivo de productos seleccionados no contiene 'product_id'.")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df = df.dropna(subset=["product_id"]).drop_duplicates(subset=["product_id"]).copy()

    return df


def load_product_metrics() -> pd.DataFrame:
    """
    Carga las métricas por producto para recuperar el precio de referencia final.
    """
    logger.info("Cargando métricas de producto...")
    df = pd.read_csv(PRODUCT_METRICS_FILE)

    required_cols = {"product_id", "avg_price_final"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas en métricas de producto: {missing}")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df["avg_price_final"] = pd.to_numeric(df["avg_price_final"], errors="coerce")

    df = df[["product_id", "avg_price_final"]].drop_duplicates(subset=["product_id"]).copy()
    return df


def load_sales() -> pd.DataFrame:
    """Carga ventas preparadas 2024-2025."""
    logger.info("Cargando ventas preparadas...")
    df = pd.read_parquet(SALES_FILE)

    required_cols = {"product_id", "date", "sales_quantity"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas en ventas: {missing}")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df["date"] = pd.to_datetime(df["date"])
    df["sales_quantity"] = pd.to_numeric(df["sales_quantity"], errors="coerce").fillna(0)

    return df


def load_forecast() -> pd.DataFrame:
    """Carga forecast preparado 2026."""
    logger.info("Cargando forecast preparado...")
    df = pd.read_parquet(FORECAST_FILE)

    required_cols = {
        "product_id",
        "date",
        "forecast_base",
        "forecast_optimista",
        "forecast_pesimista",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas en forecast: {missing}")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df["date"] = pd.to_datetime(df["date"])

    for col in ["forecast_base", "forecast_optimista", "forecast_pesimista"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


# =============================================================================
# 4. LÓGICA PRINCIPAL
# =============================================================================

def build_sales_weekly(sales: pd.DataFrame, selected_ids: set[str]) -> pd.DataFrame:
    """
    Agrega las ventas reales a nivel semanal de negocio.
    """
    logger.info("Agregando ventas reales a semana de negocio...")

    df = sales.loc[sales["product_id"].isin(selected_ids)].copy()
    df = build_business_week_fields(df, date_col="date")

    weekly = (
        df.groupby(
            ["product_id", "year_label", "week_start_date", "week_end_date"],
            as_index=False,
        )
        .agg(
            sales_units=("sales_quantity", "sum"),
        )
    )

    weekly = add_business_week_number(weekly)
    weekly = add_partial_week_fields(weekly)
    return weekly


def build_forecast_weekly(forecast: pd.DataFrame, selected_ids: set[str]) -> pd.DataFrame:
    """
    Agrega el forecast 2026 a nivel semanal de negocio.
    """
    logger.info("Agregando forecast a semana de negocio...")

    df = forecast.loc[forecast["product_id"].isin(selected_ids)].copy()
    df = build_business_week_fields(df, date_col="date")

    weekly = (
        df.groupby(
            ["product_id", "year_label", "week_start_date", "week_end_date"],
            as_index=False,
        )
        .agg(
            forecast_base_units=("forecast_base", "sum"),
            forecast_optimista_units=("forecast_optimista", "sum"),
            forecast_pesimista_units=("forecast_pesimista", "sum"),
        )
    )

    weekly = add_business_week_number(weekly)
    weekly = add_partial_week_fields(weekly)
    return weekly


def build_fact_base(
    sales_weekly: pd.DataFrame,
    forecast_weekly: pd.DataFrame,
    product_metrics: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la fact base semanal uniendo ventas, forecast y precio de referencia.
    """
    logger.info("Construyendo fact base semanal...")

    merge_keys = [
        "product_id",
        "year_label",
        "week_start_date",
        "week_end_date",
        "week_number_business",
        "year_week_key",
        "week_label",
        "n_days_week",
        "is_partial_week",
    ]

    fact = sales_weekly.merge(
        forecast_weekly,
        on=merge_keys,
        how="outer",
        validate="one_to_one",
    )

    metric_cols = [
        "sales_units",
        "forecast_base_units",
        "forecast_optimista_units",
        "forecast_pesimista_units",
    ]
    for col in metric_cols:
        if col not in fact.columns:
            fact[col] = 0
        fact[col] = pd.to_numeric(fact[col], errors="coerce").fillna(0)

    fact = fact.merge(
        product_metrics,
        on="product_id",
        how="left",
        validate="many_to_one",
    )

    fact = fact.rename(columns={"avg_price_final": "price_unit_reference"})
    fact["price_unit_reference"] = pd.to_numeric(
        fact["price_unit_reference"], errors="coerce"
    ).fillna(0)

    # Métricas brutas
    fact["sales_value_estimated"] = fact["sales_units"] * fact["price_unit_reference"]
    fact["forecast_base_value_estimated"] = (
        fact["forecast_base_units"] * fact["price_unit_reference"]
    )
    fact["forecast_optimista_value_estimated"] = (
        fact["forecast_optimista_units"] * fact["price_unit_reference"]
    )
    fact["forecast_pesimista_value_estimated"] = (
        fact["forecast_pesimista_units"] * fact["price_unit_reference"]
    )

    # Métricas ajustadas para semanas parciales
    fact = add_adjusted_metrics(fact)

    fact["week_start_date"] = pd.to_datetime(fact["week_start_date"])
    fact["week_end_date"] = pd.to_datetime(fact["week_end_date"])

    fact["week_key"] = (
        fact["year_label"].astype(int).astype(str)
        + fact["week_number_business"].astype(int).astype(str).str.zfill(2)
    )

    fact = fact.sort_values(["product_id", "year_label", "week_start_date"]).reset_index(drop=True)

    dup_count = fact.duplicated(
        subset=["product_id", "year_label", "week_start_date"]
    ).sum()
    if dup_count > 0:
        raise ValueError(
            f"Se han detectado {dup_count} duplicados en la fact para la clave "
            f"['product_id', 'year_label', 'week_start_date']."
        )

    return fact


def build_summary(fact: pd.DataFrame) -> pd.DataFrame:
    """Construye un resumen simple de validación de la fact base."""
    cross_year_issue = int((fact["week_start_date"].dt.year != fact["year_label"]).sum())
    partial_weeks = int(fact["is_partial_week"].sum())

    summary = {
        "n_filas_fact": int(len(fact)),
        "n_productos_fact": int(fact["product_id"].nunique(dropna=True)),
        "fecha_min_fact": fact["week_start_date"].min(),
        "fecha_max_fact": fact["week_end_date"].max(),
        "sales_units_total": float(fact["sales_units"].sum()),
        "forecast_base_units_total": float(fact["forecast_base_units"].sum()),
        "forecast_optimista_units_total": float(fact["forecast_optimista_units"].sum()),
        "forecast_pesimista_units_total": float(fact["forecast_pesimista_units"].sum()),
        "sales_value_estimated_total": float(fact["sales_value_estimated"].sum()),
        "forecast_base_value_estimated_total": float(fact["forecast_base_value_estimated"].sum()),
        "n_semanas_unicas": int(fact[["year_label", "week_start_date"]].drop_duplicates().shape[0]),
        "filas_con_year_label_distinto_de_week_start_year": cross_year_issue,
        "filas_semanas_parciales": partial_weeks,
    }

    return pd.DataFrame([summary])


# =============================================================================
# 5. EXPORTACIÓN / I/O
# =============================================================================

def export_outputs(fact: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    """Exporta la fact base y su resumen."""
    logger.info("Exportando fact base semanal...")

    export_dataframe(fact, OUT_FACT_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_FACT_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 6. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta el flujo completo de construcción de la fact base semanal."""
    logger.info("==== INICIO | Construcción de fact base semanal ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    selected_products = load_selected_products()
    product_metrics = load_product_metrics()
    sales = load_sales()
    forecast = load_forecast()

    selected_ids = set(selected_products["product_id"].dropna().unique())

    sales_weekly = build_sales_weekly(sales, selected_ids)
    forecast_weekly = build_forecast_weekly(forecast, selected_ids)

    fact = build_fact_base(
        sales_weekly=sales_weekly,
        forecast_weekly=forecast_weekly,
        product_metrics=product_metrics,
    )

    summary_df = build_summary(fact)
    export_outputs(fact, summary_df)

    logger.info(
        "Fact base construida | filas=%s | productos=%s | semanas=%s | semanas parciales=%s",
        len(fact),
        fact["product_id"].nunique(),
        fact[["year_label", "week_start_date"]].drop_duplicates().shape[0],
        int(fact["is_partial_week"].sum()),
    )

    logger.info("==== FIN | Construcción de fact base semanal ====")


if __name__ == "__main__":
    main()