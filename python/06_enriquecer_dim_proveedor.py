"""
===============================================================================
SCRIPT: 06_enriquecer_dim_proveedor.py
===============================================================================
DESCRIPCIÓN
-----------
Enriquece la dimensión proveedor base incorporando:

1. Datos públicos de identificación y localización, cuando han podido
   verificarse para proveedores reales.
2. Atributos operativos simulados de referencia:
   - lead_time_dias_sim
   - pedido_minimo_sim

El objetivo es transformar una dimensión proveedor mínima en una dimensión más
útil para el dashboard, sin presentar como reales atributos logísticos que
habitualmente no son públicos.

SALIDAS
-------
1. dim_proveedor_enriquecida.csv
2. resumen_dim_proveedor_enriquecida.csv

INPUT ESPERADO
--------------
- data/processed/dim_proveedor.csv

OUTPUT ESPERADO
---------------
- data/processed/dim_proveedor_enriquecida.csv
- data/processed/resumen_dim_proveedor_enriquecida.csv

DEPENDENCIAS
------------
- pandas
- numpy

INSTALACIÓN RÁPIDA
------------------
pip install pandas numpy

NOTAS
-----
- Los campos públicos (CIF y localización) se rellenan cuando existe
  información verificable.
- Los campos logísticos son simulados, pero de forma determinista y coherente.
- Para los proveedores no cubiertos por el mapa público, se aplican valores
  de respaldo conservadores.
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

INPUT_PROVIDER_FILE = PROCESSED_DIR / "dim_proveedor.csv"

OUT_PROVIDER_FILE = PROCESSED_DIR / "dim_proveedor_enriquecida.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_dim_proveedor_enriquecida.csv"


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import logging
import re
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
    """Valida que exista la dimensión proveedor base."""
    if not INPUT_PROVIDER_FILE.exists():
        raise FileNotFoundError(f"No se encuentra el archivo de entrada: {INPUT_PROVIDER_FILE}")


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


def normalize_provider_name(name: str) -> str:
    """
    Normaliza el nombre del proveedor para hacer matching robusto.
    """
    if pd.isna(name):
        return ""
    name = str(name).upper().strip()
    name = name.replace(",", " ")
    name = re.sub(r"\s+", " ", name)
    return name


def stable_hash(value: str) -> int:
    """
    Hash determinista sencillo para asignaciones reproducibles.
    """
    return sum(ord(ch) for ch in str(value))


def pick_from_options(key: str, options: list):
    """Elige una opción de forma determinista."""
    idx = stable_hash(key) % len(options)
    return options[idx]


# =============================================================================
# 3. DATOS PÚBLICOS Y REGLAS DE SIMULACIÓN
# =============================================================================

# -------------------------------------------------------------------------
# MAPA PÚBLICO VERIFICADO / SEMIVERIFICADO
# -------------------------------------------------------------------------
# La clave debe coincidir con el nombre normalizado del proveedor base.
# Los campos no disponibles se dejan como None y se completan con reglas.
# -------------------------------------------------------------------------

PUBLIC_PROVIDER_MAP = {
    "226ERS SPORTS THINGS SL": {
        "cif": "B54511670",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Alicante",
        "ciudad": "Alcoy",
        "tipo_proveedor": "Fabricante nacional",
    },
    "AMIX LEVANTE S.L.": {
        "cif": "B54442686",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Alicante",
        "ciudad": "Almoradí",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "BASTOS MEDICAL": {
        "cif": "B61566006",
        "pais": "España",
        "ccaa": "Cataluña",
        "provincia": "Barcelona",
        "ciudad": "Sant Fruitós de Bages",
        "tipo_proveedor": "Especializado / medical",
    },
    "BIG MAN NUTRITION SL": {
        "cif": "B54177696",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Alicante",
        "ciudad": "Rafal",
        "tipo_proveedor": "Fabricante nacional",
    },
    "BIG MAN NUTRITION, SL": {
        "cif": "B54177696",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Alicante",
        "ciudad": "Rafal",
        "tipo_proveedor": "Fabricante nacional",
    },
    "BIOTECH USA SL": {
        "cif": "B86832359",
        "pais": "España",
        "ccaa": "Comunidad de Madrid",
        "provincia": "Madrid",
        "ciudad": "Madrid",
        "tipo_proveedor": "Fabricante nacional",
    },
    "BIOTECH USA, SL": {
        "cif": "B86832359",
        "pais": "España",
        "ccaa": "Comunidad de Madrid",
        "provincia": "Madrid",
        "ciudad": "Madrid",
        "tipo_proveedor": "Fabricante nacional",
    },
    "CROWN NUTRITION": {
        "cif": "B26278028",
        "pais": "España",
        "ccaa": "La Rioja",
        "provincia": "La Rioja",
        "ciudad": "Arnedo",
        "tipo_proveedor": "Fabricante nacional",
    },
    "DRASANVI SL": {
        "cif": "B24279093",
        "pais": "España",
        "ccaa": "Castilla y León",
        "provincia": "León",
        "ciudad": "Villadangos del Páramo",
        "tipo_proveedor": "Fabricante nacional",
    },
    "DRASANVI, SL": {
        "cif": "B24279093",
        "pais": "España",
        "ccaa": "Castilla y León",
        "provincia": "León",
        "ciudad": "Villadangos del Páramo",
        "tipo_proveedor": "Fabricante nacional",
    },
    "GLANBIA NUTRITIONALS": {
        "cif": None,
        "pais": "Irlanda",
        "ccaa": "No aplica",
        "provincia": "Kilkenny",
        "ciudad": "Kilkenny",
        "tipo_proveedor": "Fabricante internacional",
    },
    "GOLDNUTRITION SL": {
        "cif": "B87182051",
        "pais": "España",
        "ccaa": "Comunidad de Madrid",
        "provincia": "Madrid",
        "ciudad": "Madrid",
        "tipo_proveedor": "Fabricante nacional",
    },
    "GOLDNUTRITION, SL": {
        "cif": "B87182051",
        "pais": "España",
        "ccaa": "Comunidad de Madrid",
        "provincia": "Madrid",
        "ciudad": "Madrid",
        "tipo_proveedor": "Fabricante nacional",
    },
    "HEALTHY VITAFOOD SL": {
        "cif": "B93488179",
        "pais": "España",
        "ccaa": "Andalucía",
        "provincia": "Málaga",
        "ciudad": "Málaga",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "HEALTHY VITAFOOD, SL": {
        "cif": "B93488179",
        "pais": "España",
        "ccaa": "Andalucía",
        "provincia": "Málaga",
        "ciudad": "Málaga",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "INDIEX (LIFE PRO)": {
        "cif": "B87111001",
        "pais": "España",
        "ccaa": "Comunidad de Madrid",
        "provincia": "Madrid",
        "ciudad": "Mejorada del Campo",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "JAUSUN IMPORT EXPORT SL": {
        "cif": "B25342312",
        "pais": "España",
        "ccaa": "Cataluña",
        "provincia": "Lleida",
        "ciudad": "Alcoletge",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "JAUSUN IMPORT EXPORT, SL": {
        "cif": "B25342312",
        "pais": "España",
        "ccaa": "Cataluña",
        "provincia": "Lleida",
        "ciudad": "Alcoletge",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "MARES S.P.A.": {
        "cif": "IT00204770994",
        "pais": "Italia",
        "ccaa": "No aplica",
        "provincia": "Genova",
        "ciudad": "Rapallo",
        "tipo_proveedor": "Fabricante internacional",
    },
    "NANONEN SL": {
        "cif": "B98669690",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Valencia",
        "ciudad": "Paterna",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "NANONEN, SL": {
        "cif": "B98669690",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Valencia",
        "ciudad": "Paterna",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "NASKORSPORTS": {
        "cif": None,
        "pais": "Países Bajos",
        "ccaa": "No aplica",
        "provincia": "Limburgo",
        "ciudad": "Tegelen",
        "tipo_proveedor": "Distribuidor internacional",
    },
    "NATURBEST SLU": {
        "cif": "B54487202",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Alicante",
        "ciudad": "Elda",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "NATURBEST, SLU": {
        "cif": "B54487202",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Alicante",
        "ciudad": "Elda",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "NUTRINOVEX SPORT INNOVATIONS SL": {
        "cif": "B12841474",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Castellón",
        "ciudad": "Castellón de la Plana",
        "tipo_proveedor": "Fabricante nacional",
    },
    "NUTRINOVEX SPORT INNOVATIONS, SL": {
        "cif": "B12841474",
        "pais": "España",
        "ccaa": "Comunidad Valenciana",
        "provincia": "Castellón",
        "ciudad": "Castellón de la Plana",
        "tipo_proveedor": "Fabricante nacional",
    },
    "NUTRISPORT S.A.U.": {
        "cif": "A08894750",
        "pais": "España",
        "ccaa": "Cataluña",
        "provincia": "Barcelona",
        "ciudad": "Argentona",
        "tipo_proveedor": "Fabricante nacional",
    },
    "OLIMP LABORATORIES ES": {
        "cif": "B87462438",
        "pais": "España",
        "ccaa": "Andalucía",
        "provincia": "Granada",
        "ciudad": "Granada",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "PROFITNESS CENTURY SL": {
        "cif": "B86446242",
        "pais": "España",
        "ccaa": "Cataluña",
        "provincia": "Barcelona",
        "ciudad": "Barcelona",
        "tipo_proveedor": "Distribuidor nacional",
    },
    "PROFITNESS CENTURY, SL": {
        "cif": "B86446242",
        "pais": "España",
        "ccaa": "Cataluña",
        "provincia": "Barcelona",
        "ciudad": "Barcelona",
        "tipo_proveedor": "Distribuidor nacional",
    },
}

# -------------------------------------------------------------------------
# REGLAS DE SIMULACIÓN
# -------------------------------------------------------------------------

LEAD_TIME_RULES = {
    "Fabricante nacional": (3, 5),
    "Distribuidor nacional": (4, 6),
    "Especializado / medical": (5, 7),
    "Fabricante internacional": (7, 10),
    "Distribuidor internacional": (9, 14),
}

MIN_ORDER_RULES = {
    "Fabricante nacional": [150, 250, 350],
    "Distribuidor nacional": [200, 300, 500],
    "Especializado / medical": [120, 240, 360],
    "Fabricante internacional": [400, 600, 800],
    "Distribuidor internacional": [500, 750, 1000],
}


# =============================================================================
# 4. CARGA DE DATOS
# =============================================================================

def load_dim_proveedor() -> pd.DataFrame:
    """Carga la dimensión proveedor base."""
    logger.info("Cargando dim_proveedor base...")
    df = pd.read_csv(INPUT_PROVIDER_FILE)

    required_cols = {"provider_id", "proveedor"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas obligatorias en dim_proveedor: {missing}")

    df["provider_id"] = normalize_text(df["provider_id"])
    df["proveedor"] = normalize_text(df["proveedor"], fallback="Desconocido")
    df = df.drop_duplicates(subset=["provider_id"]).copy()

    return df


# =============================================================================
# 5. LÓGICA PRINCIPAL
# =============================================================================

def apply_public_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica el mapa público de identificación y localización.
    """
    logger.info("Aplicando enriquecimiento público...")

    out = df.copy()
    out["provider_name_norm"] = out["proveedor"].map(normalize_provider_name)

    public_df = pd.DataFrame.from_dict(PUBLIC_PROVIDER_MAP, orient="index").reset_index()
    public_df = public_df.rename(columns={"index": "provider_name_norm"})

    out = out.merge(
        public_df,
        on="provider_name_norm",
        how="left",
        validate="one_to_one",
    )

    return out


def fill_public_fallbacks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rellena valores de respaldo cuando no se ha encontrado dato público.
    """
    logger.info("Aplicando reglas de respaldo para datos públicos...")

    out = df.copy()

    # País por defecto
    out["pais"] = normalize_text(out["pais"], fallback="España")

    # CCAA / provincia / ciudad
    for col in ["ccaa", "provincia", "ciudad"]:
        if col not in out.columns:
            out[col] = pd.NA

    # Si es internacional y faltan campos geográficos
    intl_mask = out["pais"].ne("España")

    out.loc[intl_mask & out["ccaa"].isna(), "ccaa"] = "No aplica"
    out.loc[intl_mask & out["provincia"].isna(), "provincia"] = "No disponible"
    out.loc[intl_mask & out["ciudad"].isna(), "ciudad"] = "No disponible"

    # Si es España y faltan datos geográficos
    out.loc[~intl_mask & out["ccaa"].isna(), "ccaa"] = "No disponible"
    out.loc[~intl_mask & out["provincia"].isna(), "provincia"] = "No disponible"
    out.loc[~intl_mask & out["ciudad"].isna(), "ciudad"] = "No disponible"

    # Tipo de proveedor de respaldo
    out["tipo_proveedor"] = normalize_text(out["tipo_proveedor"])

    mask_tipo_missing = out["tipo_proveedor"].isna()

    out.loc[mask_tipo_missing & out["pais"].eq("España"), "tipo_proveedor"] = "Distribuidor nacional"
    out.loc[mask_tipo_missing & out["pais"].ne("España"), "tipo_proveedor"] = "Distribuidor internacional"

    # Ajustes heurísticos simples
    medical_mask = out["proveedor"].str.upper().str.contains("MEDICAL", na=False)
    out.loc[medical_mask, "tipo_proveedor"] = "Especializado / medical"

    return out


def simulate_operational_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simula lead time y pedido mínimo de forma determinista y coherente con el tipo.
    """
    logger.info("Simulando atributos operativos...")

    out = df.copy()

    lead_times = []
    min_orders = []

    for _, row in out.iterrows():
        provider_key = str(row["provider_id"])
        provider_type = str(row["tipo_proveedor"])

        lead_min, lead_max = LEAD_TIME_RULES.get(provider_type, (4, 7))
        lead_span = lead_max - lead_min + 1
        lead_value = lead_min + (stable_hash(provider_key) % lead_span)

        order_options = MIN_ORDER_RULES.get(provider_type, [200, 300, 500])
        min_order_value = pick_from_options(provider_key, order_options)

        lead_times.append(int(lead_value))
        min_orders.append(int(min_order_value))

    out["lead_time_dias_sim"] = lead_times
    out["pedido_minimo_sim"] = min_orders

    return out


def finalize_dim_proveedor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena y deja la dimensión final.
    """
    logger.info("Construyendo dim_proveedor enriquecida final...")

    out = df.copy()

    # Normalización final de textos
    for col in ["cif", "pais", "ccaa", "provincia", "ciudad", "tipo_proveedor"]:
        if col in out.columns:
            out[col] = normalize_text(out[col])

    final_cols = [
        "provider_id",
        "proveedor",
        "cif",
        "pais",
        "ccaa",
        "provincia",
        "ciudad",
        "tipo_proveedor",
        "lead_time_dias_sim",
        "pedido_minimo_sim",
    ]

    out = out[final_cols].drop_duplicates(subset=["provider_id"]).copy()
    out = out.sort_values("provider_id").reset_index(drop=True)

    return out


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye resumen de validación de la dimensión enriquecida.
    """
    summary = {
        "n_filas_dim_proveedor_enriquecida": int(len(df)),
        "duplicados_provider_id": int(df["provider_id"].duplicated().sum()),
        "cif_informados": int(df["cif"].notna().sum()),
        "pais_informados": int(df["pais"].notna().sum()),
        "ccaa_informadas": int(df["ccaa"].notna().sum()),
        "provincia_informada": int(df["provincia"].notna().sum()),
        "ciudad_informada": int(df["ciudad"].notna().sum()),
        "tipo_proveedor_informado": int(df["tipo_proveedor"].notna().sum()),
        "lead_time_sim_informado": int(df["lead_time_dias_sim"].notna().sum()),
        "pedido_minimo_sim_informado": int(df["pedido_minimo_sim"].notna().sum()),
        "n_paises_unicos": int(df["pais"].nunique(dropna=True)),
        "n_tipos_proveedor_unicos": int(df["tipo_proveedor"].nunique(dropna=True)),
    }

    return pd.DataFrame([summary])


# =============================================================================
# 6. EXPORTACIÓN / I/O
# =============================================================================

def export_outputs(df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    """Exporta la dimensión enriquecida y su resumen."""
    logger.info("Exportando resultados...")

    export_dataframe(df, OUT_PROVIDER_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_PROVIDER_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 7. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta el enriquecimiento de la dimensión proveedor."""
    logger.info("==== INICIO | Enriquecimiento de dim_proveedor ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    dim_proveedor = load_dim_proveedor()
    enriched = apply_public_enrichment(dim_proveedor)
    enriched = fill_public_fallbacks(enriched)
    enriched = simulate_operational_fields(enriched)
    enriched = finalize_dim_proveedor(enriched)

    summary_df = build_summary(enriched)
    export_outputs(enriched, summary_df)

    logger.info(
        "Dimensión enriquecida construida | filas=%s | países=%s | tipos=%s",
        len(enriched),
        enriched["pais"].nunique(dropna=True),
        enriched["tipo_proveedor"].nunique(dropna=True),
    )
    logger.info("==== FIN | Enriquecimiento de dim_proveedor ====")


if __name__ == "__main__":
    main()