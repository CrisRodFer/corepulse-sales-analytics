"""
===============================================================================
SCRIPT: 09_generar_sql_snowflake.py
===============================================================================
DESCRIPCIÓN
-----------
Genera los scripts SQL necesarios para cargar el modelo final en Snowflake
siguiendo una estrategia de CREATE TABLE + INSERT multi-row.

El script:
1. Lee las tablas finales del modelo desde data/processed.
2. Genera un script de CREATE TABLE para:
   - dim_categoria
   - dim_proveedor
   - dim_producto
   - dim_calendario
   - fact_ventas
3. Genera scripts de INSERT INTO multi-row:
   - uno por cada dimensión pequeña
   - varios bloques para la fact, para evitar INSERT gigantes

NOMBRE FINAL DE TABLAS EN SNOWFLAKE
-----------------------------------
- dim_categoria
- dim_proveedor
- dim_producto
- dim_calendario
- fact_ventas

INPUT ESPERADO
--------------
- data/processed/dim_categoria_enriquecida.csv
- data/processed/dim_proveedor_enriquecida.csv
- data/processed/dim_producto_final.xlsx
- data/processed/dim_calendario.csv
- data/processed/fact_ventas_final.csv

OUTPUT ESPERADO
---------------
Carpeta: sql/snowflake/
- 01_create_tables.sql
- 02_insert_dim_categoria.sql
- 03_insert_dim_proveedor.sql
- 04_insert_dim_producto.sql
- 05_insert_dim_calendario.sql
- 06_insert_fact_ventas_part_001.sql
- 07_insert_fact_ventas_part_002.sql
- ...
- 99_run_order.txt

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
SQL_DIR = ROOT_DIR / "sql" / "snowflake"

DIM_CATEGORIA_FILE = PROCESSED_DIR / "dim_categoria_enriquecida.csv"
DIM_PROVEEDOR_FILE = PROCESSED_DIR / "dim_proveedor_enriquecida.csv"
DIM_PRODUCTO_FILE = PROCESSED_DIR / "dim_producto_final.xlsx"
DIM_CALENDARIO_FILE = PROCESSED_DIR / "dim_calendario.csv"
FACT_FILE = PROCESSED_DIR / "fact_ventas_final.csv"

OUT_CREATE_FILE = SQL_DIR / "01_create_tables.sql"
OUT_DIM_CATEGORIA_FILE = SQL_DIR / "02_insert_dim_categoria.sql"
OUT_DIM_PROVEEDOR_FILE = SQL_DIR / "03_insert_dim_proveedor.sql"
OUT_DIM_PRODUCTO_FILE = SQL_DIR / "04_insert_dim_producto.sql"
OUT_DIM_CALENDARIO_FILE = SQL_DIR / "05_insert_dim_calendario.sql"
OUT_RUN_ORDER_FILE = SQL_DIR / "99_run_order.txt"

FACT_INSERT_PREFIX = "06_insert_fact_ventas_part_"

FACT_TABLE_NAME = "fact_ventas"
DIM_PRODUCTO_TABLE_NAME = "dim_producto"
DIM_CALENDARIO_TABLE_NAME = "dim_calendario"
DIM_CATEGORIA_TABLE_NAME = "dim_categoria"
DIM_PROVEEDOR_TABLE_NAME = "dim_proveedor"

FACT_CHUNK_SIZE = 500


# =============================================================================
# 1. IMPORTS + LOGGING
# =============================================================================

import logging
import math
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
    SQL_DIR.mkdir(parents=True, exist_ok=True)


def check_input_files() -> None:
    """Valida que existan los archivos de entrada."""
    required_files = [
        DIM_CATEGORIA_FILE,
        DIM_PROVEEDOR_FILE,
        DIM_PRODUCTO_FILE,
        DIM_CALENDARIO_FILE,
        FACT_FILE,
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan archivos de entrada:\n- " + "\n- ".join(missing)
        )


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


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carga todas las tablas finales."""
    logger.info("Cargando tablas finales...")
    dim_categoria = pd.read_csv(DIM_CATEGORIA_FILE)
    dim_proveedor = pd.read_csv(DIM_PROVEEDOR_FILE)
    dim_producto = pd.read_excel(DIM_PRODUCTO_FILE)
    dim_calendario = pd.read_csv(DIM_CALENDARIO_FILE)
    fact = pd.read_csv(FACT_FILE)

    return dim_categoria, dim_proveedor, dim_producto, dim_calendario, fact


def sql_escape_string(value: str) -> str:
    """Escapa comillas simples para SQL."""
    return value.replace("'", "''")


def to_sql_literal(value) -> str:
    """
    Convierte un valor Python/Pandas a literal SQL para Snowflake.
    """
    if pd.isna(value):
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    # Timestamp / fecha
    if isinstance(value, pd.Timestamp):
        if value.time() == pd.Timestamp(value.date()).time():
            return f"'{value.strftime('%Y-%m-%d')}'"
        return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"

    # Numéricos enteros
    if isinstance(value, int):
        return str(value)

    # Numéricos float
    if isinstance(value, float):
        if math.isnan(value):
            return "NULL"
        return repr(value)

    # Strings
    text = str(value)
    return f"'{sql_escape_string(text)}'"


def build_insert_sql(
    df: pd.DataFrame,
    table_name: str,
) -> str:
    """
    Genera un INSERT multi-row para un DataFrame completo.
    """
    columns = list(df.columns)
    col_sql = ", ".join(columns)

    values_rows = []
    for _, row in df.iterrows():
        literals = [to_sql_literal(row[col]) for col in columns]
        values_rows.append(f"({', '.join(literals)})")

    sql = (
        f"INSERT INTO {table_name} ({col_sql}) VALUES\n"
        + ",\n".join(values_rows)
        + ";\n"
    )
    return sql


def write_text_file(path: Path, content: str) -> None:
    """Escribe un archivo de texto UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# =============================================================================
# 3. PREPARACIÓN DE DATOS
# =============================================================================

def prepare_dim_categoria(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    text_cols = ["category_id", "categoria", "familia_categoria", "formato_categoria"]
    for col in text_cols:
        out[col] = normalize_text(out[col])
    out["orden_categoria"] = pd.to_numeric(out["orden_categoria"], errors="coerce").astype("Int64")
    return out


def prepare_dim_proveedor(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    text_cols = [
        "provider_id", "proveedor", "cif", "pais", "ccaa",
        "provincia", "ciudad", "tipo_proveedor"
    ]
    for col in text_cols:
        out[col] = normalize_text(out[col])
    out["lead_time_dias_sim"] = pd.to_numeric(out["lead_time_dias_sim"], errors="coerce").astype("Int64")
    out["pedido_minimo_sim"] = pd.to_numeric(out["pedido_minimo_sim"], errors="coerce").astype("Int64")
    return out


def prepare_dim_producto(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["product_id"] = pd.to_numeric(out["product_id"], errors="coerce").astype("Int64")
    out["category_id"] = normalize_text(out["category_id"])
    out["provider_id"] = normalize_text(out["provider_id"])
    out["nombre"] = normalize_text(out["nombre"])
    out["marca"] = normalize_text(out["marca"])
    out["uom"] = normalize_text(out["uom"])
    out["perfil_comportamiento"] = normalize_text(out["perfil_comportamiento"])

    # ean13 puede venir largo; mejor tratarlo como texto
    out["ean13"] = out["ean13"].astype("string")
    out["pack_size"] = pd.to_numeric(out["pack_size"], errors="coerce")
    out["cluster_final"] = pd.to_numeric(out["cluster_final"], errors="coerce").astype("Int64")
    out["unit_sale_price_reference"] = pd.to_numeric(out["unit_sale_price_reference"], errors="coerce")
    return out


def prepare_dim_calendario(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    int_cols = [
        "year_label", "week_number_business", "n_days_week",
        "week_start_key", "week_end_key", "quarter_start_num",
        "quarter_end_num", "month_start_num", "month_end_num",
        "year_month_key_start", "yearmonth_start", "yearmonth_start_num",
        "year_month_key_end", "yearmonth_end", "yearmonth_end_num",
        "campaign_priority",
    ]
    for col in int_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    date_cols = ["week_start_date", "week_end_date"]
    for col in date_cols:
        out[col] = pd.to_datetime(out[col], errors="coerce")

    bool_cols = [
        "is_partial_week", "crosses_month", "crosses_quarter",
        "is_first_week_of_year", "is_last_week_of_year",
        "is_black_friday_week", "is_cyber_monday_week", "is_navidad_week",
        "is_rebajas_invierno_week", "is_rebajas_verano_week",
        "is_san_valentin_week", "is_vuelta_al_cole_week", "is_agosto_week",
        "is_prime_day_week", "is_semana_santa_week", "is_campaign_week",
    ]
    for col in bool_cols:
        out[col] = out[col].astype("boolean")

    text_cols = [
        "year_week_key", "week_label", "quarter_start_label",
        "quarter_end_label", "month_start_name", "month_start_short_name",
        "month_end_name", "month_end_short_name", "year_month_label_start",
        "yearmonth_start_text", "year_month_label_end", "yearmonth_end_text",
        "campaign_name_primary", "campaign_group_primary",
    ]
    for col in text_cols:
        out[col] = normalize_text(out[col])

    return out


def prepare_fact(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["product_id"] = pd.to_numeric(out["product_id"], errors="coerce").astype("Int64")
    out["category_id"] = normalize_text(out["category_id"])
    out["provider_id"] = normalize_text(out["provider_id"])
    out["year_week_key"] = normalize_text(out["year_week_key"])

    num_cols = [c for c in out.columns if c not in ["category_id", "provider_id", "year_week_key"]]
    for col in num_cols:
        if col != "product_id":
            out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


# =============================================================================
# 4. CREATE TABLES
# =============================================================================

def build_create_tables_sql() -> str:
    """Genera el SQL de CREATE TABLE."""
    sql = f"""
CREATE OR REPLACE TABLE {DIM_CATEGORIA_TABLE_NAME} (
    category_id VARCHAR PRIMARY KEY,
    categoria VARCHAR,
    familia_categoria VARCHAR,
    orden_categoria NUMBER(10,0),
    formato_categoria VARCHAR
);

CREATE OR REPLACE TABLE {DIM_PROVEEDOR_TABLE_NAME} (
    provider_id VARCHAR PRIMARY KEY,
    proveedor VARCHAR,
    cif VARCHAR,
    pais VARCHAR,
    ccaa VARCHAR,
    provincia VARCHAR,
    ciudad VARCHAR,
    tipo_proveedor VARCHAR,
    lead_time_dias_sim NUMBER(10,0),
    pedido_minimo_sim NUMBER(18,2)
);

CREATE OR REPLACE TABLE {DIM_PRODUCTO_TABLE_NAME} (
    product_id NUMBER(18,0) PRIMARY KEY,
    category_id VARCHAR,
    provider_id VARCHAR,
    nombre VARCHAR,
    marca VARCHAR,
    ean13 VARCHAR,
    pack_size FLOAT,
    uom VARCHAR,
    cluster_final NUMBER(10,0),
    perfil_comportamiento VARCHAR,
    unit_sale_price_reference NUMBER(18,4),
    CONSTRAINT fk_dim_producto_categoria
        FOREIGN KEY (category_id) REFERENCES {DIM_CATEGORIA_TABLE_NAME}(category_id),
    CONSTRAINT fk_dim_producto_proveedor
        FOREIGN KEY (provider_id) REFERENCES {DIM_PROVEEDOR_TABLE_NAME}(provider_id)
);

CREATE OR REPLACE TABLE {DIM_CALENDARIO_TABLE_NAME} (
    year_week_key VARCHAR PRIMARY KEY,
    year_label NUMBER(10,0),
    week_number_business NUMBER(10,0),
    week_start_date DATE,
    week_end_date DATE,
    week_label VARCHAR,
    n_days_week NUMBER(10,0),
    is_partial_week BOOLEAN,
    week_start_key NUMBER(10,0),
    week_end_key NUMBER(10,0),
    quarter_start_num NUMBER(10,0),
    quarter_start_label VARCHAR,
    quarter_end_num NUMBER(10,0),
    quarter_end_label VARCHAR,
    month_start_num NUMBER(10,0),
    month_start_name VARCHAR,
    month_start_short_name VARCHAR,
    month_end_num NUMBER(10,0),
    month_end_name VARCHAR,
    month_end_short_name VARCHAR,
    crosses_month BOOLEAN,
    crosses_quarter BOOLEAN,
    year_month_key_start NUMBER(10,0),
    year_month_label_start VARCHAR,
    yearmonth_start NUMBER(10,0),
    yearmonth_start_num NUMBER(10,0),
    yearmonth_start_text VARCHAR,
    year_month_key_end NUMBER(10,0),
    year_month_label_end VARCHAR,
    yearmonth_end NUMBER(10,0),
    yearmonth_end_num NUMBER(10,0),
    yearmonth_end_text VARCHAR,
    is_first_week_of_year BOOLEAN,
    is_last_week_of_year BOOLEAN,
    is_black_friday_week BOOLEAN,
    is_cyber_monday_week BOOLEAN,
    is_navidad_week BOOLEAN,
    is_rebajas_invierno_week BOOLEAN,
    is_rebajas_verano_week BOOLEAN,
    is_san_valentin_week BOOLEAN,
    is_vuelta_al_cole_week BOOLEAN,
    is_agosto_week BOOLEAN,
    is_prime_day_week BOOLEAN,
    is_semana_santa_week BOOLEAN,
    is_campaign_week BOOLEAN,
    campaign_name_primary VARCHAR,
    campaign_group_primary VARCHAR,
    campaign_priority NUMBER(10,0)
);

CREATE OR REPLACE TABLE {FACT_TABLE_NAME} (
    product_id NUMBER(18,0),
    category_id VARCHAR,
    provider_id VARCHAR,
    year_week_key VARCHAR,
    unit_sale_price_reference NUMBER(18,4),
    sales_units FLOAT,
    forecast_base_units FLOAT,
    forecast_optimista_units FLOAT,
    forecast_pesimista_units FLOAT,
    sales_value_estimated NUMBER(18,4),
    forecast_base_value_estimated NUMBER(18,4),
    forecast_optimista_value_estimated NUMBER(18,4),
    forecast_pesimista_value_estimated NUMBER(18,4),
    sales_units_adjusted FLOAT,
    forecast_base_units_adjusted FLOAT,
    forecast_optimista_units_adjusted FLOAT,
    forecast_pesimista_units_adjusted FLOAT,
    sales_value_estimated_adjusted NUMBER(18,4),
    forecast_base_value_estimated_adjusted NUMBER(18,4),
    forecast_optimista_value_estimated_adjusted NUMBER(18,4),
    forecast_pesimista_value_estimated_adjusted NUMBER(18,4),
    CONSTRAINT fk_fact_producto
        FOREIGN KEY (product_id) REFERENCES {DIM_PRODUCTO_TABLE_NAME}(product_id),
    CONSTRAINT fk_fact_categoria
        FOREIGN KEY (category_id) REFERENCES {DIM_CATEGORIA_TABLE_NAME}(category_id),
    CONSTRAINT fk_fact_proveedor
        FOREIGN KEY (provider_id) REFERENCES {DIM_PROVEEDOR_TABLE_NAME}(provider_id),
    CONSTRAINT fk_fact_calendario
        FOREIGN KEY (year_week_key) REFERENCES {DIM_CALENDARIO_TABLE_NAME}(year_week_key)
);
""".strip()

    return sql + "\n"


# =============================================================================
# 5. INSERTS
# =============================================================================

def generate_fact_insert_files(fact: pd.DataFrame) -> list[Path]:
    """Genera varios archivos SQL de INSERT para la fact por bloques."""
    output_paths = []

    total_rows = len(fact)
    n_chunks = math.ceil(total_rows / FACT_CHUNK_SIZE)

    logger.info("Generando INSERTs de fact en %s bloques...", n_chunks)

    for i in range(n_chunks):
        start = i * FACT_CHUNK_SIZE
        end = min((i + 1) * FACT_CHUNK_SIZE, total_rows)
        chunk = fact.iloc[start:end].copy()

        sql = build_insert_sql(chunk, FACT_TABLE_NAME)
        out_path = SQL_DIR / f"{FACT_INSERT_PREFIX}{i+1:03d}.sql"
        write_text_file(out_path, sql)
        output_paths.append(out_path)

    return output_paths


def generate_run_order_file(fact_files: list[Path]) -> None:
    """Genera un archivo con el orden recomendado de ejecución."""
    lines = [
        "Orden recomendado de ejecución en Snowflake:",
        "",
        OUT_CREATE_FILE.name,
        OUT_DIM_CATEGORIA_FILE.name,
        OUT_DIM_PROVEEDOR_FILE.name,
        OUT_DIM_PRODUCTO_FILE.name,
        OUT_DIM_CALENDARIO_FILE.name,
    ]
    lines.extend([p.name for p in fact_files])

    write_text_file(OUT_RUN_ORDER_FILE, "\n".join(lines) + "\n")


# =============================================================================
# 6. MAIN
# =============================================================================

def main() -> None:
    """Ejecuta la generación de SQL para Snowflake."""
    logger.info("==== INICIO | Generación SQL Snowflake ====")

    ensure_directories()
    check_input_files()

    (
        dim_categoria,
        dim_proveedor,
        dim_producto,
        dim_calendario,
        fact,
    ) = read_inputs()

    dim_categoria = prepare_dim_categoria(dim_categoria)
    dim_proveedor = prepare_dim_proveedor(dim_proveedor)
    dim_producto = prepare_dim_producto(dim_producto)
    dim_calendario = prepare_dim_calendario(dim_calendario)
    fact = prepare_fact(fact)

    # CREATE TABLES
    create_sql = build_create_tables_sql()
    write_text_file(OUT_CREATE_FILE, create_sql)

    # INSERTS dimensiones
    write_text_file(
        OUT_DIM_CATEGORIA_FILE,
        build_insert_sql(dim_categoria, DIM_CATEGORIA_TABLE_NAME),
    )
    write_text_file(
        OUT_DIM_PROVEEDOR_FILE,
        build_insert_sql(dim_proveedor, DIM_PROVEEDOR_TABLE_NAME),
    )
    write_text_file(
        OUT_DIM_PRODUCTO_FILE,
        build_insert_sql(dim_producto, DIM_PRODUCTO_TABLE_NAME),
    )
    write_text_file(
        OUT_DIM_CALENDARIO_FILE,
        build_insert_sql(dim_calendario, DIM_CALENDARIO_TABLE_NAME),
    )

    # INSERTS fact
    fact_files = generate_fact_insert_files(fact)

    # Run order
    generate_run_order_file(fact_files)

    logger.info("SQL generado en: %s", SQL_DIR)
    logger.info("==== FIN | Generación SQL Snowflake ====")


if __name__ == "__main__":
    main()