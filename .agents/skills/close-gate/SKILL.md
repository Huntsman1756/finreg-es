---
name: close-gate
description: Cerrar formalmente una fase/gate de FinReg — verificar criterios preregistrados, documentar veredicto por hipótesis, límites declarados, tag anotado, estado congelado.
---

# close-gate — cierre formal de fase

Usar cuando una fase cumple sus criterios preregistrados y se decide
cerrarla (patrón G0/G1: FINAL-REPORT + scope actualizado + tag).

## Procedimiento

1. Releer el scope y verificar cada criterio preregistrado contra
   evidencia (runs, tests, CI run id, hashes de cadena autoritativa).
2. Documentar veredicto por hipótesis/caso preregistrado
   (PROVEN / PROVEN WITH QUALIFICATION / DISPROVEN…).
3. Declarar límites abiertos explícitamente — son límites
   declarados, no deuda escondida.
4. Actualizar el scope doc a `CLOSED / PASS` con veredictos finales.
5. Crear `docs/G<N>-FINAL-REPORT.md` con cadena autoritativa
   (artefactos, rulesets, SHAs) y evidencia de calidad.
6. Commit de closeout + tag anotado + push + verificar CI real
   (run id del workflow correcto, no un workflow auxiliar).
7. Tras el tag: la fase no se reabre salvo defecto reproducible.

## Reglas

- No cerrar con criterios "casi" cumplidos: un criterio incumplido
  es un límite declarado o un motivo para no cerrar.
- Verificar CI del workflow correcto; un success en otro workflow
  (Dependabot, auxiliares) no es evidencia de CI verde.
