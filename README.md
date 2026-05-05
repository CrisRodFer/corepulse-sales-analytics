# 📊 Corepulse - Análisis de Ventas

## 🧠 Descripción del proyecto

Este proyecto tiene como objetivo analizar el comportamiento de ventas de una empresa de nutrición deportiva, **Corepulse**, mediante la construcción de un modelo de datos preparado para explotación analítica y visualización en herramientas de Business Intelligence.

El flujo de trabajo parte de datos originales de ventas, catálogo, previsión y atributos comerciales, y los transforma progresivamente hasta construir un modelo dimensional en formato estrella, listo para ser cargado en una base de datos y conectado a herramientas como Power BI o Looker Studio.

---

## 🎯 Objetivos del proyecto

- Analizar la evolución de las ventas por periodo.
- Identificar productos top y productos con mayor oportunidad comercial.
- Analizar el comportamiento por categoría, proveedor y familia de producto.
- Comparar ventas históricas con escenarios de forecast.
- Preparar una base analítica sólida para dashboards de negocio.
- Facilitar la toma de decisiones relacionadas con ventas, inversión comercial y compras.

---

## 🏗️ Arquitectura del proyecto

```text
Datos originales
      ↓
Preparación y limpieza con Python
      ↓
Construcción de modelo dimensional
      ↓
Generación de scripts SQL
      ↓
Carga en base de datos
      ↓
Visualización en Power BI / Looker Studio
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
├── sql/                  # Scripts SQL generados para carga en base de datos
│
├── notebooks/            # Notebooks de documentación y análisis
│
├── dashboards/           # Capturas o archivos relacionados con dashboards
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
- **Snowflake**
- **Power BI**
- **Looker Studio**
- **Git / GitHub**

---

## 🧩 Modelo de datos

El proyecto sigue un enfoque de **modelo estrella**, compuesto por una tabla de hechos central y varias dimensiones descriptivas.

### Tabla de hechos

- `fact_ventas`

### Dimensiones

- `dim_producto`
- `dim_categoria`
- `dim_proveedor`
- `dim_calendario`

La granularidad de la fact final es:

```text
1 fila = 1 producto + 1 semana de negocio
```

---

## 🔄 Pipeline del proyecto

El pipeline se estructura en scripts secuenciales:

| Script | Descripción |
|---|---|
| `01_preparar_fuentes_dashboard.py` | Prepara y alinea las fuentes base del dashboard. |
| `02_seleccionar_productos_dashboard.py` | Selecciona el subconjunto final de productos para el análisis. |
| `03_construir_fact_base_semanal.py` | Construye la fact base semanal. |
| `04_construir_dim_tiempo.py` | Construye la dimensión calendario semanal. |
| `05_construir_dim_producto.py` | Construye la dimensión producto y dimensiones auxiliares. |
| `06_enriquecer_dim_proveedor.py` | Enriquece la dimensión proveedor. |
| `07_enriquecer_dim_categoria.py` | Enriquece la dimensión categoría. |
| `08_preparar_modelo_final.py` | Cierra el modelo dimensional final. |
| `09_generar_sql_snowflake.py` | Genera los scripts SQL para Snowflake. |

---

## 📊 Resultados esperados

El proyecto generará un modelo preparado para analizar:

- Ventas totales y evolución temporal.
- Comparativa entre ventas reales y forecast.
- Escenarios base, optimista y pesimista.
- Ranking de productos.
- Análisis por categoría.
- Análisis por proveedor.
- Impacto de campañas y semanas especiales.
- Identificación de productos estables, crecientes o a revisar.

---

## 📈 Dashboard

El dashboard se desarrollará en Power BI y/o Looker Studio.

En esta sección se añadirán más adelante:

- Capturas del dashboard.
- Descripción de páginas.
- KPIs principales.
- Decisiones de diseño.
- Enlace público, si procede.

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

## ✅ Validaciones incluidas

Durante el pipeline se aplican distintas validaciones, entre ellas:

- Control de duplicados.
- Validación de claves.
- Revisión de productos excluidos.
- Control de semanas parciales.
- Validación de la granularidad de la fact.
- Validación de dimensiones y claves relacionadas.
- Resúmenes de control exportados como archivos auxiliares.

---

## ⚠️ Notas del proyecto

- Este repositorio se irá completando progresivamente.
- El README es un documento vivo y se actualizará conforme avance el proyecto.
- Los datos originales y archivos pesados se excluyen mediante `.gitignore`.
- El objetivo principal es construir un proyecto reutilizable, documentado y presentable como portfolio profesional.

---

## 👩‍💻 Autora

**Cristina Rodríguez Fernández**

Proyecto desarrollado como parte de la consolidación de conocimientos en análisis de datos, modelado dimensional, SQL y herramientas de Business Intelligence.
