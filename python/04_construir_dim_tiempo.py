

"""
===============================================================================
SCRIPT: 04_construir_dim_tiempo.py
===============================================================================
DESCRIPCIÓN
-----------
Construye la dimensión temporal final del dashboard a partir de la fact base
semanal ya validada.

En el modelo final se utilizará una única dimensión temporal llamada
`dim_calendario`, con granularidad semanal, para mantener una estructura
estrella limpia y compatible con la fact.

Granularidad:
    1 fila = 1 semana de negocio

La dimensión incluye:
- claves y fechas semanales
- atributos de año, mes y trimestre
- YearMonth
- flags de semanas parciales
- flags de campañas
- campaña principal por semana

INPUT ESPERADO
--------------
- data/processed/fact_base_semanal.csv

OUTPUT ESPERADO
---------------
- data/processed/dim_calendario.csv
- data/processed/resumen_dim_calendario.csv

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

FACT_FILE = PROCESSED_DIR / "fact_base_semanal.csv"

OUT_CALENDAR_FILE = PROCESSED_DIR / "dim_calendario.csv"
OUT_SUMMARY_FILE = PROCESSED_DIR / "resumen_dim_calendario.csv"


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

MONTH_NAME_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

MONTH_SHORT_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def ensure_directories() -> None:
    """Crea carpetas de salida si no existen."""
    for path in [PROCESSED_DIR, OUTPUTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def check_input_files() -> None:
    """Valida que exista la fact base."""
    if not FACT_FILE.exists():
        raise FileNotFoundError(f"No se encuentra el archivo de entrada: {FACT_FILE}")


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


def get_black_friday_date(year: int) -> pd.Timestamp:
    """Último viernes de noviembre."""
    november_dates = pd.date_range(f"{year}-11-01", f"{year}-11-30", freq="D")
    fridays = november_dates[november_dates.weekday == 4]
    return fridays.max()


def get_cyber_monday_date(year: int) -> pd.Timestamp:
    """Lunes posterior a Black Friday."""
    return get_black_friday_date(year) + pd.Timedelta(days=3)


def overlap_period(
    start_series: pd.Series,
    end_series: pd.Series,
    period_start: pd.Series,
    period_end: pd.Series,
) -> pd.Series:
    """Devuelve True si [start, end] solapa con [period_start, period_end]."""
    return (pd.to_datetime(start_series) <= pd.to_datetime(period_end)) & (
        pd.to_datetime(end_series) >= pd.to_datetime(period_start)
    )


# =============================================================================
# 3. CARGA DE DATOS
# =============================================================================

def load_fact() -> pd.DataFrame:
    """Carga la fact base semanal."""
    logger.info("Cargando fact base semanal...")
    df = pd.read_csv(
        FACT_FILE,
        parse_dates=["week_start_date", "week_end_date"],
    )

    required_cols = {
        "year_week_key",
        "year_label",
        "week_number_business",
        "week_start_date",
        "week_end_date",
        "week_label",
        "n_days_week",
        "is_partial_week",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Faltan columnas obligatorias en la fact: {missing}")

    return df


# =============================================================================
# 4. CONSTRUCCIÓN DE DIM_CALENDARIO SEMANAL
# =============================================================================

def build_dim_calendario(fact: pd.DataFrame) -> pd.DataFrame:
    """Construye la dimensión temporal final con grano semanal."""
    logger.info("Construyendo dim_calendario semanal...")

    dim = (
        fact[
            [
                "year_week_key",
                "year_label",
                "week_number_business",
                "week_start_date",
                "week_end_date",
                "week_label",
                "n_days_week",
                "is_partial_week",
            ]
        ]
        .drop_duplicates()
        .sort_values(["year_label", "week_start_date"])
        .reset_index(drop=True)
    )

    # -------------------------------------------------------------------------
    # CLAVES Y ATRIBUTOS TEMPORALES
    # -------------------------------------------------------------------------
    dim["week_start_key"] = dim["week_start_date"].dt.strftime("%Y%m%d")
    dim["week_end_key"] = dim["week_end_date"].dt.strftime("%Y%m%d")

    dim["quarter_start_num"] = dim["week_start_date"].dt.quarter
    dim["quarter_start_label"] = "Q" + dim["quarter_start_num"].astype(str)
    dim["quarter_end_num"] = dim["week_end_date"].dt.quarter
    dim["quarter_end_label"] = "Q" + dim["quarter_end_num"].astype(str)

    dim["month_start_num"] = dim["week_start_date"].dt.month
    dim["month_start_name"] = dim["month_start_num"].map(MONTH_NAME_ES)
    dim["month_start_short_name"] = dim["month_start_num"].map(MONTH_SHORT_ES)

    dim["month_end_num"] = dim["week_end_date"].dt.month
    dim["month_end_name"] = dim["month_end_num"].map(MONTH_NAME_ES)
    dim["month_end_short_name"] = dim["month_end_num"].map(MONTH_SHORT_ES)

    dim["crosses_month"] = dim["month_start_num"] != dim["month_end_num"]
    dim["crosses_quarter"] = dim["quarter_start_num"] != dim["quarter_end_num"]

    # YearMonth inicio
    dim["year_month_key_start"] = dim["week_start_date"].dt.strftime("%Y%m")
    dim["year_month_label_start"] = (
        dim["week_start_date"].dt.year.astype(str)
        + "-"
        + dim["month_start_short_name"]
    )
    dim["yearmonth_start"] = dim["week_start_date"].dt.strftime("%Y%m")
    dim["yearmonth_start_num"] = dim["yearmonth_start"].astype(int)
    dim["yearmonth_start_text"] = dim["year_month_label_start"]

    # YearMonth fin
    dim["year_month_key_end"] = dim["week_end_date"].dt.strftime("%Y%m")
    dim["year_month_label_end"] = (
        dim["week_end_date"].dt.year.astype(str)
        + "-"
        + dim["month_end_short_name"]
    )
    dim["yearmonth_end"] = dim["week_end_date"].dt.strftime("%Y%m")
    dim["yearmonth_end_num"] = dim["yearmonth_end"].astype(int)
    dim["yearmonth_end_text"] = dim["year_month_label_end"]

    min_week_by_year = dim.groupby("year_label")["week_number_business"].transform("min")
    max_week_by_year = dim.groupby("year_label")["week_number_business"].transform("max")

    dim["is_first_week_of_year"] = dim["week_number_business"] == min_week_by_year
    dim["is_last_week_of_year"] = dim["week_number_business"] == max_week_by_year

    # -------------------------------------------------------------------------
    # FLAGS DE CAMPAÑA
    # -------------------------------------------------------------------------
    year_str = dim["year_label"].astype(int).astype(str)

    bf_dates = {
        int(year): get_black_friday_date(int(year))
        for year in sorted(dim["year_label"].dropna().unique())
    }
    cm_dates = {
        int(year): get_cyber_monday_date(int(year))
        for year in sorted(dim["year_label"].dropna().unique())
    }

    dim["black_friday_date"] = dim["year_label"].astype(int).map(bf_dates)
    dim["cyber_monday_date"] = dim["year_label"].astype(int).map(cm_dates)

    dim["is_black_friday_week"] = (
        (dim["week_start_date"] <= dim["black_friday_date"])
        & (dim["week_end_date"] >= dim["black_friday_date"])
    )

    dim["is_cyber_monday_week"] = (
        (dim["week_start_date"] <= dim["cyber_monday_date"])
        & (dim["week_end_date"] >= dim["cyber_monday_date"])
    )

    navidad_start = pd.to_datetime(year_str + "-12-15")
    navidad_end = pd.to_datetime(year_str + "-12-31")
    dim["is_navidad_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], navidad_start, navidad_end
    )

    rebajas_inv_start = pd.to_datetime(year_str + "-01-01")
    rebajas_inv_end = pd.to_datetime(year_str + "-01-15")
    dim["is_rebajas_invierno_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], rebajas_inv_start, rebajas_inv_end
    )

    rebajas_ver_start = pd.to_datetime(year_str + "-07-01")
    rebajas_ver_end = pd.to_datetime(year_str + "-07-15")
    dim["is_rebajas_verano_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], rebajas_ver_start, rebajas_ver_end
    )

    san_valentin_start = pd.to_datetime(year_str + "-02-10")
    san_valentin_end = pd.to_datetime(year_str + "-02-14")
    dim["is_san_valentin_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], san_valentin_start, san_valentin_end
    )

    vuelta_cole_start = pd.to_datetime(year_str + "-09-01")
    vuelta_cole_end = pd.to_datetime(year_str + "-09-15")
    dim["is_vuelta_al_cole_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], vuelta_cole_start, vuelta_cole_end
    )

    agosto_start = pd.to_datetime(year_str + "-08-01")
    agosto_end = pd.to_datetime(year_str + "-08-31")
    dim["is_agosto_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], agosto_start, agosto_end
    )

    prime_day_start = pd.to_datetime(year_str + "-07-08")
    prime_day_end = pd.to_datetime(year_str + "-07-14")
    dim["is_prime_day_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], prime_day_start, prime_day_end
    )

    easter_start_map = {
        2024: pd.Timestamp("2024-03-24"),
        2025: pd.Timestamp("2025-04-13"),
        2026: pd.Timestamp("2026-03-29"),
    }
    easter_end_map = {
        2024: pd.Timestamp("2024-03-31"),
        2025: pd.Timestamp("2025-04-20"),
        2026: pd.Timestamp("2026-04-05"),
    }

    dim["semana_santa_start"] = dim["year_label"].astype(int).map(easter_start_map)
    dim["semana_santa_end"] = dim["year_label"].astype(int).map(easter_end_map)

    dim["is_semana_santa_week"] = overlap_period(
        dim["week_start_date"], dim["week_end_date"], dim["semana_santa_start"], dim["semana_santa_end"]
    )

    campaign_flags = [
        "is_black_friday_week",
        "is_cyber_monday_week",
        "is_navidad_week",
        "is_rebajas_invierno_week",
        "is_rebajas_verano_week",
        "is_san_valentin_week",
        "is_vuelta_al_cole_week",
        "is_agosto_week",
        "is_prime_day_week",
        "is_semana_santa_week",
    ]
    dim["is_campaign_week"] = dim[campaign_flags].any(axis=1)

    # -------------------------------------------------------------------------
    # CAMPAÑA PRINCIPAL POR PRIORIDAD
    # -------------------------------------------------------------------------
    dim["campaign_name_primary"] = "No campaña"
    dim["campaign_group_primary"] = "No campaña"
    dim["campaign_priority"] = 999

    campaign_priority_rules = [
        ("is_black_friday_week", "Black Friday", "Promoción comercial", 1),
        ("is_cyber_monday_week", "Cyber Monday", "Promoción comercial", 2),
        ("is_navidad_week", "Navidad", "Campaña estacional", 3),
        ("is_rebajas_invierno_week", "Rebajas Invierno", "Promoción comercial", 4),
        ("is_rebajas_verano_week", "Rebajas Verano", "Promoción comercial", 5),
        ("is_prime_day_week", "Prime Day", "Promoción comercial", 6),
        ("is_semana_santa_week", "Semana Santa", "Campaña estacional", 7),
        ("is_vuelta_al_cole_week", "Vuelta al cole", "Campaña estacional", 8),
        ("is_san_valentin_week", "San Valentín", "Campaña estacional", 9),
        ("is_agosto_week", "Agosto", "Estacionalidad", 10),
    ]

    for flag_col, campaign_name, campaign_group, priority in campaign_priority_rules:
        mask = dim[flag_col] & (dim["campaign_priority"] > priority)
        dim.loc[mask, "campaign_name_primary"] = campaign_name
        dim.loc[mask, "campaign_group_primary"] = campaign_group
        dim.loc[mask, "campaign_priority"] = priority

    # Limpieza final
    dim = dim.drop(
        columns=[
            "black_friday_date",
            "cyber_monday_date",
            "semana_santa_start",
            "semana_santa_end",
        ]
    )

    dim = dim.sort_values(["year_label", "week_start_date"]).reset_index(drop=True)
    return dim


def build_summary(dim_calendario: pd.DataFrame) -> pd.DataFrame:
    """Construye un resumen simple de validación."""
    summary = {
        "n_filas_dim_calendario": int(len(dim_calendario)),
        "n_anios": int(dim_calendario["year_label"].nunique(dropna=True)),
        "n_semanas_parciales": int(dim_calendario["is_partial_week"].sum()),
        "duplicados_year_week_key": int(dim_calendario["year_week_key"].duplicated().sum()),
        "campaign_weeks_total": int(dim_calendario["is_campaign_week"].sum()),
        "black_friday_weeks": int(dim_calendario["is_black_friday_week"].sum()),
        "cyber_monday_weeks": int(dim_calendario["is_cyber_monday_week"].sum()),
        "navidad_weeks": int(dim_calendario["is_navidad_week"].sum()),
        "rebajas_invierno_weeks": int(dim_calendario["is_rebajas_invierno_week"].sum()),
        "rebajas_verano_weeks": int(dim_calendario["is_rebajas_verano_week"].sum()),
        "san_valentin_weeks": int(dim_calendario["is_san_valentin_week"].sum()),
        "vuelta_al_cole_weeks": int(dim_calendario["is_vuelta_al_cole_week"].sum()),
        "agosto_weeks": int(dim_calendario["is_agosto_week"].sum()),
        "prime_day_weeks": int(dim_calendario["is_prime_day_week"].sum()),
        "semana_santa_weeks": int(dim_calendario["is_semana_santa_week"].sum()),
        "campaign_names_primary_unicas": int(dim_calendario["campaign_name_primary"].nunique(dropna=True)),
    }

    return pd.DataFrame([summary])


# =============================================================================
# 5. EXPORTACIÓN / I/O
# =============================================================================

def export_outputs(dim_calendario: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    """Exporta la dimensión calendario final y su resumen."""
    logger.info("Exportando dimensión calendario final...")

    export_dataframe(dim_calendario, OUT_CALENDAR_FILE)
    export_dataframe(summary_df, OUT_SUMMARY_FILE)

    logger.info("Archivo exportado: %s", OUT_CALENDAR_FILE.name)
    logger.info("Archivo exportado: %s", OUT_SUMMARY_FILE.name)


# =============================================================================
# 6. CLI / MAIN
# =============================================================================

def main() -> None:
    """Ejecuta la construcción de la dimensión calendario final."""
    logger.info("==== INICIO | Construcción de dim_calendario semanal ====")
    logger.info("ROOT_DIR detectado: %s", ROOT_DIR)

    ensure_directories()
    check_input_files()

    fact = load_fact()
    dim_calendario = build_dim_calendario(fact)
    summary_df = build_summary(dim_calendario)

    export_outputs(dim_calendario, summary_df)

    logger.info(
        "Dimensión calendario construida | filas=%s | años=%s | semanas parciales=%s",
        len(dim_calendario),
        dim_calendario["year_label"].nunique(dropna=True),
        int(dim_calendario["is_partial_week"].sum()),
    )
    logger.info("==== FIN | Construcción de dim_calendario semanal ====")


if __name__ == "__main__":
    main()