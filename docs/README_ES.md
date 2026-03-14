<p align="center">
  <img src="assets/contextgraph-hero.jpeg" alt="ContextGraph — La Capa de Conocimiento para Agentes de IA" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>La Capa de Conocimiento para Agentes de IA</strong><br>
  Almacena memorias. Extrae claims. Comparte conocimiento entre agentes.<br>
  <em>Privado por defecto. Con pagos cuando quieras. Verificado on-chain.</em>
</p>

<p align="center">
  <a href="../README.md">English</a> · <a href="README_ES.md">Español</a>
</p>

---

## ¿Qué es ContextGraph?

ContextGraph es un **protocolo de grafo de conocimiento open-source** que brinda a los agentes de IA memoria persistente y compartida con confianza, permisos y pagos integrados.

Los agentes producen conocimiento. ContextGraph lo captura como **claims estructurados** con procedencia, puntajes de confianza y fechas de expiración — y luego lo hace descubrible entre agentes, organizaciones y plataformas.

### Características principales

- **Memoria nativa de claims** — El texto se descompone automáticamente en claims estructurados con entidades, puntajes de confianza y fechas de expiración
- **Permisos granulares (4 niveles)** — `private`, `org`, `shared` (con lista de acceso), `published`
- **Pagos x402** — Los agentes pueden monetizar su conocimiento con micropagos USDC
- **Identidad ERC-8004** — Verificación de identidad de agentes on-chain
- **Servidor MCP** — Compatible con Claude, GPT y otros agentes MCP
- **Protocolo A2A** — Descubrimiento y comunicación entre agentes
- **Federación** — Comparte claims publicados entre nodos ContextGraph
- **Confianza y gobernanza** — Flujos de revisión con atestación y desafío
- **Consultas permanentes** — Suscríbete a temas y recibe notificaciones (pull, webhook, A2A)
- **Extracción BM25 + LLM** — Scoring avanzado y extracción opcional con Claude

## Inicio Rápido

### Instalar

```bash
pip install contextgraph
# Con servidor (FastAPI + Uvicorn):
pip install contextgraph[server]
```

### 5 Líneas para Memoria Compartida

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
agent = service.register_agent("mi-agente", "mi-org", ["investigacion"])
service.store_memory(agent.agent_id, "Acme Corp reportó latencia en la API.", visibility="org")
hits = service.recall(agent.agent_id, "Acme latencia")
print(hits[0].claim.statement)  # "Acme Corp reportó latencia en la API"
```

### Docker

```bash
docker compose up
```

Inicia ContextGraph + Neo4j. API en `http://localhost:8420`, docs en `http://localhost:8420/docs`.

## Dónde encaja ContextGraph

| Capa | Protocolo | Qué hace |
|------|-----------|----------|
| **Orquestación** | LangGraph, CrewAI | Enrutamiento de tareas y coordinación |
| **Comunicación** | Protocolo A2A | Descubrimiento entre agentes |
| **Herramientas** | MCP | Integración de herramientas y recursos |
| **Pagos** | Protocolo x402 | Micropagos nativos HTTP |
| **Identidad** | ERC-8004 | Identidad de agente on-chain |
| **Conocimiento** | **ContextGraph** | **Memoria compartida persistente con confianza** |

## Comparación

| Característica | ContextGraph | Mem0 | Zep | LangMem |
|---------------|:---:|:---:|:---:|:---:|
| Claims estructurados | **Sí** | No | No | No |
| Permisos granulares (4 niveles) | **Sí** | No | Básico | No |
| Compartir entre organizaciones | **Sí** | No | No | No |
| Pagos x402 | **Sí** | No | No | No |
| Identidad on-chain (ERC-8004) | **Sí** | No | No | No |
| Servidor MCP | **Sí** | No | No | No |
| Protocolo A2A | **Sí** | No | No | No |
| Federación | **Sí** | No | No | No |
| Modelo de confianza/atestación | **Sí** | No | No | No |
| Open source | **MIT** | Parcial | Parcial | Sí |

## Configuración

Todas las configuraciones son variables de entorno. Ver [`.env.example`](../.env.example) para la lista completa.

## Contribuir

¡Bienvenidas las contribuciones! Ver [CONTRIBUTING.md](../CONTRIBUTING.md) para instrucciones de desarrollo.

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd contextgraph
make install    # Instalar dependencias de desarrollo
make test       # Ejecutar tests (90+)
make lint       # Ejecutar linter
```

## Licencia

MIT — ver [LICENSE](../LICENSE).

---

<p align="center">
  Construido para la economía de agentes.<br>
  <strong>ContextGraph</strong> — porque los agentes merecen memoria estructurada, confiable y compartida.
</p>
