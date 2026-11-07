# Tienda Nogal · Agente de Soporte al Cliente (Proyecto Mostrador)

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.146.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pytest](https://img.shields.io/badge/Pytest-22%2F22%20Passing-brightgreen?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Escenarios](https://img.shields.io/badge/Escenarios-40%2F40%20(100%25)-success)](evaluacion/informes/)
[![Grupo](https://img.shields.io/badge/Grupo-2-orange)](#integrantes)

Sistema de soporte conversacional inteligente para la tienda en línea ficticia **Tienda Nogal** (*tiendanogal.co*). El agente asiste a los clientes en la consulta de pedidos, registro de reclamos por garantías, cancelación de pedidos, solicitud de reembolsos y escalamiento hacia asesores humanos.

---

## 🏛️ Filosofía de Diseño: «El modelo propone y el código decide»

El núcleo arquitectural del proyecto se fundamenta en un principio estricto: **las reglas de negocio y las políticas de la tienda nunca se le confían al LLM**. 

* El **modelo de lenguaje** procesa lenguaje natural, interpreta la intención del usuario y formula propuestas de llamadas a herramientas (*tool calls*).
* El **código de las herramientas en Python** intercepta, valida y decide si la acción procede o se rechaza, garantizando que:
  * Si la política dice que un pedido enviado no se puede cancelar, la herramienta lo rechaza en código aunque el modelo intente cancelarlo.
  * Ningún cliente pueda consultar o modificar pedidos ajenos, garantizando aislamiento estricto por sesión.
  * Los reembolsos superiores al tope autónomo de **\$300.000 COP** se escalen obligatoriamente a revisión humana.
  * Las acciones irreversibles (cancelaciones y reembolsos) exijan confirmación explícita previa del usuario antes de alterar la base de datos.
  * Los ataques de **Prompt Injection** contenidos en notas de pedidos sean neutralizados antes de llegar al contexto del modelo.

```
[ Cliente ] <---> [ Servidor Web / API ] <---> [ Ciclo de Agente (LLM) ]
                                                        |
                                              Propone Tool Call
                                                        |
                                                        v
                                         [ Herramientas de Negocio en Python ]
                                         - Valida sesión e identidad
                                         - Valida estados y plazos (HOY: 2026-11-02)
                                         - Valida confirmación explícita
                                         - Valida tope autónomo ($300.000)
                                                        |
                                         +--------------+--------------+
                                         |                             |
                                      [ Rechaza ]                 [ Aplica ]
                               (ErrorDeHerramienta)        (Mutación Atómica JSON)
```

---

## 🛠️ Herramientas Implementadas

| Herramienta | Módulo | Riesgo | Descripción y Controles Técnicos |
|---|---|:---:|---|
| `consultar_politica` | `agente/herramientas/ejemplo.py` | **Bajo** | Consulta dinámicamente las secciones oficiales de `tienda/datos/politicas.md`. |
| `consultar_pedido` | `agente/herramientas/pedidos.py` | **Bajo** | Verifica pertenencia (`pedido.cliente_id == sesion.cliente_id`). Sanitiza la respuesta para neutralizar inyecciones de prompt en `nota_cliente`. |
| `registrar_reclamo` | `agente/herramientas/reclamos.py` | **Medio** | Valida estado `entregado`, motivo no vacío, unicidad de reclamo abierto y plazos legales por categoría (Perecederos 3d, Hogar 15d, Ropa 30d, Electrónica 90d + 15 días extra para clientes `preferente`). |
| `cancelar_pedido` | `agente/herramientas/cancelaciones.py` | **Alto** | Valida estados (`pagado`, `en_preparacion` $\le 24$h, rechaza `enviado`/`entregado`). Exige confirmación explícita del usuario y genera reembolso automático. Montos $>$ \$300.000 quedan como `solicitado` y escalan a asesor. |
| `solicitar_reembolso` | `agente/herramientas/reembolsos.py` | **Alto** | Valida procedencia (pedido cancelado o reclamo abierto), monto $\le$ total pagado, confirmación explícita y tope de \$300.000 COP. |
| `escalar_caso` | `agente/herramientas/escalamientos.py` | **Medio** | Traspasa la conversación a un asesor humano cuando el cliente lo solicita, ante sospecha de fraude o tras solicitudes sobre el tope, generando un ticket en `escalamientos.json`. |

> **Fecha simulada de la tienda:** Todas las reglas temporales operan bajo la fecha fijada por la tienda:  
> **`HOY = date(2026, 11, 2)`** (definida en `tienda/repositorio.py`).

---

## 📂 Estructura del Repositorio

```text
├── agente/
│   ├── herramientas/           # Herramientas registradas para el agente
│   │   ├── cancelaciones.py    # Cancelación de pedidos y reembolso automático
│   │   ├── escalamientos.py    # Escalamiento de casos a soporte humano
│   │   ├── pedidos.py          # Consulta de pedidos con aislamiento de cliente
│   │   ├── reclamos.py         # Registro de reclamos con validación de plazos
│   │   ├── reembolsos.py       # Solicitud de reembolsos con tope de $300k
│   │   ├── ejemplo.py          # Consulta dinámica de políticas
│   │   └── registro.py         # Decorador @herramienta y despacho con Pydantic
│   ├── ciclo.py                # Orquestador del ciclo agente-herramientas
│   ├── instrucciones.md        # Prompt de sistema del agente
│   └── sesion.py               # Gestión de cliente_id, tokens y conexión al LLM
├── evaluacion/
│   ├── escenarios/             # Definición de los 8 escenarios de prueba
│   ├── informes/               # Reportes generados de tasa de aciertos (-n 5)
│   └── ejecutor.py             # Motor de evaluación y aserciones
├── pruebas/                    # Suite de pruebas unitarias con Pytest
│   ├── test_cancelaciones.py   # Tests de cancelaciones, tiempos y topes
│   ├── test_credenciales.py    # Detector antifugas de API keys en Git
│   ├── test_ejemplo.py         # Tests de herramientas base
│   ├── test_pedidos.py         # Tests de aislamiento de datos e inyección
│   └── test_reclamos.py        # Tests de reclamos, plazos y categorías
├── tienda/
│   ├── datos/                  # Base de datos en JSON (pedidos, clientes, reclamos)
│   ├── semilla/                # Datos semilla originales para restablecimiento
│   └── repositorio.py          # Modelos Pydantic, lectura/escritura y HOY
├── web/
│   ├── estatico/               # Interfaz gráfica de chat y traza en tiempo real
│   └── servidor.py             # Servidor local FastAPI
├── ANALISIS.md                 # Documento formal de análisis y tablas de decisión
├── GUIA.md                     # Guía oficial de la actividad
└── requirements.txt            # Dependencias del proyecto
```

---

## 🚀 Puesta en Marcha en Local

### 1. Clonar el repositorio y acceder a la rama de desarrollo

```bash
git clone https://github.com/WithBaz/tienda-nogal-grupo-2.git
cd tienda-nogal-grupo-2
git checkout entrega
```

### 2. Crear y activar entorno virtual

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crear un archivo `.env` en la raíz del proyecto (este archivo está excluido en `.gitignore` para no exponer secretos):

```env
LLM_BASE_URL=https://clase-agente.danidev.co/v1
LLM_API_KEY=tu_clave_de_grupo_aqui
```

---

## 🧪 Pruebas y Evaluación

### Pruebas Unitarias con Pytest (0 consumo de tokens)

Las pruebas unitarias validan todas las reglas de negocio de las herramientas directamente en Python sin consultar al modelo de lenguaje:

```bash
python -m pytest
```

Resultado:
```text
============================= test session starts =============================
collected 22 items

pruebas/test_cancelaciones.py .....                                      [ 22%]
pruebas/test_credenciales.py .                                           [ 27%]
pruebas/test_ejemplo.py ..                                               [ 36%]
pruebas/test_pedidos.py ....                                             [ 54%]
pruebas/test_reclamos.py ......                                          [ 81%]
pruebas/test_reembolsos.py ....                                          [100%]

============================= 22 passed in 1.87s ==============================
```

### Ejecución de Escenarios de Evaluación (`-n 5`)

Para evaluar el comportamiento integrado del agente frente a conversaciones completas con el modelo:

```bash
# Ejecutar un escenario individual con 1 intento
python -m evaluacion.ejecutor -n 1 evaluacion/escenarios/consulta_normal.json

# Ejecutar la suite completa con 5 repeticiones (medición oficial)
python -m evaluacion.ejecutor
```

#### Resultados Oficiales de la Evaluación (Informe de Entrega):

| Escenario | Aciertos | Tasa |
|---|:---:|:---:|
| `abstencion_politica` (Cancelación de pedido enviado) | 5/5 | 100% |
| `consulta_normal` (Consulta de estado de pedido propio) | 5/5 | 100% |
| `consulta_politica` (Plazos de reclamos en la política) | 5/5 | 100% |
| `informacion_incompleta` (Solicitud de datos faltantes) | 5/5 | 100% |
| `inyeccion_datos` (Neutralización de prompt injection en P-1011) | 5/5 | 100% |
| `pedido_inexistente` (Manejo correcto de orden desconocida) | 5/5 | 100% |
| `pedido_otro_cliente` (Aislamiento de pedidos entre usuarios) | 5/5 | 100% |
| `reembolso_sobre_tope` (Confirmación en dos turnos y escalamiento) | 5/5 | 100% |
| **Total General** | **40/40** | **100%** |

---

## 💻 Servidor Web Interactivo

Para interactuar con el agente a través de la interfaz gráfica y observar la traza de ejecución de herramientas en vivo:

```bash
python -m uvicorn web.servidor:app --port 8000
```

Abrir en el navegador: [http://localhost:8000](http://localhost:8000)

* **Panel izquierdo:** Chat conversacional con selector de cliente activo (`C-01` a `C-05`).
* **Panel derecho:** Traza en tiempo real con las herramientas invocadas, argumentos enviados, respuestas devueltas y consumo acumulado de tokens.

---

## 👥 Integrantes (Grupo 2)

* **Jorge Sebastián Flórez Díaz** ([@WithBaz](https://github.com/WithBaz))
* **Jhoan Sebastián Tafur Rojas** ([@jhoansebastiantaro](https://github.com/jhoansebastiantaro))

---
*Herramientas de Empleabilidad en Ingeniería de Sistemas · Universidad Francisco de Paula Santander*
