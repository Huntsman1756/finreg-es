# FinReg España — P1: portfolio polish (presentación pública)

> **Estado: OPEN — preregistro**. G0, G1, G2 y G3 congelados
> (`g0-portfolio-closed`, `g1-regulatory-semantics-closed`,
> `g2-longitudinal-evidence-closed`, `g3-consumability-closed`);
> no se reabren salvo defecto reproducible nuevo. P1 es
> presentación del sistema cerrado — no es una fase de ingeniería
> y no añade capacidad.

## Tesis (falsable)

```text
La superficie pública del repositorio debe permitir que un tercero
entienda, reproduzca y evalúe las capacidades ya demostradas de
FinReg sin conocer su historia interna de gates.
```

## El fallo concreto

```text
el sistema ya hace más de lo que el README comunica:
  README describe el motor (G0–G2)
  pero G3 añadió CLI, MCP, proyección Datasette, wheel instalable
  con runtime evidence bundle — nada de eso es visible desde fuera
```

## Qué es FinReg hoy (postura pública correcta)

```text
Motor regulatorio auditable, longitudinal y bitemporal con
superficies de consumo read-only reproducibles.

NO es: servicio productivo, SaaS, registro exhaustivo del mercado,
ni distribución pública soportada.
```

## Frontera estricta

```text
P1 toca documentación pública; nunca el sistema.

README.md            actualizable
docs/p1-*, docs/examples/   artefactos nuevos permitidos
finreg_es/           CONGELADO — cero cambios
adapters/            cero cambios semánticos o de payload
fixtures/            cero cambios (los ejemplos se capturan, no se mutan)
```

## Restricciones vinculantes

```text
1. cero cambios en finreg_es/
2. cero cambios semánticos o de payload en adapters/
3. ningún ejemplo inventado, sintetizado o "simplificado"
4. ningún claim del README que no pueda enlazarse a un
   G0/G1/G2/G3 FINAL-REPORT o a una ejecución reproducible
```

Regla de presentación: si el README muestra sólo parte de un
output, lo declara explícitamente como extracto y enlaza al output
completo en `docs/examples/` — un snippet visual nunca se confunde
con el artefacto reproducible.

## Workstreams preregistrados

| ID | Área | Entregable |
|----|------|------------|
| P1-A | README actual | tesis + capacidades G0–G3 + límites; describe lo que existe, no lo que se prometió |
| P1-B | quickstart reproducible | checkout del tag → build wheel local → venv limpio → instalar wheel + extra → `finreg --help` → query real → resultado verificable |
| P1-C | ejemplos reales | 2–3 outputs capturados de comandos reales; canonical JSON exacto; `command + tag + inputs + stdout + sha256(stdout)` |
| P1-D | arquitectura | diagrama: fuente oficial → core → bitemporal/diff → facade → CLI/MCP/Datasette → runtime evidence bundle |
| P1-E | GitHub Release | **OPCIONAL / task separada**, sin PyPI; su propio GO y evidencia |

### Ejemplos autoritativos (P1-C)

```text
docs/examples/
  assess-bitemporal.json     (o nombres equivalentes)
  evidence.json
  changes-blocked.json

cada uno documenta:
  command + versión/tag + inputs
  + stdout canonical JSON completo (sin reformatear)
  + sha256(stdout)
```

### Quickstart (P1-B) — sin trampa de distribución

No existe release pública: el quickstart NO documenta
`pip install finreg-es`. Documenta el flujo real soportado:

```text
git clone …
git checkout g3-consumability-closed
python -m build                 # requiere build+hatchling
python -m venv .venv
…\Scripts\activate | bin/activate
pip install "dist/finreg_es-0.0.1-py3-none-any.whl[cli]"
finreg --help
finreg assess-bitemporal …      # query real con resultado esperado
```

### Fricción del quickstart

```text
quickstart failure
→ finding documentado de P1
→ no fix dentro de P1
→ task/fase sucesora
```

P1 es auditoría de presentabilidad, no excusa para reabrir G3.

## Fuera de alcance de P1

- PyPI / índices / wheelhouses remotos (es P1-E+ o fase de release).
- Cambios de producto por fricción descubierta (→ finding).
- Nuevas capacidades de dominio (otra fase, con su preregistro).
- Tag de cierre: P1 es polish, no capacidad técnica nueva; basta
  commit de cierre.

## Criterios de cierre de P1

```text
✓ quickstart ejecutado realmente desde limpio (no aspiracional)
✓ 2–3 outputs regenerados byte-idénticos, hashes documentados
✓ README consistente con docs/G3-FINAL-REPORT.md
✓ diagrama no introduce capacidades inexistentes
✓ enlaces internos válidos
✓ suite completa verde + replay G2-F PASS
✓ G3 permanece congelado (tag intacto, artefactos intocados)
```

## Resultados válidos (declarados antes de ejecutar)

```text
PASS       todos los workstreams A–D cumplidos; E pendiente aparte
QUALIFIED  presentación publicada con una limitación concreta
           declarada (p.ej. un ejemplo no reproducible → finding)
FAIL       el sistema no puede presentarse honestamente sin tocar
           producción — eso sería evidencia contra P1, no se oculta
```

## Tasks derivadas

```text
p1-preregister        esta preregistro (docs-only)
p1-portfolio-polish   ejecución A–D; cambios limitados a
                      README.md · docs/p1-* · docs/examples/*
p1-e-github-release   OPCIONAL, task separada, status blocked
                      hasta GO explícito
```
