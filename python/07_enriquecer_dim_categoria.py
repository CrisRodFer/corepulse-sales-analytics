"""
===============================================================================
SCRIPT: 07_enriquecer_dim_categoria.py
===============================================================================
DESCRIPCIÓN
-----------
Enriquece la dimensión categoría base incorporando atributos analíticos
ligeros y defendibles para el dashboard.

La lógica de enriquecimiento añade:
- familia_categoria
- orden_categoria
- formato_categoria

El objetivo es mejorar la capacidad de segmentación y el orden visual de la
dimensión, sin introducir atributos demasiado interpretativos o difíciles de
justificar con la información disponible.

SALIDAS
-------
1. dim_categoria_enriquecida.csv
2. resumen_dim_categoria_enriquecida.csv

INPUT ESPERADO
--------------
- data/processed/dim_categoria.csv

OUTPUT ESPERADO
---------------
- data/processed/dim_categoria_enriquecida.csv
- data/processed/resumen_dim_categoria_enriquecida.csv

DEPENDENCIAS
------------
- pandas

INSTALACIÓN RÁPIDA
------------------
pip install pandas
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

INPUT_CATEGORY_FILE = PROCESSED_DIR / "dim_categoria.csv"

OUT_CATEGORY_FILE = PROCESSED_DIR / "dim_categoria_enriquecida.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_dim_categoria_enriquecida.csv"


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

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
    """Valida que exista dim_categoria."""
    if not INPUT_CATEGORY_FILE.exists():
        raise FileNotFoundError(f"No se encuentra el archivo de entrada: {INPUT_CATEGORY_FILE}")


def export_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Exporta un DataFrame según la extensión."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    else:
        raise ValueError(f"Extensión no soportada: {path.suffix}")


def normalize_text(series: pd.Series, fallback: str | None = None) -> pd.Series:
    """Normaliza texto, espacios y nulos."""
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
    if fallback is not None:
        s = s.fillna(fallback)
    return s


# =============================================================================
# 3. MAPA DE ENRIQUECIMIENTO
# =============================================================================

CATEGORY_ENRICHMENT_MAP = {
    "Aminoacidos": {
        "familia_categoria": "Suplementación deportiva",
        "orden_categoria": 7,
        "formato_categoria": "Cápsulas / Polvo",
    },
    "Barritas": {
        "familia_categoria": "Nutrición funcional",
        "orden_categoria": 5,
        "formato_categoria": "Sólido",
    },
    "Bebidas": {
        "familia_categoria": "Nutrición funcional",
        "orden_categoria": 4,
        "formato_categoria": "Líquido",
    },
    "Cheat Meal": {
        "familia_categoria": "Alimentación funcional",
        "orden_categoria": 10,
        "formato_categoria": "Sólido",
    },
    "Cosmética": {
        "familia_categoria": "Cuidado personal",
        "orden_categoria": 19,
        "formato_categoria": "Tópico",
    },
    "Creatina": {
        "familia_categoria": "Suplementación deportiva",
        "orden_categoria": 3,
        "formato_categoria": "Polvo / Cápsulas",
    },
    "Definición": {
        "familia_categoria": "Objetivo físico",
        "orden_categoria": 11,
        "formato_categoria": "Mixto / No dominante",
    },
    "Deportes": {
        "familia_categoria": "Accesorios / deporte",
        "orden_categoria": 18,
        "formato_categoria": "No aplica",
    },
    "Energía": {
        "familia_categoria": "Rendimiento deportivo",
        "orden_categoria": 2,
        "formato_categoria": "Mixto / No dominante",
    },
    "Fit Food": {
        "familia_categoria": "Alimentación funcional",
        "orden_categoria": 9,
        "formato_categoria": "Sólido",
    },
    "Hidratación": {
        "familia_categoria": "Rendimiento deportivo",
        "orden_categoria": 6,
        "formato_categoria": "Polvo / Líquido",
    },
    "Hidratos de carbono": {
        "familia_categoria": "Rendimiento deportivo",
        "orden_categoria": 8,
        "formato_categoria": "Polvo / Gel",
    },
    "Masa muscular": {
        "familia_categoria": "Objetivo físico",
        "orden_categoria": 12,
        "formato_categoria": "Mixto / No dominante",
    },
    "Post entreno": {
        "familia_categoria": "Rendimiento deportivo",
        "orden_categoria": 14,
        "formato_categoria": "Mixto / No dominante",
    },
    "Pre-Entreno": {
        "familia_categoria": "Rendimiento deportivo",
        "orden_categoria": 13,
        "formato_categoria": "Polvo / Líquido",
    },
    "Proteínas": {
        "familia_categoria": "Suplementación deportiva",
        "orden_categoria": 1,
        "formato_categoria": "Polvo",
    },
    "Recuperación": {
        "familia_categoria": "Rendimiento deportivo",
        "orden_categoria": 15,
        "formato_categoria": "Mixto / No dominante",
    },
    "Sustitutos y otros": {
        "familia_categoria": "Alimentación funcional",
        "orden_categoria": 17,
        "formato_categoria": "Mixto / No dominante",
    },
    "Vitaminas y Minerales": {
        "familia_categoria": "Salud y bienestar",
        "orden_categoria": 16,
        "formato_categoria": "Cápsulas / Comprimidos",
    },
}


# =============================================================================
# 4. CARGA DE DATOS
# =============================================================================

def load_dim_categoria() -> pd.DataFrame:
    """Carga la dimensión categoría base."""
    logger.info("Cargando dim_categoria base...")
    df = pd.read_csv(INPUT_CATEGORY_FILE)

    required_cols = {"category_id", "categoria"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas obligatorias en dim_categoria: {missing}")

    df["category_id"] = normalize_text(df["category_id"])
    df["categoria"] = normalize_text(df["categoria"], fallback="Desconocido")

    df = df.drop_duplicates(subset=["category_id"]).copy()
    return df


# =============================================================================
# 5. LÓGICA PRINCIPAL
# =============================================================================

def apply_category_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enriquece la dimensión categoría a partir del mapa predefinido.
    """
    logger.info("Aplicando enriquecimiento de categoría...")

    out = df.copy()

    enrich_df = pd.DataFrame.from_dict(CATEGORY_ENRICHMENT_MAP, orient="index").reset_index()
    enrich_df = enrich_df.rename(columns={"index": "categoria"})

    out = out.merge(
        enrich_df,
        on="categoria",
        how="left",
        validate="one_to_one",
    )

    # Fallbacks defensivos por si apareciera alguna categoría no mapeada
    out["familia_categoria"] = normalize_text(
        out["familia_categoria"],
        fallback="No clasificada",
    )
    out["formato_categoria"] = normalize_text(
        out["formato_categoria"],
        fallback="Mixto / No dominante",
    )

    if "orden_categoria" not in out.columns:
        out["orden_categoria"] = pd.NA

    # Si alguna categoría quedara sin orden, asignar al final
    max_order = pd.to_numeric(out["orden_categoria"], errors="coerce").max()
    if pd.isna(max_order):
        max_order = 0

    missing_order_mask = pd.to_numeric(out["orden_categoria"], errors="coerce").isna()
    if missing_order_mask.any():
        missing_categories = out.loc[missing_order_mask, "categoria"].tolist()
        logger.warning(
            "Se han encontrado categorías fuera del mapa. Se asignarán al final: %s",
            missing_categories,
        )

        next_order = int(max_order) + 1
        for idx in out.loc[missing_order_mask].index:
            out.at[idx, "orden_categoria"] = next_order
            next_order += 1

    out["orden_categoria"] = pd.to_numeric(out["orden_categoria"], errors="coerce").astype(int)

    out = out[
        [
            "category_id",
            "categoria",
            "familia_categoria",
            "orden_categoria",
            "formato_categoria",
        ]
    ].copy()

    out = out.sort_values(["orden_categoria", "categoria"]).reset_index(drop=True)
    return out


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye resumen de validación de la dimensión enriquecida.
    """
    summary = {
        "n_filas_dim_categoria_enriquecida": int(len(df)),
        "duplicados_category_id": int(df["category_id"].duplicated().sum()),
        "familias_unicas": int(df["familia_categoria"].nunique(dropna=True)),
        "formatos_unicos": int(df["formato_categoria"].nunique(dropna=True)),
        "ordenes_duplicados": int(df["orden_categoria"].duplicated().sum()),
        "nulos_familia_categoria": int(df["familia_categoria"].isna().sum()),
        "nulos_formato_categoria": int(df["formato_categoria"].isna().sum()),
    }

    return pd.DataFrame([summary])


# =============================================================================
# 6. EXPORTACIÓN / I/O
# =============================================================================

def export_outputs(df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    """Exporta la dimensión enriquecida y su resumen."""
    logger.info("Exportando resultados...")

    export_dataframe(df, OUT_CATEGORY_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_CATEGORY_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 7. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta el enriquecimiento de la dimensión categoría."""
    logger.info("==== INICIO | Enriquecimiento de dim_categoria ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    dim_categoria = load_dim_categoria()
    enriched = apply_category_enrichment(dim_categoria)
    summary_df = build_summary(enriched)
    export_outputs(enriched, summary_df)

    logger.info(
        "Dimensión enriquecida construida | filas=%s | familias=%s | formatos=%s",
        len(enriched),
        enriched["familia_categoria"].nunique(dropna=True),
        enriched["formato_categoria"].nunique(dropna=True),
    )
    logger.info("==== FIN | Enriquecimiento de dim_categoria ====")


if __name__ == "__main__":
    main()