# Contribuir

Gracias por el interés. FinReg-ES está en **maintenance/feedback mode**:
se priorizan defectos reproducibles y necesidades de consumidores concretos.
Las nuevas capacidades requieren preregistro antes de tocar producto.

Antes de proponer cambios, lee `README.md`, los informes `docs/G*-FINAL-REPORT.md`
y las invariantes del proyecto.

## Setup y verificación

El paquete base mantiene `dependencies = []`. Desde la raíz del checkout,
crea y activa un entorno virtual con Python 3.11 o posterior.

POSIX (sh/bash/zsh):

```sh
python3 -m venv .venv
. .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows (cmd.exe):

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

Si PowerShell bloquea la activación, usa cmd.exe o ejecuta los comandos
siguientes con `.\.venv\Scripts\python.exe` en lugar de `python`.

En el entorno virtual, instala el extra completo de tests y verifica:

```sh
python -m pip install ".[test]"
python -m pip check
python -m pytest -ra
```

El extra `[test]` incluye los oráculos, las superficies opcionales de G3 y
las herramientas de empaquetado necesarias para la suite completa.
`[tooling]` se conserva por compatibilidad, incluido mutmut (Linux/WSL),
pero no sustituye a `[test]`.

Para verificar regeneración y replay, usa un checkout desechable: el replay
reconstruye artefactos en rutas históricas, no sólo los lee. No lo ejecutes
en un checkout con trabajo en curso. Prepara allí el mismo entorno anterior.

```sh
python -m finreg_es.openlineage_export
python tools/audit_g2f_replay.py
```

Ambos deben regenerar byte-idéntico; no se deben sobrescribir ni publicar
cambios en los artefactos históricos como remediación.

La CI es la referencia final de compatibilidad para Python 3.11, 3.12 y 3.13.

## Convenciones no negociables

- **Determinista**: mismos inputs → mismos bytes cuando el contrato lo exige. Toda serialización canónica pasa por `canonical.py` (`FINREG_CANONICAL_JSON_V1`).
- **Fail-closed**: evidencia insuficiente produce un finding clasificado, nunca una aserción positiva inventada.
- **Stdlib-only en el core**: `finreg_es/` no puede depender de paquetes externos. Las superficies opcionales viven fuera del core.
- **Provenance**: toda afirmación emitida es trazable a un snapshot congelado por SHA-256. No se afirma nada sin claim.
- **No reescribir historia**: un artefacto o run defectuoso se conserva; la remediación se emite como artefacto/run sucesor.
- **Clasificación ≠ autorización**: no promocionar listados estadísticos a evidencia de entitlement.
- **OSS scan antes de construir**: ninguna infraestructura genérica nueva sin un scan failure-driven previo (`docs/adr-oss-scan-failure-driven.md`).
- **Preregistro**: cambios semánticos o de capacidad se preregistran antes de implementación.

## Pull requests

Un PR debe incluir:

- defecto reproducible o consumidor concreto que justifica el cambio;
- `python -m pytest` en verde;
- artefactos congelados regenerados desde sus entrypoints, nunca editados a mano;
- evidencia de que no se rompe determinismo, fail-closed ni provenance;
- scan OSS previo si añade infraestructura genérica;
- cero secretos, credenciales o datos personales en diffs, fixtures o logs.

Estilo de commit: `tipo(ámbito): resumen` (ver `git log`).

Los cambios de mantenimiento documental que no alteran producto pueden ser más
pequeños, pero deben seguir dejando la CI verde.
