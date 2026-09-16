## Resumen

<!-- Qué cambia y qué defecto reproducible o consumidor concreto lo justifica -->

## Evidencia / alcance

<!-- Preregistro, issue, FINAL-REPORT o evidencia oficial que delimita el cambio -->

## Test plan

- [ ] `python -m pytest` en verde
- [ ] Artefactos congelados regenerados desde su entrypoint (no editados a mano)
- [ ] Ningún fallo de derivación inventa una aserción positiva
- [ ] Sin dependencias runtime nuevas en `finreg_es/` (stdlib-only)
- [ ] Provenance y determinismo preservados
- [ ] Si añade infraestructura genérica: scan OSS failure-driven realizado
- [ ] Sin secretos, credenciales ni datos personales en el diff

## Compatibilidad / límites

<!-- Indica cambios de payload, packaging, superficies públicas o límites conocidos; "ninguno" si no aplica. -->
