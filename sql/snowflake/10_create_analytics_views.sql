
-- ============================================================
-- SCRIPT: 10_create_analytics_views.sql
-- PROYECTO: Corepulse Sales Analytics
-- DESCRIPCIÓN:
--   Crea la capa analítica del modelo en Snowflake mediante vistas
--   reutilizables para rankings, comparativas anuales y análisis YoY.
--
-- DEPENDENCIAS:
--   - fact_ventas
--   - dim_producto
--   - dim_categoria
--   - dim_proveedor
--   - dim_calendario
--
-- VISTAS CREADAS:
--   1. vw_ventas_base
--   2. vw_ranking_productos_anual_escenario
--   3. vw_ranking_proveedores_anual_escenario
--   4. vw_comparativa_ranking_productos_anual
--   5. vw_comparativa_ranking_proveedores_anual
--   6. vw_ventas_yoy_producto_semana
--   7. vw_ventas_yoy_categoria_semana
-- ============================================================

CREATE OR REPLACE VIEW vw_ventas_base AS
SELECT
    f.product_id,
    f.category_id,
    f.provider_id,
    f.year_week_key,

    p.nombre,
    p.marca,
    p.cluster_final,
    p.perfil_comportamiento,
    p.unit_sale_price_reference,

    c.categoria,
    c.familia_categoria,
    c.formato_categoria,

    pr.proveedor,
    pr.pais,
    pr.ccaa,
    pr.tipo_proveedor,
    pr.lead_time_dias_sim,
    pr.pedido_minimo_sim,

    cal.year_label,
    cal.week_number_business,
    cal.week_start_date,
    cal.week_end_date,
    cal.week_label,
    cal.month_start_name,
    cal.quarter_start_label,
    cal.is_partial_week,
    cal.is_campaign_week,
    cal.campaign_name_primary,
    cal.campaign_group_primary,

    f.sales_units,
    f.forecast_base_units,
    f.forecast_optimista_units,
    f.forecast_pesimista_units,
    f.sales_value_estimated,
    f.forecast_base_value_estimated,
    f.forecast_optimista_value_estimated,
    f.forecast_pesimista_value_estimated,
    f.sales_units_adjusted,
    f.forecast_base_units_adjusted,
    f.forecast_optimista_units_adjusted,
    f.forecast_pesimista_units_adjusted,
    f.sales_value_estimated_adjusted,
    f.forecast_base_value_estimated_adjusted,
    f.forecast_optimista_value_estimated_adjusted,
    f.forecast_pesimista_value_estimated_adjusted

FROM fact_ventas f
LEFT JOIN dim_producto p
    ON f.product_id = p.product_id
LEFT JOIN dim_categoria c
    ON f.category_id = c.category_id
LEFT JOIN dim_proveedor pr
    ON f.provider_id = pr.provider_id
LEFT JOIN dim_calendario cal
    ON f.year_week_key = cal.year_week_key;

SELECT * FROM VW_VENTAS_BASE



CREATE OR REPLACE VIEW vw_ranking_productos_anual_escenario AS

WITH metricas_producto_anual AS (

    -- Ventas reales 2024 y 2025
    SELECT
        year_label,
        'Real' AS escenario,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor,
        SUM(sales_units) AS units_value,
        SUM(sales_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label IN (2024, 2025)
    GROUP BY
        year_label,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor

    UNION ALL

    -- Forecast 2026: escenario base
    SELECT
        year_label,
        'Forecast base' AS escenario,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor,
        SUM(forecast_base_units) AS units_value,
        SUM(forecast_base_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor

    UNION ALL

    -- Forecast 2026: escenario optimista
    SELECT
        year_label,
        'Forecast optimista' AS escenario,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor,
        SUM(forecast_optimista_units) AS units_value,
        SUM(forecast_optimista_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor

    UNION ALL

    -- Forecast 2026: escenario pesimista
    SELECT
        year_label,
        'Forecast pesimista' AS escenario,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor,
        SUM(forecast_pesimista_units) AS units_value,
        SUM(forecast_pesimista_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        product_id,
        nombre,
        marca,
        categoria,
        proveedor
),

ranking AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY year_label, escenario
            ORDER BY sales_value DESC
        ) AS ranking_producto,

        sales_value
        / NULLIF(
            SUM(sales_value) OVER (
                PARTITION BY year_label, escenario
            ),
            0
        ) AS pct_contribucion,

        SUM(sales_value) OVER (
            PARTITION BY year_label, escenario
            ORDER BY sales_value DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
        / NULLIF(
            SUM(sales_value) OVER (
                PARTITION BY year_label, escenario
            ),
            0
        ) AS pct_contribucion_acumulada

    FROM metricas_producto_anual
)

SELECT *
FROM ranking;

SELECT * FROM vw_ranking_productos_anual_escenario LIMIT 50;

CREATE OR REPLACE VIEW vw_ranking_proveedores_anual_escenario AS

WITH metricas_proveedor_anual AS (

    -- Ventas reales 2024 y 2025
    SELECT
        year_label,
        'Real' AS escenario,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim,
        COUNT(DISTINCT product_id) AS n_productos,
        SUM(sales_units) AS units_value,
        SUM(sales_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label IN (2024, 2025)
    GROUP BY
        year_label,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim

    UNION ALL

    -- Forecast 2026: escenario base
    SELECT
        year_label,
        'Forecast base' AS escenario,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim,
        COUNT(DISTINCT product_id) AS n_productos,
        SUM(forecast_base_units) AS units_value,
        SUM(forecast_base_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim

    UNION ALL

    -- Forecast 2026: escenario optimista
    SELECT
        year_label,
        'Forecast optimista' AS escenario,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim,
        COUNT(DISTINCT product_id) AS n_productos,
        SUM(forecast_optimista_units) AS units_value,
        SUM(forecast_optimista_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim

    UNION ALL

    -- Forecast 2026: escenario pesimista
    SELECT
        year_label,
        'Forecast pesimista' AS escenario,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim,
        COUNT(DISTINCT product_id) AS n_productos,
        SUM(forecast_pesimista_units) AS units_value,
        SUM(forecast_pesimista_value_estimated) AS sales_value
    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        provider_id,
        proveedor,
        pais,
        ccaa,
        tipo_proveedor,
        lead_time_dias_sim,
        pedido_minimo_sim
),

ranking AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY year_label, escenario
            ORDER BY sales_value DESC
        ) AS ranking_proveedor,

        sales_value
        / NULLIF(
            SUM(sales_value) OVER (
                PARTITION BY year_label, escenario
            ),
            0
        ) AS pct_contribucion,

        SUM(sales_value) OVER (
            PARTITION BY year_label, escenario
            ORDER BY sales_value DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
        / NULLIF(
            SUM(sales_value) OVER (
                PARTITION BY year_label, escenario
            ),
            0
        ) AS pct_contribucion_acumulada

    FROM metricas_proveedor_anual
)

SELECT *
FROM ranking;

SELECT * FROM VW_RANKING_PROVEEDORES_ANUAL_ESCENARIO LIMIT 50;


CREATE OR REPLACE VIEW vw_comparativa_ranking_productos_anual AS

WITH ranking_base AS (
    SELECT *
    FROM vw_ranking_productos_anual_escenario
),

comparativa AS (
    SELECT
        actual.product_id,
        actual.nombre,
        actual.marca,
        actual.categoria,
        actual.proveedor,

        anterior.year_label AS year_anterior,
        actual.year_label AS year_actual,

        anterior.escenario AS escenario_anterior,
        actual.escenario AS escenario_actual,

        anterior.units_value AS units_value_anterior,
        actual.units_value AS units_value_actual,

        anterior.sales_value AS sales_value_anterior,
        actual.sales_value AS sales_value_actual,

        anterior.ranking_producto AS ranking_anterior,
        actual.ranking_producto AS ranking_actual,

        anterior.pct_contribucion AS pct_contribucion_anterior,
        actual.pct_contribucion AS pct_contribucion_actual,

        anterior.pct_contribucion_acumulada AS pct_contribucion_acumulada_anterior,
        actual.pct_contribucion_acumulada AS pct_contribucion_acumulada_actual

    FROM ranking_base actual
    LEFT JOIN ranking_base anterior
        ON actual.product_id = anterior.product_id
        AND actual.year_label = anterior.year_label + 1
        AND anterior.escenario = 'Real'

    WHERE actual.year_label IN (2025, 2026)
)

SELECT
    *,

    units_value_actual - units_value_anterior AS var_units_abs,

    (units_value_actual - units_value_anterior)
        / NULLIF(units_value_anterior, 0) AS var_units_pct,

    sales_value_actual - sales_value_anterior AS var_value_abs,

    (sales_value_actual - sales_value_anterior)
        / NULLIF(sales_value_anterior, 0) AS var_value_pct,

    ranking_actual - ranking_anterior AS variacion_ranking,

    pct_contribucion_actual - pct_contribucion_anterior AS var_pct_contribucion,

    CASE
        WHEN ranking_anterior IS NULL 
             AND ranking_actual IS NOT NULL
            THEN 'Nuevo en ranking'

        WHEN ranking_actual < ranking_anterior
            THEN 'Sube posiciones'

        WHEN ranking_actual > ranking_anterior
            THEN 'Baja posiciones'

        WHEN ranking_actual = ranking_anterior
            THEN 'Mantiene posición'

        ELSE 'Sin clasificar'
    END AS estado_ranking,

    CAST(year_anterior AS VARCHAR)
        || ' '
        || escenario_anterior
        || ' vs '
        || CAST(year_actual AS VARCHAR)
        || ' '
        || escenario_actual AS periodo_comparativo

FROM comparativa;

SELECT * FROM vw_comparativa_ranking_productos_anual LIMIT 50;

CREATE OR REPLACE VIEW vw_comparativa_ranking_proveedores_anual AS

WITH ranking_base AS (
    SELECT *
    FROM vw_ranking_proveedores_anual_escenario
),

comparativa AS (
    SELECT
        actual.provider_id,
        actual.proveedor,
        actual.pais,
        actual.ccaa,
        actual.tipo_proveedor,
        actual.lead_time_dias_sim,
        actual.pedido_minimo_sim,

        anterior.year_label AS year_anterior,
        actual.year_label AS year_actual,

        anterior.escenario AS escenario_anterior,
        actual.escenario AS escenario_actual,

        anterior.n_productos AS n_productos_anterior,
        actual.n_productos AS n_productos_actual,

        anterior.units_value AS units_value_anterior,
        actual.units_value AS units_value_actual,

        anterior.sales_value AS sales_value_anterior,
        actual.sales_value AS sales_value_actual,

        anterior.ranking_proveedor AS ranking_anterior,
        actual.ranking_proveedor AS ranking_actual,

        anterior.pct_contribucion AS pct_contribucion_anterior,
        actual.pct_contribucion AS pct_contribucion_actual,

        anterior.pct_contribucion_acumulada AS pct_contribucion_acumulada_anterior,
        actual.pct_contribucion_acumulada AS pct_contribucion_acumulada_actual

    FROM ranking_base actual
    LEFT JOIN ranking_base anterior
        ON actual.provider_id = anterior.provider_id
        AND actual.year_label = anterior.year_label + 1
        AND anterior.escenario = 'Real'

    WHERE actual.year_label IN (2025, 2026)
)

SELECT
    *,

    n_productos_actual - n_productos_anterior AS var_n_productos_abs,

    units_value_actual - units_value_anterior AS var_units_abs,

    (units_value_actual - units_value_anterior)
        / NULLIF(units_value_anterior, 0) AS var_units_pct,

    sales_value_actual - sales_value_anterior AS var_value_abs,

    (sales_value_actual - sales_value_anterior)
        / NULLIF(sales_value_anterior, 0) AS var_value_pct,

    ranking_actual - ranking_anterior AS variacion_ranking,

    pct_contribucion_actual - pct_contribucion_anterior AS var_pct_contribucion,

    CASE
        WHEN ranking_anterior IS NULL 
             AND ranking_actual IS NOT NULL
            THEN 'Nuevo en ranking'

        WHEN ranking_actual < ranking_anterior
            THEN 'Sube posiciones'

        WHEN ranking_actual > ranking_anterior
            THEN 'Baja posiciones'

        WHEN ranking_actual = ranking_anterior
            THEN 'Mantiene posición'

        ELSE 'Sin clasificar'
    END AS estado_ranking,

    CAST(year_anterior AS VARCHAR)
        || ' '
        || escenario_anterior
        || ' vs '
        || CAST(year_actual AS VARCHAR)
        || ' '
        || escenario_actual AS periodo_comparativo

FROM comparativa;

SELECT * FROM VW_COMPARATIVA_RANKING_PROVEEDORES_ANUAL LIMIT 50;

CREATE OR REPLACE VIEW vw_ventas_yoy_producto_semana AS

WITH metricas_producto_semana AS (

    -- Ventas reales 2024 y 2025
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Real' AS escenario,

        product_id,
        nombre,
        marca,
        categoria,
        proveedor,

        sales_units AS units_value,
        sales_value_estimated AS sales_value,

        sales_units_adjusted AS units_value_adjusted,
        sales_value_estimated_adjusted AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label IN (2024, 2025)

    UNION ALL

    -- Forecast 2026: escenario base
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Forecast base' AS escenario,

        product_id,
        nombre,
        marca,
        categoria,
        proveedor,

        forecast_base_units AS units_value,
        forecast_base_value_estimated AS sales_value,

        forecast_base_units_adjusted AS units_value_adjusted,
        forecast_base_value_estimated_adjusted AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label = 2026

    UNION ALL

    -- Forecast 2026: escenario optimista
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Forecast optimista' AS escenario,

        product_id,
        nombre,
        marca,
        categoria,
        proveedor,

        forecast_optimista_units AS units_value,
        forecast_optimista_value_estimated AS sales_value,

        forecast_optimista_units_adjusted AS units_value_adjusted,
        forecast_optimista_value_estimated_adjusted AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label = 2026

    UNION ALL

    -- Forecast 2026: escenario pesimista
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Forecast pesimista' AS escenario,

        product_id,
        nombre,
        marca,
        categoria,
        proveedor,

        forecast_pesimista_units AS units_value,
        forecast_pesimista_value_estimated AS sales_value,

        forecast_pesimista_units_adjusted AS units_value_adjusted,
        forecast_pesimista_value_estimated_adjusted AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label = 2026
),

comparativa AS (
    SELECT
        actual.product_id,
        actual.nombre,
        actual.marca,
        actual.categoria,
        actual.proveedor,

        anterior.year_label AS year_anterior,
        actual.year_label AS year_actual,

        anterior.escenario AS escenario_anterior,
        actual.escenario AS escenario_actual,

        actual.week_number_business,
        anterior.year_week_key AS year_week_key_anterior,
        actual.year_week_key AS year_week_key_actual,

        anterior.week_label AS week_label_anterior,
        actual.week_label AS week_label_actual,

        actual.week_start_date,
        actual.week_end_date,

        actual.is_partial_week,
        actual.is_campaign_week,
        actual.campaign_name_primary,
        actual.campaign_group_primary,

        anterior.units_value AS units_value_anterior,
        actual.units_value AS units_value_actual,

        anterior.sales_value AS sales_value_anterior,
        actual.sales_value AS sales_value_actual,

        anterior.units_value_adjusted AS units_value_adjusted_anterior,
        actual.units_value_adjusted AS units_value_adjusted_actual,

        anterior.sales_value_adjusted AS sales_value_adjusted_anterior,
        actual.sales_value_adjusted AS sales_value_adjusted_actual

    FROM metricas_producto_semana actual
    LEFT JOIN metricas_producto_semana anterior
        ON actual.product_id = anterior.product_id
        AND actual.week_number_business = anterior.week_number_business
        AND actual.year_label = anterior.year_label + 1
        AND anterior.escenario = 'Real'

    WHERE actual.year_label IN (2025, 2026)
)

SELECT
    *,

    units_value_actual - units_value_anterior AS var_units_abs,

    (units_value_actual - units_value_anterior)
        / NULLIF(units_value_anterior, 0) AS var_units_pct,

    sales_value_actual - sales_value_anterior AS var_value_abs,

    (sales_value_actual - sales_value_anterior)
        / NULLIF(sales_value_anterior, 0) AS var_value_pct,

    units_value_adjusted_actual - units_value_adjusted_anterior 
        AS var_units_adjusted_abs,

    (units_value_adjusted_actual - units_value_adjusted_anterior)
        / NULLIF(units_value_adjusted_anterior, 0) AS var_units_adjusted_pct,

    sales_value_adjusted_actual - sales_value_adjusted_anterior 
        AS var_value_adjusted_abs,

    (sales_value_adjusted_actual - sales_value_adjusted_anterior)
        / NULLIF(sales_value_adjusted_anterior, 0) AS var_value_adjusted_pct,

    CAST(year_anterior AS VARCHAR)
        || ' '
        || escenario_anterior
        || ' vs '
        || CAST(year_actual AS VARCHAR)
        || ' '
        || escenario_actual AS periodo_comparativo

FROM comparativa;

SELECT * FROM VW_VENTAS_YOY_PRODUCTO_SEMANA LIMIT 50; 

CREATE OR REPLACE VIEW vw_ventas_yoy_categoria_semana AS

WITH metricas_categoria_semana AS (

    -- Ventas reales 2024 y 2025
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Real' AS escenario,

        category_id,
        categoria,
        familia_categoria,
        formato_categoria,

        SUM(sales_units) AS units_value,
        SUM(sales_value_estimated) AS sales_value,

        SUM(sales_units_adjusted) AS units_value_adjusted,
        SUM(sales_value_estimated_adjusted) AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label IN (2024, 2025)
    GROUP BY
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,
        category_id,
        categoria,
        familia_categoria,
        formato_categoria

    UNION ALL

    -- Forecast 2026: escenario base
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Forecast base' AS escenario,

        category_id,
        categoria,
        familia_categoria,
        formato_categoria,

        SUM(forecast_base_units) AS units_value,
        SUM(forecast_base_value_estimated) AS sales_value,

        SUM(forecast_base_units_adjusted) AS units_value_adjusted,
        SUM(forecast_base_value_estimated_adjusted) AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,
        category_id,
        categoria,
        familia_categoria,
        formato_categoria

    UNION ALL

    -- Forecast 2026: escenario optimista
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Forecast optimista' AS escenario,

        category_id,
        categoria,
        familia_categoria,
        formato_categoria,

        SUM(forecast_optimista_units) AS units_value,
        SUM(forecast_optimista_value_estimated) AS sales_value,

        SUM(forecast_optimista_units_adjusted) AS units_value_adjusted,
        SUM(forecast_optimista_value_estimated_adjusted) AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,
        category_id,
        categoria,
        familia_categoria,
        formato_categoria

    UNION ALL

    -- Forecast 2026: escenario pesimista
    SELECT
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,

        'Forecast pesimista' AS escenario,

        category_id,
        categoria,
        familia_categoria,
        formato_categoria,

        SUM(forecast_pesimista_units) AS units_value,
        SUM(forecast_pesimista_value_estimated) AS sales_value,

        SUM(forecast_pesimista_units_adjusted) AS units_value_adjusted,
        SUM(forecast_pesimista_value_estimated_adjusted) AS sales_value_adjusted

    FROM vw_ventas_base
    WHERE year_label = 2026
    GROUP BY
        year_label,
        week_number_business,
        year_week_key,
        week_label,
        week_start_date,
        week_end_date,
        is_partial_week,
        is_campaign_week,
        campaign_name_primary,
        campaign_group_primary,
        category_id,
        categoria,
        familia_categoria,
        formato_categoria
),

comparativa AS (
    SELECT
        actual.category_id,
        actual.categoria,
        actual.familia_categoria,
        actual.formato_categoria,

        anterior.year_label AS year_anterior,
        actual.year_label AS year_actual,

        anterior.escenario AS escenario_anterior,
        actual.escenario AS escenario_actual,

        actual.week_number_business,
        anterior.year_week_key AS year_week_key_anterior,
        actual.year_week_key AS year_week_key_actual,

        anterior.week_label AS week_label_anterior,
        actual.week_label AS week_label_actual,

        actual.week_start_date,
        actual.week_end_date,

        actual.is_partial_week,
        actual.is_campaign_week,
        actual.campaign_name_primary,
        actual.campaign_group_primary,

        anterior.units_value AS units_value_anterior,
        actual.units_value AS units_value_actual,

        anterior.sales_value AS sales_value_anterior,
        actual.sales_value AS sales_value_actual,

        anterior.units_value_adjusted AS units_value_adjusted_anterior,
        actual.units_value_adjusted AS units_value_adjusted_actual,

        anterior.sales_value_adjusted AS sales_value_adjusted_anterior,
        actual.sales_value_adjusted AS sales_value_adjusted_actual

    FROM metricas_categoria_semana actual
    LEFT JOIN metricas_categoria_semana anterior
        ON actual.category_id = anterior.category_id
        AND actual.week_number_business = anterior.week_number_business
        AND actual.year_label = anterior.year_label + 1
        AND anterior.escenario = 'Real'

    WHERE actual.year_label IN (2025, 2026)
)

SELECT
    *,

    units_value_actual - units_value_anterior AS var_units_abs,

    (units_value_actual - units_value_anterior)
        / NULLIF(units_value_anterior, 0) AS var_units_pct,

    sales_value_actual - sales_value_anterior AS var_value_abs,

    (sales_value_actual - sales_value_anterior)
        / NULLIF(sales_value_anterior, 0) AS var_value_pct,

    units_value_adjusted_actual - units_value_adjusted_anterior 
        AS var_units_adjusted_abs,

    (units_value_adjusted_actual - units_value_adjusted_anterior)
        / NULLIF(units_value_adjusted_anterior, 0) AS var_units_adjusted_pct,

    sales_value_adjusted_actual - sales_value_adjusted_anterior 
        AS var_value_adjusted_abs,

    (sales_value_adjusted_actual - sales_value_adjusted_anterior)
        / NULLIF(sales_value_adjusted_anterior, 0) AS var_value_adjusted_pct,

    CAST(year_anterior AS VARCHAR)
        || ' '
        || escenario_anterior
        || ' vs '
        || CAST(year_actual AS VARCHAR)
        || ' '
        || escenario_actual AS periodo_comparativo

FROM comparativa;

SELECT * FROM vw_ventas_yoy_categoria_semana LIMIT 50;