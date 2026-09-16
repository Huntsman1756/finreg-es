# G3-E0 — Contrato de packaging: runtime evidence bundle (preregistro)

**Estado:** FROZEN antes de producción (task
`g3-e0-package-preregister`; la ejecución es `g3-e1-package-build`,
el cierre `g3-e2-closeout`). Deriva de `docs/g3-scope.md` (G3-E:
"instalación local reproducible; cierre formal").

## 1. El fallo concreto

```text
adapters/common.py: ROOT = Path(__file__).resolve().parents[1]
defaults: fixtures/...

en checkout  → ROOT = <repo>            → funciona
en wheel     → ROOT = <site-packages>   → instala bien pero falla
               al cargar evidence set / contracts / events

pyproject.toml actual: sin [build-system], sin [project.scripts]
```

Un paquete que instala pero no responde es un gate falso. Lo que
se congela aquí no es el console script: es el contrato del
**runtime evidence bundle** — un wheel instalado fuera del
checkout debe responder con exactamente los mismos artefactos,
hashes y veredictos.

## 2. Tesis (falsable)

```text
Un wheel puro instalado en un venv limpio fuera del repo responde
con los mismos artefactos (byte-iguales), los mismos ids de
provenance (evidence_set_id, logical_projection_sha256) y los
mismos veredictos que el checkout — sin tocar finreg_es/ ni
duplicar fixtures en el source tree.
```

## 3. Micro-scan de backend (failure-driven)

Fallo a medir, uno solo:

```text
crear un wheel puro que contenga finreg_es + adapters + los
artefactos congelados necesarios, SIN duplicarlos en el source tree
```

| Backend | Licencia | Encaje medido | Decisión |
|---------|----------|---------------|----------|
| **hatchling** | MIT | `force-include` mapea paths existentes a rutas dentro del wheel sin copias fuente; reproducible builds soportados; mantenimiento alto (hatch ecosystem) | **ADOPT** |
| setuptools | MIT | `package_data` exige los ficheros DENTRO del package dir en el source tree → obligaría a duplicar/symlinkar fixtures | REJECT (para este fallo) |
| flit-core | BSD | sólo empaqueta lo que vive dentro del módulo; sin mapeo de paths externos | REJECT (ídem) |
| pdm-backend | MIT | includes/por-package-data no ofrecen la primitiva limpia de mapeo externo→bundle | REFERENCE |
| uv-build | Apache-2.0/MIT | backend joven (2025), pensado para workspaces uv; data inclusion limitada hoy | REFERENCE |

**Decisión: ADOPT hatchling** (`[build-system] requires =
["hatchling"]`). La expectativa registrada en la task (hatchling
probable ADOPT) queda confirmada por el scan: `force-include` es
exactamente la primitiva que el fallo exige.

## 4. Runtime evidence bundle (contenido mínimo congelado)

Sólo lo que las superficies públicas necesitan — no los raws ni
toda la evidencia histórica (~5 MB):

```text
finreg_es/                          paquete core (stdlib-only)
adapters/                           superficies + _data

adapters/_data/fixtures/
  contracts/*.json
  g1/derived-assertions-g1-e-002.json
  g2/events/*.json
  g3/projection/finreg-g3.sqlite
  g3/projection/manifest.json
```

Los ficheros son los originales del repo, incluidos byte-for-byte
por el backend en build; **no** se crean copias versionadas en el
source tree.

## 5. Resolución de paths (vive exclusivamente en adapters/)

```text
path explícito del usuario   → usar exactamente ese path
default + checkout           → <repo>/fixtures/...
default + wheel instalado    → <site-packages>/adapters/_data/fixtures/...
```

`finreg_es/` permanece congelado y stdlib-only: la detección
(bundle presente junto a `adapters/` ⇒ wheel; si no, repo root)
vive en `adapters/common.py`. En checkout el comportamiento actual
no cambia.

## 6. Propiedad byte-equality (binding)

```text
sha256(fixture en repo) == sha256(mismo fichero en wheel)
                        == sha256(fichero instalado)
```

Consecuencia verificable: `evidence_set_id` (`<stem>@sha256:…`)
tras instalar es idéntico, y el `.sqlite` instalado conserva su
`logical_projection_sha256`. Si el packaging cambia un byte, el
gate falla.

Reproducibilidad del propio wheel: el gate contractual es
igualdad de content manifest + sha256 por fichero; si hatchling
produce además el mismo wheel SHA en build ×2, se registra como
evidencia adicional — igual que con el `.sqlite`, el byte del
contenedor no es el requisito semántico.

## 7. Ejecutable público

```toml
[project.scripts]
finreg = "adapters.entrypoint:main"
```

`adapters/entrypoint.py`: shim mínimo stdlib-only —

```text
typer instalado   → delega en adapters.cli:main()
typer ausente     → error estructurado en stderr
                    {"error": {"code": "missing_extra",
                     "message": "instale finreg-es[cli]"}}
                    + exit != 0   (nunca un traceback)
```

`project.dependencies` permanece `[]`: el wheel base instala con
cero dependencias y no deja un console script roto. MCP sigue
siendo `finreg-es[mcp]` vía `python -m adapters.mcp_server` — no se
inventa un segundo ejecutable sin necesidad real.

## 8. Acceptance criteria de E1 (binding)

```text
✓ wheel + sdist construidos desde clean checkout
✓ build ×2: mismo content manifest (mismo wheel SHA = evidencia
  adicional si el backend lo consigue)
✓ venv nuevo, fuera del repo; instala el WHEEL (no pip -e)
✓ `import finreg_es` con cero dependencias externas
✓ `finreg` base sin [cli] → error limpio indicando el extra
✓ con [cli]: `finreg --help` + una query E0 real PASS
✓ con [mcp]: discovery + query PASS
✓ evidence_set_id instalado == evidence_set_id del repo
✓ `changes` funciona desde los events incluidos
✓ logical_projection_sha256 del .sqlite instalado == manifest
✓ ningún path de salida depende del checkout original
✓ full suite + G2-F replay + G3-D smoke siguen verdes
```

## 9. Resultados válidos (declarados antes de observar)

```text
PASS       todos los criterios E1 cumplidos
QUALIFIED  cumplidos con una limitación concreta declarada
FAIL       el bundle no reproduce los artefactos/veredictos —
           o hace falta tocar finreg_es/ para conseguirlo
```

## 10. Cierre (E2)

`docs/G3-FINAL-REPORT.md` con veredicto por workstream, cadena
autoritativa y límites declarados; `docs/g3-scope.md` →
`CLOSED / PASS`; tag anotado `g3-consumability-closed`.

## 11. Fuera de alcance de G3-E

- Publicación a PyPI/registries (distribución, no consumibilidad).
- Más ejecutables, installers, installers OS-level, containers.
- Mutar `finreg_es/` para empaquetar.
