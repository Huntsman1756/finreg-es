---
name: audit-divergences
description: Auditar divergencias entre ejecuciones, artefactos sucesores o mutantes — replay determinista, clasificación de supervivientes, cero cambios silenciosos.
---

# audit-divergences

Usar para auditorías de replay, comparación de artefactos sucesores
y auditorías de mutación (patrón G0.7-C / E6).

## Procedimiento

1. Definir qué dos ejecuciones/artefactos se comparan y bajo qué
   versión de semántica.
2. Ejecutar replay: mismos inputs → mismos bytes (verificar por
   hash canónico, no por inspección).
3. Toda divergencia se clasifica: defecto reproducible, equivalente
   documentado, o cambio semántico esperado con sucesor declarado.
4. En mutation testing: cada superviviente se clasifica
   (equivalente / cosmético / no observable); ninguno se "mata"
   cambiando semántica de producción para mejorar el score.
5. Emitir evidencia: conteos, clasificación por mutante/divergencia,
   artefacto de auditoría congelable.

## Reglas

- Cero divergencias no clasificadas.
- La remediación nunca sobrescribe el artefacto histórico.
- Un mutante superviviente equivalente se documenta, no se oculta.
