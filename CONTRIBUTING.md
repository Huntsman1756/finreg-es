# Contribuir

Gracias por el interés. Este repositorio es un estudio de caso de
ingeniería de datos regulatoria: antes de proponer cambios, lee el
`README.md` y los docs de `docs/` para entender las invariantes del
proyecto.

## Setup y verificación

```bash
python -m pytest                          # suite completa, offline
pip install "jsonschema>=4.21,<5"         # sólo para tests/schemas (tooling)
python -m finreg_es.openlineage_export    # regenera openlineage/ byte-idéntico
```

Sin servicios, sin red, sin credenciales. Todo input es un fichero del
repo; todo output es un artefacto hash-fijado.

## Convenciones no negociables

- **Determinista**: mismos inputs → mismos bytes. Toda serialización
  pasa por `canonical.py` (`FINREG_CANONICAL_JSON_V1`).
- **Fail-closed**: evidencia insuficiente produce un finding
  clasificado, nunca una aserción positiva inventada.
- **Stdlib-only en runtime**: `finreg_es/` no puede depender de nada
  externo (hay un test que lo fija). `jsonschema` es tooling-only.
- **Provenance**: toda afirmación emitida es trazable a un snapshot
  congelado por sha256. No se afirma nada sin claim.
- **No se reescribe la historia**: un artefacto o run defectuoso se
  conserva; la remediación se emite como artefacto/run que lo supersedes
  (ver G05-B-F01, G1-C-F01 en `docs/`).
- **Clasificación ≠ autorización**: no promocionar listados
  estadísticos a evidencia de entitlement.

## Pull requests

- `python -m pytest` en verde.
- Los artefactos congelados sólo cambian regenerándolos desde sus
  entrypoints (`build_*`, `run_assessment`), nunca editados a mano.
- Estilo de commit: `tipo(ámbito): resumen` (ver `git log`).
