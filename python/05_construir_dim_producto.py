"""
===============================================================================
SCRIPT: 05_construir_dim_producto.py
===============================================================================
DESCRIPCIÓN
-----------
Construye la dimensión producto del dashboard y, en paralelo, las dimensiones
auxiliares de categoría y proveedor.

La lógica parte del subconjunto final de productos seleccionado y recupera los
atributos descriptivos y analíticos necesarios para el modelo estrella.

SALIDAS
-------
1. dim_producto.csv
2. dim_producto.xlsx
3. dim_categoria.csv
4. dim_proveedor.csv
5. resumen_dim_producto.csv

OBJETIVO
--------
- Dejar Dim_Producto limpia y lista para relacionarse con la fact base.
- Separar categoría y proveedor en dimensiones propias.
- Mantener en producto únicamente atributos propios del producto y claves
  hacia las dimensiones auxiliares.

ATRIBUTOS INCLUIDOS EN DIM_PRODUCTO
-----------------------------------
- product_id
- category_id
- provider_id
- nombre
- marca
- ean13
- pack_size
- uom
- cluster_final
- perfil_comportamiento

ATRIBUTOS EXCLUIDOS
-------------------
- is_outlier_catalogo
- estado_producto

INPUT ESPERADO
--------------
- data/processed/productos_seleccionados_dashboard.csv
- data/processed/metricas_producto_dashboard.csv
- data/raw/catalog_items_enriquecido.csv

OUTPUT ESPERADO
---------------
- data/processed/dim_producto.csv
- data/processed/dim_producto.xlsx
- data/processed/dim_categoria.csv
- data/processed/dim_proveedor.csv
- data/processed/resumen_dim_producto.csv

DEPENDENCIAS
------------
- pandas
- numpy
- openpyxl

INSTALACIÓN RÁPIDA
------------------
pip install pandas numpy openpyxl
===============================================================================
"""

# =============================================================================
# 0. CONFIG
# =============================================================================

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"

SELECTED_PRODUCTS_FILE = PROCESSED_DIR / "productos_seleccionados_dashboard.csv"
PRODUCT_METRICS_FILE = PROCESSED_DIR / "metricas_producto_dashboard.csv"
CATALOG_FILE = RAW_DIR / "catalog_items_enriquecido.csv"

OUT_PRODUCT_FILE = PROCESSED_DIR / "dim_producto.csv"
OUT_PRODUCT_XLSX_FILE = PROCESSED_DIR / "dim_producto.xlsx"
OUT_CATEGORY_FILE = PROCESSED_DIR / "dim_categoria.csv"
OUT_PROVIDER_FILE = PROCESSED_DIR / "dim_proveedor.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_dim_producto.csv"


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import csv
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
        SELECTED_PRODUCTS_FILE,
        PRODUCT_METRICS_FILE,
        CATALOG_FILE,
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan archivos de entrada:\n- " + "\n- ".join(missing)
        )


def export_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Exporta un DataFrame según la extensión."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".csv":
        df.to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
            quoting=csv.QUOTE_ALL,
        )
    elif path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    else:
        raise ValueError(f"Extensión no soportada: {path.suffix}")


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


def normalize_text_column(series: pd.Series, fallback: str = "Desconocido") -> pd.Series:
    """Normaliza columnas de texto y rellena vacíos."""
    s = series.astype("string").str.strip()
    s = s.replace(
        {
            "": pd.NA,
            "nan": pd.NA,
            "None": pd.NA,
            "NaN": pd.NA,
            "<NA>": pd.NA,
        }
    )
    return s.fillna(fallback)


def build_sequential_id(prefix: str, values: pd.Series) -> pd.DataFrame:
    """
    Construye IDs secuenciales estables a partir de un conjunto de valores únicos.
    """
    unique_values = (
        pd.Series(values.dropna().astype("string").unique())
        .sort_values()
        .reset_index(drop=True)
    )

    df = pd.DataFrame({"value": unique_values})
    df[f"{prefix.lower()}_id"] = [
        f"{prefix}_{str(i).zfill(3)}" for i in range(1, len(df) + 1)
    ]
    return df


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

    return df[["product_id"]]


def load_product_metrics() -> pd.DataFrame:
    """
    Carga métricas agregadas por producto, que ya contienen gran parte de los
    atributos descriptivos y analíticos necesarios.
    """
    logger.info("Cargando métricas de producto...")
    df = pd.read_csv(PRODUCT_METRICS_FILE)

    if "product_id" not in df.columns:
        raise KeyError("El archivo de métricas no contiene 'product_id'.")

    df["product_id"] = normalizar_product_id(df["product_id"])

    expected_cols = [
        "product_id",
        "nombre",
        "marca",
        "ean13",
        "categoria",
        "proveedor",
        "cluster_final",
        "perfil_comportamiento",
    ]

    available_cols = [col for col in expected_cols if col in df.columns]
    extra_cols = [c for c in ["pack_size", "uom"] if c in df.columns]

    df = df[available_cols + extra_cols].copy()
    df = df.drop_duplicates(subset=["product_id"]).copy()

    return df


def load_catalog() -> pd.DataFrame:
    """
    Carga catálogo enriquecido para rescatar atributos que puedan no estar en
    métricas, como pack_size o uom.
    """
    logger.info("Cargando catálogo enriquecido...")
    df = pd.read_csv(CATALOG_FILE)

    rename_map = {
        "Product_ID": "product_id",
        "EAN13": "ean13",
        "Marca": "marca",
        "Proveedor": "proveedor",
        "Nombre": "nombre",
        "Categoria": "categoria",
    }

    available_rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=available_rename_map)

    if "product_id" not in df.columns:
        raise KeyError("El catálogo no contiene 'Product_ID' / 'product_id'.")

    df["product_id"] = normalizar_product_id(df["product_id"])
    df = df.dropna(subset=["product_id"]).copy()

    keep_cols = ["product_id", "nombre", "marca", "ean13", "proveedor", "categoria"]
    keep_cols += [c for c in ["pack_size", "uom"] if c in df.columns]
    keep_cols = [c for c in keep_cols if c in df.columns]

    df = df[keep_cols].drop_duplicates(subset=["product_id"]).copy()

    return df


# =============================================================================
# 4. CONSTRUCCIÓN DE DIMENSIONES
# =============================================================================

def build_base_product_table(
    selected_products: pd.DataFrame,
    product_metrics: pd.DataFrame,
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye una base de producto consolidada a partir de métricas y catálogo.
    """
    logger.info("Construyendo base consolidada de producto...")

    base = selected_products.merge(
        product_metrics,
        on="product_id",
        how="left",
        validate="one_to_one",
    )

    catalog_suffix_cols = [c for c in catalog.columns if c != "product_id"]
    catalog_renamed = catalog.rename(
        columns={col: f"{col}_catalog" for col in catalog_suffix_cols}
    )

    base = base.merge(
        catalog_renamed,
        on="product_id",
        how="left",
        validate="one_to_one",
    )

    # Resolver atributos descriptivos priorizando métricas y luego catálogo
    for col in ["nombre", "marca", "ean13", "categoria", "proveedor", "pack_size", "uom"]:
        col_catalog = f"{col}_catalog"
        if col not in base.columns and col_catalog in base.columns:
            base[col] = base[col_catalog]
        elif col in base.columns and col_catalog in base.columns:
            base[col] = base[col].fillna(base[col_catalog])

    # Normalización final
    for col in ["nombre", "marca", "categoria", "proveedor", "cluster_final", "perfil_comportamiento", "uom"]:
        if col in base.columns:
            base[col] = normalize_text_column(base[col])

    if "ean13" in base.columns:
        base["ean13"] = base["ean13"].astype("string").str.strip()

    if "pack_size" in base.columns:
        base["pack_size"] = pd.to_numeric(base["pack_size"], errors="coerce")

    # Si no existen, se crean vacías
    for col in ["pack_size", "uom", "ean13", "cluster_final", "perfil_comportamiento"]:
        if col not in base.columns:
            base[col] = pd.NA

    return base


def build_dim_categoria(base_product: pd.DataFrame) -> pd.DataFrame:
    """Construye Dim_Categoria."""
    logger.info("Construyendo dim_categoria...")

    cat_map = build_sequential_id("CAT", base_product["categoria"])
    cat_map = cat_map.rename(columns={"value": "categoria"})

    dim_categoria = cat_map[["cat_id", "categoria"]].copy()
    dim_categoria = dim_categoria.rename(columns={"cat_id": "category_id"})

    return dim_categoria


def build_dim_proveedor(base_product: pd.DataFrame) -> pd.DataFrame:
    """Construye Dim_Proveedor."""
    logger.info("Construyendo dim_proveedor...")

    prov_map = build_sequential_id("PRV", base_product["proveedor"])
    prov_map = prov_map.rename(columns={"value": "proveedor"})

    dim_proveedor = prov_map[["prv_id", "proveedor"]].copy()
    dim_proveedor = dim_proveedor.rename(columns={"prv_id": "provider_id"})

    return dim_proveedor


def build_dim_producto(
    base_product: pd.DataFrame,
    dim_categoria: pd.DataFrame,
    dim_proveedor: pd.DataFrame,
) -> pd.DataFrame:
    """Construye Dim_Producto."""
    logger.info("Construyendo dim_producto...")

    dim_producto = base_product.merge(
        dim_categoria,
        on="categoria",
        how="left",
        validate="many_to_one",
    )

    dim_producto = dim_producto.merge(
        dim_proveedor,
        on="proveedor",
        how="left",
        validate="many_to_one",
    )

    dim_producto = dim_producto[
        [
            "product_id",
            "category_id",
            "provider_id",
            "nombre",
            "marca",
            "ean13",
            "pack_size",
            "uom",
            "cluster_final",
            "perfil_comportamiento",
        ]
    ].copy()

    # Orden y limpieza final
    dim_producto = dim_producto.drop_duplicates(subset=["product_id"]).copy()
    dim_producto = dim_producto.sort_values("product_id").reset_index(drop=True)

    return dim_producto


def validate_dim_producto(dim_producto: pd.DataFrame) -> None:
    """Valida estructura básica de dim_producto antes de exportar."""
    expected_cols = [
        "product_id",
        "category_id",
        "provider_id",
        "nombre",
        "marca",
        "ean13",
        "pack_size",
        "uom",
        "cluster_final",
        "perfil_comportamiento",
    ]

    missing = [c for c in expected_cols if c not in dim_producto.columns]
    if missing:
        raise ValueError(f"Faltan columnas en dim_producto: {missing}")

    if dim_producto["product_id"].duplicated().any():
        raise ValueError("dim_producto contiene product_id duplicados.")


def build_summary(
    dim_producto: pd.DataFrame,
    dim_categoria: pd.DataFrame,
    dim_proveedor: pd.DataFrame,
) -> pd.DataFrame:
    """Construye un resumen simple de validación."""
    summary = {
        "n_filas_dim_producto": int(len(dim_producto)),
        "n_productos_unicos": int(dim_producto["product_id"].nunique(dropna=True)),
        "duplicados_product_id": int(dim_producto["product_id"].duplicated().sum()),
        "n_filas_dim_categoria": int(len(dim_categoria)),
        "duplicados_category_id": int(dim_categoria["category_id"].duplicated().sum()),
        "n_filas_dim_proveedor": int(len(dim_proveedor)),
        "duplicados_provider_id": int(dim_proveedor["provider_id"].duplicated().sum()),
        "nulos_category_id_en_producto": int(dim_producto["category_id"].isna().sum()),
        "nulos_provider_id_en_producto": int(dim_producto["provider_id"].isna().sum()),
    }

    return pd.DataFrame([summary])


# =============================================================================
# 5. EXPORTACIÓN / I/O
# =============================================================================

def export_outputs(
    dim_producto: pd.DataFrame,
    dim_categoria: pd.DataFrame,
    dim_proveedor: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    """Exporta las dimensiones y su resumen."""
    logger.info("Exportando dimensiones de producto...")

    export_dataframe(dim_producto, OUT_PRODUCT_FILE)
    export_dataframe(dim_producto, OUT_PRODUCT_XLSX_FILE)
    export_dataframe(dim_categoria, OUT_CATEGORY_FILE)
    export_dataframe(dim_proveedor, OUT_PROVIDER_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_PRODUCT_FILE.name)
    logger.info("Archivo exportado: %s", OUT_PRODUCT_XLSX_FILE.name)
    logger.info("Archivo exportado: %s", OUT_CATEGORY_FILE.name)
    logger.info("Archivo exportado: %s", OUT_PROVIDER_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 6. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta la construcción de la dimensión producto y auxiliares."""
    logger.info("==== INICIO | Construcción de dimensiones de producto ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    selected_products = load_selected_products()
    product_metrics = load_product_metrics()
    catalog = load_catalog()

    base_product = build_base_product_table(
        selected_products=selected_products,
        product_metrics=product_metrics,
        catalog=catalog,
    )

    dim_categoria = build_dim_categoria(base_product)
    dim_proveedor = build_dim_proveedor(base_product)
    dim_producto = build_dim_producto(
        base_product=base_product,
        dim_categoria=dim_categoria,
        dim_proveedor=dim_proveedor,
    )

    validate_dim_producto(dim_producto)

    summary_df = build_summary(
        dim_producto=dim_producto,
        dim_categoria=dim_categoria,
        dim_proveedor=dim_proveedor,
    )

    export_outputs(
        dim_producto=dim_producto,
        dim_categoria=dim_categoria,
        dim_proveedor=dim_proveedor,
        summary_df=summary_df,
    )

    logger.info(
        "Dimensiones construidas | producto=%s | categoría=%s | proveedor=%s",
        len(dim_producto),
        len(dim_categoria),
        len(dim_proveedor),
    )
    logger.info("==== FIN | Construcción de dimensiones de producto ====")


if __name__ == "__main__":
    main()