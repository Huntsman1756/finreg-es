---
name: preregister-gate
description: Preregistrar un gate/workstream de FinReg antes de implementarlo — criterios de éxito/fallo, casos esperados y artefactos, publicados antes de escribir producción.
---

# preregister-gate

Usar antes de cualquier gate nuevo o capacidad con criterios
evaluables. El preregistro va en `docs/` y se commitea/pushea ANTES
de implementar.

## Procedimiento

1. Definir el fallo o propiedad concreta que el gate demuestra
   (una frase falsable, no una aspiración).
2. Fijar criterios de éxito/fallo medibles y casos preregistrados
   (B01…, E01…, etc.) con resultados esperados.
3. Declarar artefactos objetivo y schemas que habrá que versionar.
4. Declarar explícitamente qué resultados son válidos (incluido
   "0 cambios" / "NOT_REPRESENTABLE") para que el objetivo no se
   mueva tras ver los datos.
5. Commit + push del documento antes de cualquier código.

## Anti-reglas

- Nunca ajustar criterios preregistrados tras observar resultados:
  si el contrato era incorrecto → finding + sucesor documental.
- Nunca implementar producción antes del preregistro publicado.
