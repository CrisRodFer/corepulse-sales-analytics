"""
===============================================================================
SCRIPT: 02_seleccionar_productos_dashboard.py
===============================================================================
DESCRIPCIÓN
-----------
Selecciona el subconjunto final de productos que se utilizará en el dashboard.

Esta versión aplica una estrategia de selección controlada para evitar:
- dispersión excesiva por categoría,
- sobrerrepresentación del clúster dominante,
- y falta de productos que apoyen la narrativa de inversión / mantenimiento /
  revisión del catálogo.

La selección combina:
1. Núcleo fuerte por valor 2025.
2. Productos con crecimiento YoY.
3. Productos con oportunidad forecast 2026.
4. Productos estables.
5. Productos estacionales / irregulares.
6. Productos a revisar.
7. Cobertura controlada de categorías top y proveedores top.
8. Cuotas mínimas y máximas por clúster.

Además, separa:
- motivo_principal: criterio por el que el producto entra por primera vez.
- criterios_cumplidos: conjunto de reglas que el producto satisface.

FLUJO DEL PIPELINE
------------------
1. Cargar ventas preparadas 2024-2025.
2. Cargar forecast preparado 2026.
3. Cargar catálogo enriquecido.
4. Construir métricas agregadas por producto.
5. Calcular cuotas objetivo por clúster.
6. Seleccionar productos por bloques con control de cuotas.
7. Completar hasta el tamaño objetivo.
8. Exportar productos seleccionados, métricas y trazabilidad.

INPUT ESPERADO
--------------
- data/interim/ventas_2024_2025_preparadas.parquet
- data/interim/forecast_2026_preparado.parquet
- data/raw/catalog_items_enriquecido.csv

OUTPUT ESPERADO
---------------
- data/processed/productos_seleccionados_dashboard.csv
- data/processed/metricas_producto_dashboard.csv
- data/processed/trazabilidad_seleccion_productos.csv
- data/processed/resumen_seleccion_productos.csv

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
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"

SALES_FILE = INTERIM_DIR / "ventas_2024_2025_preparadas.parquet"
FORECAST_FILE = INTERIM_DIR / "forecast_2026_preparado.parquet"
CATALOG_FILE = RAW_DIR / "catalog_items_enriquecido.csv"

OUT_SELECTED_FILE = PROCESSED_DIR / "productos_seleccionados_dashboard.csv"
OUT_METRICS_FILE = PROCESSED_DIR / "metricas_producto_dashboard.csv"
OUT_TRACE_FILE = PROCESSED_DIR / "trazabilidad_seleccion_productos.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_seleccion_productos.csv"

# -------------------------------------------------------------------------
# PARÁMETROS DE SELECCIÓN
# -------------------------------------------------------------------------
TARGET_N_PRODUCTS = 60

CORE_PRODUCTS = 16
GROWTH_PRODUCTS = 8
FORECAST_PRODUCTS = 8
STABLE_PRODUCTS = 6
SEASONAL_PRODUCTS = 6
REVIEW_PRODUCTS = 6

TOP_CATEGORIES_ELIGIBLE = 15
TOP_CATEGORIES_COVERAGE = 12
TOP_PROVIDERS_COVERAGE = 6

MIN_PRODUCTS_PER_CLUSTER = 6
MAX_CLUSTER_SHARE = 0.50  # ningún clúster puede superar el 50% del total final

MIN_ACTIVE_WEEKS_STABLE = 40
MIN_ACTIVE_WEEKS_SEASONAL = 10

# Tope suave para la categoría dominante
DOMINANT_CATEGORY_CAP = 15

EPSILON = 1e-9


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import logging
import math
import sys
from typing import Dict, Optional, Set

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
    required_files = [SALES_FILE, FORECAST_FILE, CATALOG_FILE]
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


def safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    """División segura evitando divisiones por cero."""
    den_adj = den.replace(0, np.nan)
    return num / den_adj


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


def mode_non_null(series: pd.Series):
    """Devuelve la moda no nula de una serie, si existe."""
    s = series.dropna()
    if len(s) == 0:
        return np.nan
    mode_values = s.mode()
    if len(mode_values) == 0:
        return np.nan
    return mode_values.iloc[0]


# =============================================================================
# 3. CARGA Y PREPARACIÓN DE DATOS
# =============================================================================

def load_sales() -> pd.DataFrame:
    """Carga ventas preparadas 2024-2025."""
    logger.info("Cargando ventas preparadas...")
    df = pd.read_parquet(SALES_FILE)

    required_cols = {"product_id", "date", "sales_quantity", "precio_medio", "cluster_id"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas obligatorias en ventas: {missing}")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year

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
        raise KeyError(f"Faltan columnas obligatorias en forecast: {missing}")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year

    return df


def load_catalog() -> pd.DataFrame:
    """Carga catálogo enriquecido y renombra columnas relevantes."""
    logger.info("Cargando catálogo enriquecido...")
    df = pd.read_csv(CATALOG_FILE)

    rename_map = {
        "Product_ID": "product_id",
        "EAN13": "ean13",
        "Marca": "marca",
        "Proveedor": "proveedor",
        "Nombre": "nombre",
        "Categoria": "categoria",
        "Cluster": "cluster_catalogo",
        "precio_medio": "precio_medio_catalogo",
        "is_outlier": "is_outlier_catalogo",
    }

    available_rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=available_rename_map)

    if "product_id" not in df.columns:
        raise KeyError("El catálogo no contiene la columna Product_ID/product_id.")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df = df.dropna(subset=["product_id"]).copy()
    df = df.drop_duplicates(subset=["product_id"]).copy()

    return df


# =============================================================================
# 4. MÉTRICAS POR PRODUCTO
# =============================================================================

def build_product_metrics(
    sales: pd.DataFrame,
    forecast: pd.DataFrame,
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    """Construye métricas agregadas por producto para la selección."""
    logger.info("Construyendo métricas agregadas por producto...")

    # ---------------------------------------------------------------------
    # 4.1. MÉTRICAS ANUALES DE VENTAS
    # ---------------------------------------------------------------------
    sales_yearly = (
        sales.groupby(["product_id", "year"], as_index=False)
        .agg(
            sales_units=("sales_quantity", "sum"),
            avg_price=("precio_medio", "mean"),
            cluster_mode=("cluster_id", mode_non_null),
        )
    )

    sales_pivot = (
        sales_yearly.pivot(index="product_id", columns="year", values="sales_units")
        .rename(columns={2024: "sales_units_2024", 2025: "sales_units_2025"})
        .reset_index()
    )

    price_2025 = (
        sales_yearly.loc[sales_yearly["year"] == 2025, ["product_id", "avg_price"]]
        .rename(columns={"avg_price": "avg_price_2025"})
    )

    cluster_sales = (
        sales_yearly.groupby("product_id", as_index=False)
        .agg(cluster_sales=("cluster_mode", mode_non_null))
    )

    product_metrics = sales_pivot.merge(price_2025, on="product_id", how="left")
    product_metrics = product_metrics.merge(cluster_sales, on="product_id", how="left")

    product_metrics["sales_units_2024"] = product_metrics["sales_units_2024"].fillna(0)
    product_metrics["sales_units_2025"] = product_metrics["sales_units_2025"].fillna(0)

    product_metrics["sales_value_2024_est"] = (
        product_metrics["sales_units_2024"] * product_metrics["avg_price_2025"]
    )
    product_metrics["sales_value_2025_est"] = (
        product_metrics["sales_units_2025"] * product_metrics["avg_price_2025"]
    )

    product_metrics["yoy_units_abs"] = (
        product_metrics["sales_units_2025"] - product_metrics["sales_units_2024"]
    )
    product_metrics["yoy_units_pct"] = safe_divide(
        product_metrics["yoy_units_abs"],
        product_metrics["sales_units_2024"],
    )

    product_metrics["yoy_value_abs_est"] = (
        product_metrics["sales_value_2025_est"] - product_metrics["sales_value_2024_est"]
    )
    product_metrics["yoy_value_pct_est"] = safe_divide(
        product_metrics["yoy_value_abs_est"],
        product_metrics["sales_value_2024_est"],
    )

    # ---------------------------------------------------------------------
    # 4.2. MÉTRICAS SEMANALES 2025: ESTABILIDAD / IRREGULARIDAD
    # ---------------------------------------------------------------------
    sales_2025 = sales.loc[sales["year"] == 2025].copy()
    sales_2025["week_start"] = sales_2025["date"].dt.to_period("W-MON").dt.start_time

    weekly_2025 = (
        sales_2025.groupby(["product_id", "week_start"], as_index=False)
        .agg(weekly_units=("sales_quantity", "sum"))
    )

    weekly_stats = (
        weekly_2025.groupby("product_id", as_index=False)
        .agg(
            weekly_mean_2025=("weekly_units", "mean"),
            weekly_std_2025=("weekly_units", "std"),
            weekly_max_2025=("weekly_units", "max"),
            active_weeks_2025=("weekly_units", lambda s: (s > 0).sum()),
        )
    )

    weekly_stats["weekly_std_2025"] = weekly_stats["weekly_std_2025"].fillna(0)
    weekly_stats["cv_2025"] = safe_divide(
        weekly_stats["weekly_std_2025"],
        weekly_stats["weekly_mean_2025"],
    )
    weekly_stats["peak_week_share_2025"] = safe_divide(
        weekly_stats["weekly_max_2025"],
        weekly_stats["weekly_mean_2025"] * weekly_stats["active_weeks_2025"],
    )

    product_metrics = product_metrics.merge(weekly_stats, on="product_id", how="left")

    # ---------------------------------------------------------------------
    # 4.3. MÉTRICAS DE FORECAST 2026
    # ---------------------------------------------------------------------
    forecast_2026 = (
        forecast.groupby("product_id", as_index=False)
        .agg(
            forecast_base_2026=("forecast_base", "sum"),
            forecast_optimista_2026=("forecast_optimista", "sum"),
            forecast_pesimista_2026=("forecast_pesimista", "sum"),
        )
    )

    product_metrics = product_metrics.merge(forecast_2026, on="product_id", how="left")

    product_metrics["forecast_base_vs_2025_abs"] = (
        product_metrics["forecast_base_2026"] - product_metrics["sales_units_2025"]
    )
    product_metrics["forecast_base_vs_2025_pct"] = safe_divide(
        product_metrics["forecast_base_vs_2025_abs"],
        product_metrics["sales_units_2025"],
    )

    # ---------------------------------------------------------------------
    # 4.4. ATRIBUTOS DE CATÁLOGO
    # ---------------------------------------------------------------------
    product_metrics = product_metrics.merge(catalog, on="product_id", how="left")

    if "cluster_catalogo" not in product_metrics.columns:
        product_metrics["cluster_catalogo"] = np.nan

    product_metrics["cluster_final"] = product_metrics["cluster_catalogo"].fillna(
        product_metrics["cluster_sales"]
    )
    product_metrics["cluster_final"] = product_metrics["cluster_final"].astype("string").fillna("Sin cluster")

    for col in ["categoria", "proveedor", "marca", "nombre"]:
        if col not in product_metrics.columns:
            product_metrics[col] = "Desconocido"
        product_metrics[col] = product_metrics[col].fillna("Desconocido")

    if "precio_medio_catalogo" in product_metrics.columns:
        product_metrics["avg_price_final"] = product_metrics["avg_price_2025"].fillna(
            product_metrics["precio_medio_catalogo"]
        )
    else:
        product_metrics["avg_price_final"] = product_metrics["avg_price_2025"]

    product_metrics["sales_value_2025_est"] = (
        product_metrics["sales_units_2025"] * product_metrics["avg_price_final"]
    )

    # ---------------------------------------------------------------------
    # 4.5. FLAGS Y PERFILES
    # ---------------------------------------------------------------------
    product_metrics["has_sales_2025"] = product_metrics["sales_units_2025"] > 0
    product_metrics["has_sales_2024"] = product_metrics["sales_units_2024"] > 0
    product_metrics["has_forecast_2026"] = product_metrics["forecast_base_2026"].fillna(0) > 0

    product_metrics["perfil_comportamiento"] = "Mixto"

    stable_mask = (
        (product_metrics["active_weeks_2025"] >= MIN_ACTIVE_WEEKS_STABLE)
        & (product_metrics["cv_2025"] <= product_metrics["cv_2025"].quantile(0.25))
    )

    seasonal_mask = (
        (product_metrics["active_weeks_2025"] >= MIN_ACTIVE_WEEKS_SEASONAL)
        & (
            (product_metrics["peak_week_share_2025"] >= product_metrics["peak_week_share_2025"].quantile(0.75))
            | (product_metrics["cv_2025"] >= product_metrics["cv_2025"].quantile(0.75))
        )
    )

    growth_mask = product_metrics["yoy_units_pct"].fillna(-np.inf) > 0

    product_metrics.loc[stable_mask, "perfil_comportamiento"] = "Estable"
    product_metrics.loc[seasonal_mask, "perfil_comportamiento"] = "Estacional/Irregular"
    product_metrics.loc[growth_mask & ~stable_mask & ~seasonal_mask, "perfil_comportamiento"] = "Creciente"

    product_metrics = product_metrics.sort_values(
        ["sales_value_2025_est", "sales_units_2025"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return product_metrics


# =============================================================================
# 5. CONTEXTO DE SELECCIÓN
# =============================================================================

def compute_top_categories(metrics: pd.DataFrame) -> list[str]:
    """Devuelve las categorías top por valor 2025."""
    cat_rank = (
        metrics.groupby("categoria", as_index=False)
        .agg(category_value_2025=("sales_value_2025_est", "sum"))
        .sort_values("category_value_2025", ascending=False)
    )
    return cat_rank["categoria"].head(TOP_CATEGORIES_ELIGIBLE).tolist()


def compute_top_categories_for_coverage(metrics: pd.DataFrame) -> list[str]:
    """Devuelve las categorías top a cubrir explícitamente."""
    cat_rank = (
        metrics.groupby("categoria", as_index=False)
        .agg(category_value_2025=("sales_value_2025_est", "sum"))
        .sort_values("category_value_2025", ascending=False)
    )
    return cat_rank["categoria"].head(TOP_CATEGORIES_COVERAGE).tolist()


def compute_top_providers_for_coverage(metrics: pd.DataFrame) -> list[str]:
    """Devuelve los proveedores top a cubrir explícitamente."""
    prov_rank = (
        metrics.groupby("proveedor", as_index=False)
        .agg(provider_value_2025=("sales_value_2025_est", "sum"))
        .sort_values("provider_value_2025", ascending=False)
    )
    return prov_rank["proveedor"].head(TOP_PROVIDERS_COVERAGE).tolist()


def compute_category_caps(metrics: pd.DataFrame) -> dict[str, int]:
    """
    Define un límite suave para la categoría dominante por valor 2025.
    El resto de categorías no tendrá límite explícito.
    """
    category_rank = (
        metrics.groupby("categoria", as_index=False)
        .agg(category_value_2025=("sales_value_2025_est", "sum"))
        .sort_values("category_value_2025", ascending=False)
        .reset_index(drop=True)
    )

    dominant_category = category_rank.loc[0, "categoria"]
    caps = {dominant_category: DOMINANT_CATEGORY_CAP}

    logger.info(
        "Categoría dominante detectada: %s | límite suave aplicado: %s",
        dominant_category,
        DOMINANT_CATEGORY_CAP,
    )

    return caps


def compute_cluster_quotas(metrics: pd.DataFrame, target_n: int) -> dict[str, int]:
    """
    Calcula cuotas objetivo por clúster:
    - mínimo por clúster,
    - reparto adicional por peso económico,
    - máximo porcentaje del total por clúster.
    """
    cluster_stats = (
        metrics.groupby("cluster_final", as_index=False)
        .agg(
            cluster_value_2025=("sales_value_2025_est", "sum"),
            n_products=("product_id", "nunique"),
        )
        .sort_values("cluster_value_2025", ascending=False)
        .reset_index(drop=True)
    )

    clusters = cluster_stats["cluster_final"].tolist()
    max_cap = math.floor(target_n * MAX_CLUSTER_SHARE)

    quotas: Dict[str, int] = {}
    for _, row in cluster_stats.iterrows():
        cluster = row["cluster_final"]
        available = int(row["n_products"])
        quotas[cluster] = min(MIN_PRODUCTS_PER_CLUSTER, available)

    assigned = sum(quotas.values())
    remaining = max(0, target_n - assigned)

    cluster_stats["value_share"] = (
        cluster_stats["cluster_value_2025"] / max(cluster_stats["cluster_value_2025"].sum(), EPSILON)
    )

    capacities: Dict[str, int] = {}
    raw_extras: Dict[str, float] = {}

    for _, row in cluster_stats.iterrows():
        cluster = row["cluster_final"]
        available = int(row["n_products"])
        capacity = max(0, min(max_cap, available) - quotas[cluster])
        capacities[cluster] = capacity
        raw_extras[cluster] = row["value_share"] * remaining

    extra_alloc = {
        cluster: min(int(math.floor(raw_extras[cluster])), capacities[cluster])
        for cluster in clusters
    }

    assigned_extra = sum(extra_alloc.values())
    remaining_extra = remaining - assigned_extra

    fractions = sorted(
        [
            (cluster, raw_extras[cluster] - math.floor(raw_extras[cluster]))
            for cluster in clusters
        ],
        key=lambda x: x[1],
        reverse=True,
    )

    for cluster, _ in fractions:
        if remaining_extra <= 0:
            break
        if extra_alloc[cluster] < capacities[cluster]:
            extra_alloc[cluster] += 1
            remaining_extra -= 1

    if remaining_extra > 0:
        cluster_order = cluster_stats.sort_values(
            "cluster_value_2025",
            ascending=False
        )["cluster_final"].tolist()

        for cluster in cluster_order:
            while remaining_extra > 0 and extra_alloc[cluster] < capacities[cluster]:
                extra_alloc[cluster] += 1
                remaining_extra -= 1
            if remaining_extra <= 0:
                break

    for cluster in clusters:
        quotas[cluster] += extra_alloc[cluster]

    total_quotas = sum(quotas.values())
    if total_quotas > target_n:
        overflow = total_quotas - target_n
        cluster_order_desc = cluster_stats.sort_values(
            "cluster_value_2025",
            ascending=False
        )["cluster_final"].tolist()

        for cluster in cluster_order_desc:
            removable = max(0, quotas[cluster] - MIN_PRODUCTS_PER_CLUSTER)
            to_remove = min(removable, overflow)
            quotas[cluster] -= to_remove
            overflow -= to_remove
            if overflow <= 0:
                break

    logger.info("Cuotas objetivo por clúster: %s", quotas)
    return quotas


# =============================================================================
# 6. LÓGICA DE SELECCIÓN
# =============================================================================

def add_candidates(
    candidate_df: pd.DataFrame,
    selected_ids: Set[str],
    primary_reason_map: Dict[str, str],
    criteria_map: Dict[str, Set[str]],
    cluster_counts: Dict[str, int],
    cluster_quotas: Dict[str, int],
    category_counts: Dict[str, int],
    category_caps: Dict[str, int],
    reason: str,
    max_new: Optional[int] = None,
    allowed_categories: Optional[Set[str]] = None,
) -> int:
    """
    Añade candidatos preservando:
    - orden del DataFrame
    - no duplicidad
    - cuotas por clúster
    - tope suave por categoría dominante

    Además separa:
    - motivo_principal = regla por la que el producto entra por primera vez
    - criterios_cumplidos = conjunto de reglas que el producto satisface
    """
    added = 0

    for _, row in candidate_df.iterrows():
        product_id = row["product_id"]
        cluster = row["cluster_final"]
        category = row["categoria"]

        if allowed_categories is not None and category not in allowed_categories:
            continue

        criteria_map.setdefault(product_id, set()).add(reason)

        if product_id in selected_ids:
            continue

        current_cluster_count = cluster_counts.get(cluster, 0)
        cluster_quota = cluster_quotas.get(cluster, TARGET_N_PRODUCTS)
        if current_cluster_count >= cluster_quota:
            continue

        current_category_count = category_counts.get(category, 0)
        category_cap = category_caps.get(category, TARGET_N_PRODUCTS)
        if current_category_count >= category_cap:
            continue

        selected_ids.add(product_id)
        primary_reason_map[product_id] = reason

        cluster_counts[cluster] = current_cluster_count + 1
        category_counts[category] = current_category_count + 1
        added += 1

        if max_new is not None and added >= max_new:
            break

    return added


def select_products(product_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Selección híbrida de productos para el dashboard.
    v3: incorpora bloque de productos a revisar y control suave de categoría dominante.
    """
    logger.info("Iniciando selección híbrida de productos (v3)...")

    metrics = product_metrics.copy()

    top_categories_eligible = set(compute_top_categories(metrics))
    top_categories_coverage = compute_top_categories_for_coverage(metrics)
    top_providers_coverage = compute_top_providers_for_coverage(metrics)
    cluster_quotas = compute_cluster_quotas(metrics, TARGET_N_PRODUCTS)
    category_caps = compute_category_caps(metrics)

    value_q30 = metrics["sales_value_2025_est"].quantile(0.30)
    value_q40 = metrics["sales_value_2025_est"].quantile(0.40)
    value_q50 = metrics["sales_value_2025_est"].quantile(0.50)
    value_q90 = metrics["sales_value_2025_est"].quantile(0.90)

    selected_ids: Set[str] = set()
    primary_reason_map: Dict[str, str] = {}
    criteria_map: Dict[str, Set[str]] = {}
    cluster_counts: Dict[str, int] = {cluster: 0 for cluster in cluster_quotas.keys()}
    category_counts: Dict[str, int] = {}

    # ---------------------------------------------------------------------
    # 6.1. CORE POR VALOR 2025
    # ---------------------------------------------------------------------
    core_candidates = metrics.loc[metrics["sales_value_2025_est"] > 0].copy()
    core_candidates = core_candidates.sort_values(
        ["sales_value_2025_est", "sales_units_2025"],
        ascending=[False, False],
    )

    add_candidates(
        core_candidates,
        selected_ids,
        primary_reason_map,
        criteria_map,
        cluster_counts,
        cluster_quotas,
        category_counts,
        category_caps,
        reason="Core valor 2025",
        max_new=CORE_PRODUCTS,
        allowed_categories=None,
    )

    # ---------------------------------------------------------------------
    # 6.2. CRECIMIENTO YoY
    # ---------------------------------------------------------------------
    growth_candidates = metrics.loc[
        (metrics["sales_units_2024"] > 0)
        & (metrics["sales_units_2025"] > 0)
        & (metrics["yoy_units_pct"].fillna(-np.inf) > 0.10)
        & (metrics["sales_value_2025_est"] >= value_q40)
        & (metrics["sales_value_2025_est"] <= value_q90)
    ].copy()

    growth_candidates = growth_candidates.sort_values(
        ["yoy_units_pct", "sales_value_2025_est"],
        ascending=[False, False],
    )

    add_candidates(
        growth_candidates,
        selected_ids,
        primary_reason_map,
        criteria_map,
        cluster_counts,
        cluster_quotas,
        category_counts,
        category_caps,
        reason="Crecimiento YoY",
        max_new=GROWTH_PRODUCTS,
        allowed_categories=top_categories_eligible,
    )

    # ---------------------------------------------------------------------
    # 6.3. OPORTUNIDAD FORECAST 2026
    # ---------------------------------------------------------------------
    forecast_candidates = metrics.loc[
        (metrics["sales_units_2025"] > 0)
        & (metrics["forecast_base_2026"] > 0)
        & (metrics["forecast_base_vs_2025_pct"].fillna(-np.inf) > 0.05)
        & (metrics["sales_value_2025_est"] >= value_q30)
    ].copy()

    forecast_candidates = forecast_candidates.sort_values(
        ["forecast_base_vs_2025_pct", "forecast_base_2026", "sales_value_2025_est"],
        ascending=[False, False, False],
    )

    add_candidates(
        forecast_candidates,
        selected_ids,
        primary_reason_map,
        criteria_map,
        cluster_counts,
        cluster_quotas,
        category_counts,
        category_caps,
        reason="Oportunidad forecast 2026",
        max_new=FORECAST_PRODUCTS,
        allowed_categories=top_categories_eligible,
    )

    # ---------------------------------------------------------------------
    # 6.4. ESTABILIDAD
    # ---------------------------------------------------------------------
    stable_candidates = metrics.loc[
        (metrics["active_weeks_2025"] >= MIN_ACTIVE_WEEKS_STABLE)
        & (metrics["sales_value_2025_est"] >= value_q40)
        & (metrics["cv_2025"].notna())
    ].copy()

    stable_candidates = stable_candidates.sort_values(
        ["cv_2025", "sales_value_2025_est"],
        ascending=[True, False],
    )

    add_candidates(
        stable_candidates,
        selected_ids,
        primary_reason_map,
        criteria_map,
        cluster_counts,
        cluster_quotas,
        category_counts,
        category_caps,
        reason="Producto estable",
        max_new=STABLE_PRODUCTS,
        allowed_categories=top_categories_eligible,
    )

    # ---------------------------------------------------------------------
    # 6.5. ESTACIONAL / IRREGULAR
    # ---------------------------------------------------------------------
    seasonal_candidates = metrics.loc[
        (metrics["active_weeks_2025"] >= MIN_ACTIVE_WEEKS_SEASONAL)
        & (metrics["sales_value_2025_est"] >= value_q30)
        & (
            (metrics["peak_week_share_2025"] >= metrics["peak_week_share_2025"].quantile(0.75))
            | (metrics["cv_2025"] >= metrics["cv_2025"].quantile(0.75))
        )
    ].copy()

    seasonal_candidates = seasonal_candidates.sort_values(
        ["peak_week_share_2025", "cv_2025", "sales_value_2025_est"],
        ascending=[False, False, False],
    )

    add_candidates(
        seasonal_candidates,
        selected_ids,
        primary_reason_map,
        criteria_map,
        cluster_counts,
        cluster_quotas,
        category_counts,
        category_caps,
        reason="Producto estacional/irregular",
        max_new=SEASONAL_PRODUCTS,
        allowed_categories=top_categories_eligible,
    )

    # ---------------------------------------------------------------------
    # 6.6. PRODUCTOS A REVISAR
    # ---------------------------------------------------------------------
    review_candidates = metrics.loc[
        (metrics["sales_units_2025"] > 0)
        & (metrics["sales_value_2025_est"] >= value_q40)
        & (
            (metrics["yoy_units_pct"].fillna(np.inf) <= 0)
            | (metrics["forecast_base_vs_2025_pct"].fillna(np.inf) <= 0.02)
        )
    ].copy()

    review_candidates = review_candidates.sort_values(
        ["sales_value_2025_est", "yoy_units_pct", "forecast_base_vs_2025_pct"],
        ascending=[False, True, True],
    )

    add_candidates(
        review_candidates,
        selected_ids,
        primary_reason_map,
        criteria_map,
        cluster_counts,
        cluster_quotas,
        category_counts,
        category_caps,
        reason="Producto a revisar",
        max_new=REVIEW_PRODUCTS,
        allowed_categories=top_categories_eligible,
    )

    # ---------------------------------------------------------------------
    # 6.7. COBERTURA DE CATEGORÍAS TOP
    # ---------------------------------------------------------------------
    selected_categories = set(
        metrics.loc[metrics["product_id"].isin(selected_ids), "categoria"].dropna().unique().tolist()
    )

    for category in top_categories_coverage:
        if category in selected_categories:
            continue

        category_candidates = metrics.loc[metrics["categoria"] == category].copy()
        category_candidates = category_candidates.sort_values(
            ["sales_value_2025_est", "sales_units_2025"],
            ascending=[False, False],
        )

        added = add_candidates(
            category_candidates,
            selected_ids,
            primary_reason_map,
            criteria_map,
            cluster_counts,
            cluster_quotas,
            category_counts,
            category_caps,
            reason="Cobertura categoría top",
            max_new=1,
            allowed_categories=None,
        )

        if added > 0:
            selected_categories.add(category)

    # ---------------------------------------------------------------------
    # 6.8. COBERTURA DE PROVEEDORES TOP
    # ---------------------------------------------------------------------
    selected_providers = set(
        metrics.loc[metrics["product_id"].isin(selected_ids), "proveedor"].dropna().unique().tolist()
    )

    for provider in top_providers_coverage:
        if provider in selected_providers:
            continue

        provider_candidates = metrics.loc[metrics["proveedor"] == provider].copy()
        provider_candidates = provider_candidates.sort_values(
            ["sales_value_2025_est", "sales_units_2025"],
            ascending=[False, False],
        )

        added = add_candidates(
            provider_candidates,
            selected_ids,
            primary_reason_map,
            criteria_map,
            cluster_counts,
            cluster_quotas,
            category_counts,
            category_caps,
            reason="Cobertura proveedor top",
            max_new=1,
            allowed_categories=top_categories_eligible,
        )

        if added > 0:
            selected_providers.add(provider)

    # ---------------------------------------------------------------------
    # 6.9. RELLENO PRINCIPAL
    # ---------------------------------------------------------------------
    if len(selected_ids) < TARGET_N_PRODUCTS:
        filler_candidates = metrics.sort_values(
            ["sales_value_2025_est", "sales_units_2025"],
            ascending=[False, False],
        )

        add_candidates(
            filler_candidates,
            selected_ids,
            primary_reason_map,
            criteria_map,
            cluster_counts,
            cluster_quotas,
            category_counts,
            category_caps,
            reason="Relleno por valor controlado",
            max_new=TARGET_N_PRODUCTS - len(selected_ids),
            allowed_categories=top_categories_eligible,
        )

    # ---------------------------------------------------------------------
    # 6.10. RELLENO SECUNDARIO
    # ---------------------------------------------------------------------
    if len(selected_ids) < TARGET_N_PRODUCTS:
        filler_all = metrics.sort_values(
            ["sales_value_2025_est", "sales_units_2025"],
            ascending=[False, False],
        )

        add_candidates(
            filler_all,
            selected_ids,
            primary_reason_map,
            criteria_map,
            cluster_counts,
            cluster_quotas,
            category_counts,
            category_caps,
            reason="Relleno por valor ampliado",
            max_new=TARGET_N_PRODUCTS - len(selected_ids),
            allowed_categories=None,
        )

    # ---------------------------------------------------------------------
    # 6.11. RELLENO FINAL RELAJADO
    # ---------------------------------------------------------------------
    if len(selected_ids) < TARGET_N_PRODUCTS:
        logger.warning(
            "No se alcanzó el objetivo con restricciones estrictas. "
            "Se aplica relleno final relajado."
        )

        filler_relaxed = metrics.sort_values(
            ["sales_value_2025_est", "sales_units_2025"],
            ascending=[False, False],
        )

        for _, row in filler_relaxed.iterrows():
            product_id = row["product_id"]
            cluster = row["cluster_final"]
            category = row["categoria"]

            criteria_map.setdefault(product_id, set()).add("Relleno final relajado")

            if product_id in selected_ids:
                continue

            selected_ids.add(product_id)
            primary_reason_map[product_id] = "Relleno final relajado"

            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

            if len(selected_ids) >= TARGET_N_PRODUCTS:
                break

    # ---------------------------------------------------------------------
    # 6.12. DATAFRAMES FINALES
    # ---------------------------------------------------------------------
    selected_df = metrics.loc[metrics["product_id"].isin(selected_ids)].copy()

    selected_df["motivo_principal"] = selected_df["product_id"].map(
        lambda pid: primary_reason_map.get(pid, "No informado")
    )

    selected_df["criterios_cumplidos"] = selected_df["product_id"].map(
        lambda pid: "; ".join(sorted(criteria_map.get(pid, set())))
    )

    selected_df = selected_df.sort_values(
        ["sales_value_2025_est", "sales_units_2025"],
        ascending=[False, False],
    ).reset_index(drop=True)

    if len(selected_df) > TARGET_N_PRODUCTS:
        selected_df = selected_df.head(TARGET_N_PRODUCTS).copy()

    trace_df = selected_df[
        [
            "product_id",
            "nombre",
            "marca",
            "proveedor",
            "categoria",
            "cluster_final",
            "sales_units_2024",
            "sales_units_2025",
            "sales_value_2025_est",
            "yoy_units_pct",
            "forecast_base_2026",
            "forecast_base_vs_2025_pct",
            "cv_2025",
            "peak_week_share_2025",
            "perfil_comportamiento",
            "motivo_principal",
            "criterios_cumplidos",
        ]
    ].copy()

    return selected_df, trace_df


# =============================================================================
# 7. VALIDACIONES DE SALIDA
# =============================================================================

def validate_selection(selected_df: pd.DataFrame, metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Valida la selección final y genera un resumen ejecutivo."""
    logger.info("Validando selección final...")

    if selected_df["product_id"].duplicated().any():
        raise ValueError("La selección final contiene Product_ID duplicados.")

    if len(selected_df) > TARGET_N_PRODUCTS:
        raise ValueError(
            f"La selección final supera el objetivo: {len(selected_df)} > {TARGET_N_PRODUCTS}"
        )

    cluster_dist = (
        selected_df.groupby("cluster_final", as_index=False)
        .agg(n_productos=("product_id", "nunique"))
        .sort_values("n_productos", ascending=False)
    )

    category_dist = (
        selected_df.groupby("categoria", as_index=False)
        .agg(n_productos=("product_id", "nunique"))
        .sort_values("n_productos", ascending=False)
    )

    cluster_dist_str = "; ".join(
        [f"{row['cluster_final']}={row['n_productos']}" for _, row in cluster_dist.iterrows()]
    )

    category_dist_str = "; ".join(
        [f"{row['categoria']}={row['n_productos']}" for _, row in category_dist.head(5).iterrows()]
    )

    summary = {
        "n_productos_seleccionados": int(len(selected_df)),
        "n_productos_objetivo": int(TARGET_N_PRODUCTS),
        "n_categorias_seleccionadas": int(selected_df["categoria"].nunique(dropna=True)),
        "n_clusters_seleccionados": int(selected_df["cluster_final"].nunique(dropna=True)),
        "n_proveedores_seleccionados": int(selected_df["proveedor"].nunique(dropna=True)),
        "ventas_2025_unidades_total_seleccion": float(selected_df["sales_units_2025"].sum()),
        "ventas_2025_valor_total_est_seleccion": float(selected_df["sales_value_2025_est"].sum()),
        "forecast_2026_base_total_seleccion": float(selected_df["forecast_base_2026"].sum()),
        "peso_valor_2025_seleccion_sobre_universo": float(
            selected_df["sales_value_2025_est"].sum()
            / max(metrics_df["sales_value_2025_est"].sum(), EPSILON)
        ),
        "distribucion_clusters": cluster_dist_str,
        "top_categorias_seleccion": category_dist_str,
    }

    return pd.DataFrame([summary])


# =============================================================================
# 8. EXPORTACIÓN / I/O
# =============================================================================

def export_outputs(
    selected_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    """Exporta los resultados del script."""
    logger.info("Exportando resultados de selección...")

    selected_export = selected_df[
        [
            "product_id",
            "nombre",
            "marca",
            "proveedor",
            "categoria",
            "cluster_final",
            "sales_units_2025",
            "sales_value_2025_est",
            "forecast_base_2026",
            "motivo_principal",
            "criterios_cumplidos",
        ]
    ].copy()

    export_dataframe(selected_export, OUT_SELECTED_FILE)
    export_dataframe(metrics_df, OUT_METRICS_FILE)
    export_dataframe(trace_df, OUT_TRACE_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_SELECTED_FILE.name)
    logger.info("Archivo exportado: %s", OUT_METRICS_FILE.name)
    logger.info("Archivo exportado: %s", OUT_TRACE_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 9. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta el flujo completo de selección de productos."""
    logger.info("==== INICIO | Selección de productos para dashboard (v3) ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    sales = load_sales()
    forecast = load_forecast()
    catalog = load_catalog()

    metrics_df = build_product_metrics(
        sales=sales,
        forecast=forecast,
        catalog=catalog,
    )

    selected_df, trace_df = select_products(metrics_df)
    summary_df = validate_selection(selected_df, metrics_df)

    export_outputs(
        selected_df=selected_df,
        metrics_df=metrics_df,
        trace_df=trace_df,
        summary_df=summary_df,
    )

    logger.info(
        "Selección final completada | productos=%s | categorías=%s | clústeres=%s | proveedores=%s",
        len(selected_df),
        selected_df["categoria"].nunique(dropna=True),
        selected_df["cluster_final"].nunique(dropna=True),
        selected_df["proveedor"].nunique(dropna=True),
    )

    logger.info("==== FIN | Selección de productos completada ====")


if __name__ == "__main__":
    main()