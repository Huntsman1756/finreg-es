# Política de seguridad

## Versiones soportadas

Este es un estudio de caso sin releases: sólo `main` está soportada.

## Reportar una vulnerabilidad

Usa la funcionalidad de reporte privado de GitHub
(**Security → Advisories → Report a vulnerability**) en lugar de un
issue público.

El sistema es offline y sin dependencias runtime, por lo que la
superficie de ataque es pequeña. Lo que sí se considera relevante:

- Manipulación de snapshots congelados o de los sha256 que los anclan.
- Defectos que permitan emitir una aserción positiva sin claim
  trazable (ruptura de la invariante fail-closed).
- Vulnerabilidades en la cadena de tooling (fixtures, schemas, CI).

Recibirás acuse y una evaluación en la medida de lo posible. Gracias
por reportar de forma responsable.
