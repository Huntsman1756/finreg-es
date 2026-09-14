---
name: oss-scan
description: Scan OSS failure-driven obligatorio antes de implementar infraestructura genérica — candidatos, licencia, mantenimiento, prueba real, decisión ADOPT/WRAP/PORT_PATTERN/REFERENCE/REJECT.
---

# oss-scan — evaluación failure-driven

Obligatorio antes de escribir cualquier pieza de infraestructura
genérica (diffing, parsing, identity, storage, provenance export…).
Regla: `docs/adr-oss-scan-failure-driven.md`.

## Procedimiento

1. Enunciar el fallo concreto (qué se rompe sin la pieza).
2. Separar qué es semántica propia (FinReg la conserva) de qué es
   genérico (candidato a reutilizar).
3. Buscar GitHub/GitLab por el fallo; inspeccionar 5–10 candidatos.
4. Por candidato: licencia, mantenimiento (releases/issues),
   calidad de tests, arquitectura, offline/determinismo, encaje.
5. Medir contra un caso REAL del repo, no contra el README.
6. Decidir y documentar: ADOPT | WRAP | PORT_PATTERN | REFERENCE
   | REJECT, con la medición.

## Reglas

- No adoptar por popularidad; adoptar por gate.
- Ninguna librería decide una cuestión jurídica/regulatoria.
- ADOPT en runtime exige justificar romper stdlib-only; la opción
  por defecto es tooling-extra u oráculo de tests.
