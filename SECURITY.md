# Política de seguridad

## Versiones soportadas

La versión pública de referencia es la pre-release `v0.0.1`. `main` puede contener cambios posteriores de mantenimiento y documentación, pero no implica soporte productivo ni SLA.

## Reportar una vulnerabilidad

Usa la funcionalidad de reporte privado de GitHub
(**Security → Advisories → Report a vulnerability**) en lugar de un
issue público.

El sistema es local/read-only y el paquete base no tiene dependencias runtime externas, por lo que la superficie de ataque es acotada. Se consideran especialmente relevantes:

- Manipulación de snapshots congelados o de los SHA-256 que los anclan.
- Defectos que permitan emitir una aserción positiva sin claim trazable (ruptura de la invariante fail-closed).
- Vulnerabilidades en la cadena de tooling, packaging, fixtures, schemas o CI.
- Vulnerabilidades en las superficies opcionales CLI/MCP/Datasette o en el runtime evidence bundle.

Incluye, si es posible, versión/tag afectado, commit, pasos mínimos de reproducción e impacto observado. Evita publicar secretos, datos personales o detalles explotables en issues públicos.

Se dará acuse y evaluación en la medida de lo posible. Gracias por reportar de forma responsable.
