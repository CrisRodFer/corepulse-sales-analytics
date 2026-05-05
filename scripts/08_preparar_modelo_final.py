"""
===============================================================================
SCRIPT: 08_preparar_modelo_final.py
===============================================================================
DESCRIPCIÓN
-----------
Cierra el modelo dimensional final del dashboard a partir de las tablas ya
validadas.

Este script realiza dos tareas:

1. Enriquece Dim_Producto con el precio unitario de referencia, asumiendo que
   dicho precio corresponde al precio de venta al consumidor final.
2. Construye la fact final en formato estrella, incorporando las claves
   foráneas necesarias hacia categoría y proveedor y eliminando los atributos
   temporales redundantes, ya que la navegación temporal se resolverá a través
   de Dim_Calendario.

GRANULARIDAD DE LA FACT FINAL
-----------------------------
1 fila = 1 producto + 1 semana de negocio

CLAVES FINALES EN LA FACT
-------------------------
- product_id
- category_id
- provider_id
- year_week_key

MÉTRICAS FINALES
----------------
- sales_units
- forecast_base_units
- forecast_optimista_units
- forecast_pesimista_units
- unit_sale_price_reference
- estimated_sales_value
- forecast_base_value_estimated
- forecast_optimista_value_estimated
- forecast_pesimista_value_estimated
- (y las métricas ajustadas, si existen)

INPUT ESPERADO
--------------
- data/processed/fact_base_semanal.csv
- data/processed/dim_producto.xlsx
- data/processed/dim_categoria_enriquecida.csv
- data/processed/dim_proveedor_enriquecida.csv

OUTPUT ESPERADO
---------------
- data/processed/fact_ventas_final.csv
- data/processed/dim_producto_final.xlsx
- data/processed/dim_producto_final.csv
- data/processed/resumen_modelo_final.csv

DEPENDENCIAS
------------
- pandas
- openpyxl

INSTALACIÓN RÁPIDA
------------------
pip install pandas openpyxl
===============================================================================
"""

# =============================================================================
# 0. CONFIG
# =============================================================================

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"

FACT_FILE = PROCESSED_DIR / "fact_base_semanal.csv"
DIM_PRODUCT_FILE = PROCESSED_DIR / "dim_producto.xlsx"
DIM_CATEGORY_FILE = PROCESSED_DIR / "dim_categoria_enriquecida.csv"
DIM_PROVIDER_FILE = PROCESSED_DIR / "dim_proveedor_enriquecida.csv"

OUT_FACT_FILE = PROCESSED_DIR / "fact_ventas_final.csv"
OUT_DIM_PRODUCT_XLSX_FILE = PROCESSED_DIR / "dim_producto_final.xlsx"
OUT_DIM_PRODUCT_CSV_FILE = PROCESSED_DIR / "dim_producto_final.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_modelo_final.csv"


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import csv
import logging
import sys

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
        FACT_FILE,
        DIM_PRODUCT_FILE,
        DIM_CATEGORY_FILE,
        DIM_PROVIDER_FILE,
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan archivos de entrada:\n- " + "\n- ".join(missing)
        )


def export_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Exporta DataFrame según extensión."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".csv":
        df.to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
            quoting=csv.QUOTE_ALL,
        )
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    elif path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    else:
        raise ValueError(f"Extensión no soportada: {path.suffix}")


def normalize_text(series: pd.Series) -> pd.Series:
    """Normaliza texto y nulos."""
    s = series.astype("string").str.strip()
    s = s.replace(
        {
            "": pd.NA,
            "nan": pd.NA,
            "NaN": pd.NA,
            "None": pd.NA,
            "<NA>": pd.NA,
        }
    )
    return s


def normalize_product_id(series: pd.Series) -> pd.Series:
    """Normaliza product_id a string homogéneo."""
    numeric = pd.to_numeric(series, errors="coerce")
    out = pd.Series(pd.NA, index=series.index, dtype="string")

    mask_num = numeric.notna()
    if mask_num.any():
        out.loc[mask_num] = numeric.loc[mask_num].astype("Int64").astype("string")

    mask_non_num = ~mask_num
    if mask_non_num.any():
        temp = series.loc[mask_non_num].astype("string").str.strip()
        temp = temp.str.replace(r"\.0$", "", regex=True)
        temp = temp.replace(
            {"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "<NA>": pd.NA}
        )
        out.loc[mask_non_num] = temp

    return out


# =============================================================================
# 3. CARGA DE DATOS
# =============================================================================

def load_fact() -> pd.DataFrame:
    """Carga la fact base semanal."""
    logger.info("Cargando fact base semanal...")
    fact = pd.read_csv(FACT_FILE)

    fact["product_id"] = normalize_product_id(fact["product_id"])
    fact["year_week_key"] = normalize_text(fact["year_week_key"])

    # Normalización de métricas numéricas
    metric_candidates = [
        "sales_units",
        "forecast_base_units",
        "forecast_optimista_units",
        "forecast_pesimista_units",
        "price_unit_reference",
        "sales_value_estimated",
        "forecast_base_value_estimated",
        "forecast_optimista_value_estimated",
        "forecast_pesimista_value_estimated",
        "sales_units_adjusted",
        "forecast_base_units_adjusted",
        "forecast_optimista_units_adjusted",
        "forecast_pesimista_units_adjusted",
        "sales_value_estimated_adjusted",
        "forecast_base_value_estimated_adjusted",
        "forecast_optimista_value_estimated_adjusted",
        "forecast_pesimista_value_estimated_adjusted",
    ]
    for col in metric_candidates:
        if col in fact.columns:
            fact[col] = pd.to_numeric(fact[col], errors="coerce")

    return fact


def load_dim_producto() -> pd.DataFrame:
    """Carga dim_producto desde XLSX."""
    logger.info("Cargando dim_producto...")
    dim = pd.read_excel(DIM_PRODUCT_FILE)

    required_cols = {"product_id", "category_id", "provider_id"}
    missing = required_cols - set(dim.columns)
    if missing:
        raise KeyError(f"Faltan columnas en dim_producto: {missing}")

    dim["product_id"] = normalize_product_id(dim["product_id"])
    dim["category_id"] = normalize_text(dim["category_id"])
    dim["provider_id"] = normalize_text(dim["provider_id"])

    if dim["product_id"].duplicated().any():
        raise ValueError("dim_producto contiene product_id duplicados.")

    return dim


def load_dim_categoria() -> pd.DataFrame:
    """Carga dim_categoria enriquecida."""
    logger.info("Cargando dim_categoria_enriquecida...")
    dim = pd.read_csv(DIM_CATEGORY_FILE)
    dim["category_id"] = normalize_text(dim["category_id"])

    if dim["category_id"].duplicated().any():
        raise ValueError("dim_categoria_enriquecida contiene category_id duplicados.")

    return dim


def load_dim_proveedor() -> pd.DataFrame:
    """Carga dim_proveedor enriquecida."""
    logger.info("Cargando dim_proveedor_enriquecida...")
    dim = pd.read_csv(DIM_PROVIDER_FILE)
    dim["provider_id"] = normalize_text(dim["provider_id"])

    if dim["provider_id"].duplicated().any():
        raise ValueError("dim_proveedor_enriquecida contiene provider_id duplicados.")

    return dim


# =============================================================================
# 4. LÓGICA PRINCIPAL
# =============================================================================

def build_price_map_from_fact(fact: pd.DataFrame) -> pd.DataFrame:
    """
    Construye un mapa de precio unitario por producto a partir de la fact.
    Valida que el precio sea único por product_id.
    """
    logger.info("Construyendo mapa de precios unitarios desde la fact...")

    if "price_unit_reference" not in fact.columns:
        raise KeyError("La fact no contiene 'price_unit_reference'.")

    price_map = (
        fact[["product_id", "price_unit_reference"]]
        .dropna(subset=["product_id"])
        .drop_duplicates()
        .copy()
    )

    conflicts = (
        price_map.groupby("product_id")["price_unit_reference"]
        .nunique(dropna=True)
        .reset_index(name="n_prices")
    )
    conflicts = conflicts[conflicts["n_prices"] > 1]

    if not conflicts.empty:
        raise ValueError(
            "Se han detectado productos con más de un precio unitario de referencia."
        )

    price_map = (
        price_map.groupby("product_id", as_index=False)
        .agg(unit_sale_price_reference=("price_unit_reference", "max"))
    )

    return price_map


def build_dim_producto_final(
    dim_producto: pd.DataFrame,
    price_map: pd.DataFrame,
) -> pd.DataFrame:
    """
    Añade el precio unitario de venta de referencia a Dim_Producto.
    """
    logger.info("Construyendo dim_producto_final...")

    dim_final = dim_producto.merge(
        price_map,
        on="product_id",
        how="left",
        validate="one_to_one",
    )

    return dim_final


def build_fact_final(
    fact: pd.DataFrame,
    dim_producto_final: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la fact final en formato estrella:
    - añade category_id y provider_id
    - conserva solo la week key temporal
    - renombra el precio unitario como precio de venta de referencia
    """
    logger.info("Construyendo fact final...")

    join_cols = ["product_id", "category_id", "provider_id", "unit_sale_price_reference"]

    fact_final = fact.merge(
        dim_producto_final[join_cols],
        on="product_id",
        how="left",
        validate="many_to_one",
    )

    # Validaciones de claves añadidas
    if fact_final["category_id"].isna().any():
        raise ValueError("La fact final contiene nulos en category_id.")
    if fact_final["provider_id"].isna().any():
        raise ValueError("La fact final contiene nulos en provider_id.")

    # Mantener solo la clave temporal final
    temporal_cols_to_drop = [
        "week_key",
        "year_label",
        "week_number_business",
        "week_start_date",
        "week_end_date",
        "week_label",
        "n_days_week",
        "is_partial_week",
    ]
    existing_temporal_drop = [c for c in temporal_cols_to_drop if c in fact_final.columns]
    fact_final = fact_final.drop(columns=existing_temporal_drop)

    # Renombrar precio de referencia si sigue existiendo en la fact antigua
    if "price_unit_reference" in fact_final.columns:
        fact_final = fact_final.drop(columns=["price_unit_reference"])

    # Orden de columnas
    preferred_order = [
        "product_id",
        "category_id",
        "provider_id",
        "year_week_key",
        "unit_sale_price_reference",
        "sales_units",
        "forecast_base_units",
        "forecast_optimista_units",
        "forecast_pesimista_units",
        "sales_value_estimated",
        "forecast_base_value_estimated",
        "forecast_optimista_value_estimated",
        "forecast_pesimista_value_estimated",
        "sales_units_adjusted",
        "forecast_base_units_adjusted",
        "forecast_optimista_units_adjusted",
        "forecast_pesimista_units_adjusted",
        "sales_value_estimated_adjusted",
        "forecast_base_value_estimated_adjusted",
        "forecast_optimista_value_estimated_adjusted",
        "forecast_pesimista_value_estimated_adjusted",
    ]

    existing_cols = [c for c in preferred_order if c in fact_final.columns]
    remaining_cols = [c for c in fact_final.columns if c not in existing_cols]
    fact_final = fact_final[existing_cols + remaining_cols].copy()

    # Validar duplicados de grano
    dup_count = fact_final.duplicated(subset=["product_id", "year_week_key"]).sum()
    if dup_count > 0:
        raise ValueError(
            f"La fact final tiene {dup_count} duplicados para la clave "
            "['product_id', 'year_week_key']."
        )

    return fact_final


def build_summary(
    fact_final: pd.DataFrame,
    dim_producto_final: pd.DataFrame,
    dim_categoria: pd.DataFrame,
    dim_proveedor: pd.DataFrame,
) -> pd.DataFrame:
    """Construye un resumen final de validación."""
    summary = {
        "n_filas_fact_final": int(len(fact_final)),
        "n_productos_fact_final": int(fact_final["product_id"].nunique(dropna=True)),
        "duplicados_fact_product_week": int(
            fact_final.duplicated(subset=["product_id", "year_week_key"]).sum()
        ),
        "nulos_category_id_fact": int(fact_final["category_id"].isna().sum()),
        "nulos_provider_id_fact": int(fact_final["provider_id"].isna().sum()),
        "nulos_year_week_key_fact": int(fact_final["year_week_key"].isna().sum()),
        "n_filas_dim_producto_final": int(len(dim_producto_final)),
        "duplicados_dim_producto_final": int(dim_producto_final["product_id"].duplicated().sum()),
        "nulos_precio_dim_producto_final": int(
            dim_producto_final["unit_sale_price_reference"].isna().sum()
        ),
        "n_filas_dim_categoria": int(len(dim_categoria)),
        "n_filas_dim_proveedor": int(len(dim_proveedor)),
    }

    return pd.DataFrame([summary])


# =============================================================================
# 5. EXPORTACIÓN
# =============================================================================

def export_outputs(
    fact_final: pd.DataFrame,
    dim_producto_final: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    """Exporta outputs finales."""
    logger.info("Exportando modelo final...")

    export_dataframe(fact_final, OUT_FACT_FILE)
    export_dataframe(dim_producto_final, OUT_DIM_PRODUCT_CSV_FILE)
    export_dataframe(dim_producto_final, OUT_DIM_PRODUCT_XLSX_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_FACT_FILE.name)
    logger.info("Archivo exportado: %s", OUT_DIM_PRODUCT_CSV_FILE.name)
    logger.info("Archivo exportado: %s", OUT_DIM_PRODUCT_XLSX_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 6. MAIN
# =============================================================================

def main() -> None:
    """Ejecuta el cierre final del modelo."""
    logger.info("==== INICIO | Preparación del modelo final ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    fact = load_fact()
    dim_producto = load_dim_producto()
    dim_categoria = load_dim_categoria()
    dim_proveedor = load_dim_proveedor()

    price_map = build_price_map_from_fact(fact)
    dim_producto_final = build_dim_producto_final(dim_producto, price_map)
    fact_final = build_fact_final(fact, dim_producto_final)

    summary_df = build_summary(
        fact_final=fact_final,
        dim_producto_final=dim_producto_final,
        dim_categoria=dim_categoria,
        dim_proveedor=dim_proveedor,
    )

    export_outputs(
        fact_final=fact_final,
        dim_producto_final=dim_producto_final,
        summary_df=summary_df,
    )

    logger.info(
        "Modelo final preparado | fact=%s | dim_producto_final=%s",
        len(fact_final),
        len(dim_producto_final),
    )
    logger.info("==== FIN | Preparación del modelo final ====")


if __name__ == "__main__":
    main()