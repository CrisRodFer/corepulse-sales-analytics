# 📊 Corepulse - Dashboard Comercial y Forecast 2026

## 🧠 Descripción del proyecto

**Corepulse** es un proyecto de análisis comercial desarrollado sobre una empresa simulada de nutrición deportiva. El objetivo principal es construir un modelo analítico completo que permita estudiar el comportamiento de ventas, analizar productos y proveedores estratégicos, y evaluar escenarios de previsión para 2026 mediante un dashboard interactivo en **Data Studio**.

El proyecto parte de datos de ventas, catálogo de productos, proveedores, categorías, campañas y previsiones comerciales. A partir de ellos se desarrolla un flujo completo de preparación, modelado dimensional, carga en base de datos, creación de vistas analíticas en BigQuery y explotación visual en un cuadro de mando final.

El resultado es un dashboard orientado a negocio que permite responder preguntas como:

- Qué productos concentran mayor volumen de ventas.
- Cómo evolucionan las ventas frente al año anterior.
- Qué productos presentan mayor potencial o riesgo.
- Qué proveedores tienen mayor peso comercial.
- Qué proveedores requieren seguimiento prioritario.
- Cómo varía la previsión 2026 según distintos escenarios.

---

## 🔗 Dashboard interactivo

El dashboard final está disponible en modo solo lectura:

[Ver dashboard interactivo en Data Studio](https://datastudio.google.com/reporting/ff539db7-7142-4ea5-9e66-bf3125feee87)

---

## 🎯 Objetivos del proyecto

- Construir un modelo de datos preparado para análisis comercial.
- Diseñar una arquitectura analítica basada en vistas SQL reutilizables.
- Analizar la evolución de ventas y unidades vendidas.
- Comparar ventas actuales frente al año anterior.
- Clasificar productos según su comportamiento estratégico.
- Evaluar proveedores según dependencia comercial y prioridad de revisión.
- Analizar escenarios de previsión para 2026: pesimista, base y optimista.
- Crear un dashboard interactivo y visualmente cuidado en Data Studio.
- Documentar el proceso técnico y metodológico en notebooks.
- Presentar el proyecto como pieza de portfolio profesional de análisis de datos.

---

## 🏗️ Arquitectura del proyecto

```text
Datos originales
      ↓
Preparación y limpieza con Python
      ↓
Construcción del modelo dimensional
      ↓
Generación de tablas finales
      ↓
Carga y explotación analítica en BigQuery
      ↓
Creación de vistas SQL de consumo
      ↓
Visualización en Data Studio
      ↓
Documentación técnica y metodológica
```

---

## 📂 Estructura del repositorio

```text
Proyecto_1_Corepulse/
│
├── data/
│   ├── raw/              # Datos originales no incluidos en GitHub
│   ├── interim/          # Datos intermedios generados durante el pipeline
│   └── processed/        # Tablas finales preparadas para análisis
│
├── scripts/              # Scripts Python del pipeline
│
├── sql/                  # Scripts SQL generados y consultas de vistas
│
├── notebooks/            # Notebooks de documentación, validación y análisis
│
├── dashboards/           # Capturas o recursos relacionados con el dashboard
│
├── docs/                 # Documentación adicional del modelo
│
├── README.md             # Documentación principal del proyecto
└── requirements.txt      # Dependencias del entorno Python
```

---

## ⚙️ Tecnologías utilizadas

- **Python**
  - pandas
  - numpy
  - pyarrow
  - openpyxl

- **SQL**
  - modelado analítico
  - creación de vistas
  - validaciones de datos

- **BigQuery**
  - capa analítica final
  - vistas de consumo para Data Studio

- **Snowflake**
  - fase inicial de generación y validación de scripts SQL

- **Data Studio**
  - dashboard interactivo final

- **Git / GitHub**
  - control de versiones
  - documentación del proyecto
  - preparación para portfolio

---

## 🧩 Modelo de datos

El proyecto sigue un enfoque de **modelo dimensional en estrella**, compuesto por una tabla de hechos central y varias dimensiones descriptivas.

### Tabla de hechos

- `fact_ventas`

### Dimensiones

- `dim_producto`
- `dim_categoria`
- `dim_proveedor`
- `dim_calendario`

La granularidad de la tabla de hechos final es:

```text
1 fila = 1 producto + 1 semana de negocio
```

Este grano permite analizar la evolución temporal de las ventas manteniendo un volumen de datos manejable para su explotación en herramientas de Business Intelligence.

---

## 🔄 Pipeline del proyecto

El pipeline se estructura en scripts secuenciales:

| Script | Descripción |
|---|---|
| `01_preparar_fuentes_dashboard.py` | Prepara y alinea las fuentes base del dashboard. |
| `02_seleccionar_productos_dashboard.py` | Selecciona el subconjunto final de productos para el análisis. |
| `03_construir_fact_base_semanal.py` | Construye la tabla de hechos semanal. |
| `04_construir_dim_tiempo.py` | Construye la dimensión calendario semanal. |
| `05_construir_dim_producto.py` | Construye la dimensión producto y dimensiones auxiliares. |
| `06_enriquecer_dim_proveedor.py` | Enriquece la dimensión proveedor. |
| `07_enriquecer_dim_categoria.py` | Enriquece la dimensión categoría. |
| `08_preparar_modelo_final.py` | Cierra el modelo dimensional final. |
| `09_generar_sql_snowflake.py` | Genera scripts SQL para la carga inicial en base de datos. |

---

## 🗄️ Capa analítica en BigQuery

Tras la construcción del modelo dimensional, se desarrolla una capa analítica en BigQuery mediante vistas SQL.

Estas vistas permiten centralizar la lógica de negocio antes de conectar los datos a Data Studio, reduciendo la necesidad de cálculos complejos dentro de la herramienta de visualización.

### Vistas principales conectadas al dashboard

| Vista | Uso principal |
|---|---|
| `vw_ventas_base` | Base analítica general de ventas, calendario, producto, proveedor y forecast. |
| `vw_ventas_yoy_producto_semana` | Comparativa semanal TY vs LY por producto. |
| `vw_detalle_producto` | Fuente principal para la página de detalle de producto. |
| `vw_detalle_proveedor` | Fuente principal para la página de análisis estratégico de proveedores. |
| `vw_forecast_2026` | Fuente principal para la página de previsión 2026. |
| `vw_forecast_2026_resumen_escenario` | Resumen comparativo de escenarios de previsión. |

### Vistas auxiliares

Algunas vistas no se conectan directamente al dashboard, pero sirven como base para construir indicadores utilizados posteriormente:

| Vista auxiliar | Uso |
|---|---|
| `vw_ranking_productos_anual_escenario` | Ranking y contribución de productos por año y escenario. |
| `vw_ranking_proveedores_anual_escenario` | Ranking y contribución de proveedores por año y escenario. |
| `vw_clasificacion_producto_estrategica` | Clasificación estratégica de productos. |

Esta separación entre vistas finales y vistas auxiliares permite mantener el dashboard más limpio y trasladar la lógica compleja a SQL.

---

## 📊 Dashboard final

El dashboard final se desarrolla en **Data Studio** y está compuesto por cinco páginas principales.

### 1. Resumen ejecutivo

Página inicial del informe. Presenta una visión global del negocio mediante:

- KPIs principales de ventas, unidades y variación YoY.
- Evolución de ventas TY vs LY.
- Distribución de productos por clasificación estratégica.
- Ventas por dimensión dinámica.
- Top proveedores por ventas.

Esta página permite entender rápidamente el estado general del negocio.

---

### 2. Detalle de producto

Página orientada al análisis individual de cada producto.

Incluye:

- Ficha técnica del producto.
- Imagen del producto.
- Ventas y unidades TY.
- Variación YoY.
- Contribución sobre ventas.
- Venta media semanal.
- Ranking 2025.
- Evolución semanal TY vs LY.
- Comparación del producto frente a su categoría.
- Información básica del proveedor asociado.

Esta página permite analizar el comportamiento comercial de un producto concreto y contextualizarlo dentro de su categoría.

---

### 3. Análisis estratégico de proveedores

Página accesoria orientada a evaluar el peso y riesgo de cada proveedor.

Incluye:

- Ficha del proveedor.
- Dependencia comercial.
- Prioridad del proveedor.
- Motivo de prioridad.
- Ventas TY proveedor.
- Contribución del proveedor sobre ventas totales.
- Productos en riesgo.
- Porcentaje de ventas en riesgo.
- Ranking del proveedor.
- Evolución TY vs LY.
- Ventas por clasificación estratégica.
- Tabla de productos asociados.

Esta página permite identificar proveedores relevantes y analizar si requieren seguimiento o revisión.

---

### 4. Previsión 2026

Página dedicada al análisis prospectivo del negocio mediante escenarios de forecast.

Incluye:

- Selector de escenario: pesimista, base u optimista.
- Ventas previstas 2026.
- Unidades previstas 2026.
- Variación frente a 2025.
- Ticket medio previsto.
- Productos con mayor potencial.
- Evolución prevista 2026 vs real 2025.
- Forecast por dimensión dinámica.
- Top productos previstos.
- Resumen comparativo por escenario.

Esta página permite analizar cómo podría evolucionar el negocio bajo distintos escenarios comerciales.

---

### 5. Metodología y criterios de análisis

Página de apoyo interpretativo del dashboard.

Explica:

- Alcance del informe.
- Fuentes y modelo de datos.
- Clasificación estratégica de productos.
- Dependencia y prioridad de proveedores.
- Escenarios de previsión 2026.

Además, incorpora navegación contextual para volver a la página desde la que se accede a cada explicación, manteniendo una experiencia de usuario más fluida.

---

## 🧠 Lógicas de negocio destacadas

### Clasificación estratégica de productos

Los productos se clasifican en función de ventas TY, variación YoY, ranking y previsión 2026.

| Clasificación | Interpretación |
|---|---|
| Líder consolidado | Producto top en ventas, con evolución estable o positiva. |
| Líder en riesgo | Producto top en ventas, pero con señales de caída o previsión desfavorable. |
| Emergente | Producto no líder, pero con crecimiento y previsión positiva. |
| Rezagado | Producto con menor peso relativo o señales débiles de evolución. |

---

### Dependencia comercial del proveedor

La dependencia comercial mide cuánto depende el negocio de un proveedor según su peso relativo en ventas.

| Nivel | Criterio |
|---|---|
| Alta | Proveedor dentro del top 25 % por ventas. |
| Media | Proveedor entre el top 25 % y top 50 %. |
| Baja | Resto de proveedores. |

La dependencia comercial no implica necesariamente riesgo. Un proveedor puede ser muy relevante para el negocio y, aun así, no requerir revisión urgente.

---

### Prioridad del proveedor

La prioridad del proveedor indica si un proveedor requiere seguimiento o revisión.

Se calcula combinando:

- Dependencia comercial.
- Porcentaje de ventas en riesgo.
- Porcentaje de ventas asociadas a productos líderes en riesgo.
- Productos rezagados.
- Lead time elevado.

La prioridad puede ser:

| Prioridad | Interpretación |
|---|---|
| Alta | Proveedor relevante con señales claras de riesgo o exposición elevada. |
| Media | Proveedor con señales moderadas de seguimiento. |
| Baja | Proveedor sin señales relevantes de prioridad. |

---

### Escenarios de previsión 2026

La previsión se analiza mediante tres escenarios:

| Escenario | Interpretación |
|---|---|
| Pesimista | Escenario conservador. |
| Base | Escenario más probable. |
| Optimista | Escenario de mayor crecimiento. |

También se identifican productos con mayor potencial, definidos como aquellos cuya previsión crece más de un 15 % frente a 2025.

---

## ✅ Validaciones incluidas

Durante el proyecto se aplican distintas validaciones técnicas y analíticas:

- Control de duplicados.
- Validación de claves primarias y foráneas.
- Revisión de productos excluidos.
- Validación de granularidad de la tabla de hechos.
- Control de semanas parciales.
- Comprobación de dimensiones.
- Validación de rankings y contribuciones.
- Revisión de métricas YoY.
- Validación de escenarios de forecast.
- Comprobación de coherencia entre vistas BigQuery y visualizaciones en Data Studio.

---

## 📈 Resultados del proyecto

El proyecto permite analizar:

- Ventas totales y evolución temporal.
- Variación de ventas frente al año anterior.
- Ranking de productos y proveedores.
- Contribución de productos y proveedores.
- Clasificación estratégica del catálogo.
- Comportamiento individual de productos.
- Dependencia y prioridad de proveedores.
- Previsión de ventas para 2026.
- Escenarios pesimista, base y optimista.
- Productos con mayor potencial comercial.

---

## 🗃️ Datos

Los datos originales no se incluyen en el repositorio por motivos de tamaño, privacidad y buenas prácticas de versionado.

La estructura esperada para ejecutar el proyecto es:

```text
data/raw/
```

Los archivos generados durante el proceso se guardan en:

```text
data/interim/
data/processed/
```

---

## 🚀 Cómo ejecutar el proyecto

1. Clonar el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
```

2. Crear y activar un entorno virtual:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Colocar los datos originales en:

```text
data/raw/
```

5. Ejecutar los scripts en orden desde la raíz del proyecto:

```bash
python scripts/01_preparar_fuentes_dashboard.py
python scripts/02_seleccionar_productos_dashboard.py
python scripts/03_construir_fact_base_semanal.py
python scripts/04_construir_dim_tiempo.py
python scripts/05_construir_dim_producto.py
python scripts/06_enriquecer_dim_proveedor.py
python scripts/07_enriquecer_dim_categoria.py
python scripts/08_preparar_modelo_final.py
python scripts/09_generar_sql_snowflake.py
```

---

## 📚 Documentación

El proyecto se documenta principalmente en notebooks, donde se explica:

- Preparación de datos.
- Validación del modelo.
- Construcción de vistas analíticas.
- Decisiones metodológicas.
- Diseño del dashboard.
- Criterios de clasificación e interpretación.
- Validaciones finales.

Notebook principal:

```text
notebooks/02_validacion_explotacion_modelo_corepulse.ipynb
```

---

## ⚠️ Notas del proyecto

- Este proyecto utiliza datos simulados o adaptados con fines formativos y de portfolio.
- Los datos originales y archivos pesados se excluyen mediante `.gitignore`.
- El dashboard se comparte en modo solo lectura.
- El objetivo principal es mostrar un flujo completo de trabajo analítico: preparación, modelado, SQL, BI, documentación y storytelling de negocio.

---

## 👩‍💻 Autora

**Cristina Rodríguez Fernández**

Proyecto desarrollado como parte de la consolidación de conocimientos en análisis de datos, modelado dimensional, SQL, BigQuery y herramientas de Business Intelligence.
