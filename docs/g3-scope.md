# FinReg España — G3: consumibilidad del motor

> **Estado: OPEN — preregistro**. G1 y G2 congelados
> (`g1-regulatory-semantics-closed`, `g2-longitudinal-evidence-closed`);
> no se reabren salvo defecto reproducible nuevo.

## Tesis

```text
FinReg expone assessments, evidencia, historia y provenance mediante
interfaces read-only estables, sin duplicar ni alterar la semántica
del core.
```

G3 no es "más motor": el motor está validado (515 tests, 18/18 probes
bitemporales, replay byte-idéntico). El problema a resolver es de
superficie pública: un tercero no puede consultarlo cómodamente.

## El fallo concreto

```text
hoy FinReg tiene un motor validado,
pero un tercero no puede consultarlo cómodamente.
```

Casos reales que la superficie debe cubrir:

```text
1. assessment actual
2. assessment valid_at × known_at
3. mostrar evidence_set + source_assertions
4. explicar por qué un resultado es BLOCKED/INDETERMINATE
5. consultar un cambio longitudinal
```

## Frontera estricta

```text
finreg_es core   stdlib-only, congelado (V1/V2/V3 intactas)
adapters/        pueden adoptar OSS justificado por scan
UI/API/MCP       nunca contienen semántica regulatoria
```

## Regla de arquitectura (restricción, no preferencia)

> Antes de escribir infraestructura genérica para FinReg, buscar
> primero OSS serio y medirlo contra un caso real; sólo construir
> propio si el scan termina en `PORT_PATTERN`/`REJECT`.

(`docs/adr-oss-scan-failure-driven.md`, elevada a restricción de
arquitectura tras G2.)

Donde OSS aporta valor real: interfaz, protocolo, exploración, CLI,
serving, scheduling, storage. Lo que FinReg conserva como propio:
semántica regulatoria, temporalidad, provenance y fail-closed.

## Workstreams preregistrados

| ID | Área | Pregunta a resolver |
|----|------|---------------------|
| G3-0 | README + public capability contract | Qué promete públicamente el sistema. |
| G3-A | OSS scan de query surfaces | Qué se adopta/reutiliza para exponer el core; decisión medida, no por popularidad. |
| G3-B | adapter read-only elegido | La interfaz que decide G3-A, implementada sobre el core sin copiar reglas. |
| G3-C | provenance/explanation surface | Cada respuesta expone evidence_set_id + trazas + razón del veredicto. |
| G3-D | smoke externo | Un cliente consulta FinReg sin conocer internals. |
| G3-E | packaging/deployment + closeout | Instalación local reproducible; cierre formal. |

## Criterios de medición del scan (G3-A)

```text
- cuánto código FinReg exige
- read-only de verdad
- determinismo / offline
- provenance conservada (evidence_set_id, claims, snapshots)
- dependencia y footprint
- API estable
- facilidad de despliegue local
- reutilizar el mismo core sin copiar reglas
```

Candidatos iniciales (lista de partida, **no** decisión):

```text
Datasette        exploración humana + JSON API sobre proyección SQLite read-only
MCP Python SDK   exponer assess/assess_bitemporal/evidencia a clientes MCP
FastAPI          API HTTP convencional para consumidores no-MCP
Typer            CLI tipada y reproducible
DuckDB           análisis/export sobre corpus (tooling, no semántica)
Streamlit        sólo UI exploratoria; comparar con Datasette
```

Expectativa previa registrada (NO vinculante; el scan decide):

```text
MCP SDK   → probablemente ADOPT (interfaz agente)
Typer     → probablemente ADOPT (CLI)
FastAPI   → probablemente ADOPT/WRAP (HTTP)
Datasette → PILOT fuerte (exploración humana)
DuckDB    → tooling/analytics
Streamlit → probablemente REJECT salvo que Datasette se quede corto
```

## Fuera de alcance en G3

- Semántica regulatoria nueva (otro gate, no éste).
- Mutar `finreg_es/` para servir interfaces.
- Escritura/mutación vía interfaces: read-only estricto.
- Auth, multiusuario, SaaS, hosting gestionado.
- Reabrir G1/G2 salvo defecto reproducible.

## Criterios de cierre de G3

```text
- capability contract público publicado
- scan OSS ejecutado y documentado con decisión por candidato
- adapter read-only implementado sobre el core sin copiar reglas
- provenance surface: cada respuesta expone evidence_set_id + trazas
- smoke externo reproducible por un cliente que no conoce internals
- cero regresión: full suite + replay G2-F verdes
```
