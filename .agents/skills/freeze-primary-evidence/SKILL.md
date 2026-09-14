---
name: freeze-primary-evidence
description: Capturar y congelar una observación de fuente primaria — manifiesto nuevo con retrieved_at por item, SHA sobre bytes descargados, source_as_of leído de la fuente, sin reinterpretar históricos.
---

# freeze-primary-evidence — adquisición de snapshots

Usar para capturar fuentes oficiales (EBA, BdE, ESMA, CNMV, …).

## Procedimiento

1. Descargar bytes de la URL oficial declarada en el source contract
   (`fixtures/contracts/`).
2. Calcular SHA-256 sobre los bytes descargados. Si el SHA ya existe
   en una observación anterior → mismo `content_id`: NO duplicar el
   fichero; registrar sólo la nueva observación en el manifiesto.
3. `source_as_of` se lee de la fuente (fecha declarada, metadata
   publicada, contenido del fichero) — nunca se hereda de
   observaciones previas ni se infiere de `retrieved_at`.
4. `retrieved_at` por item (formato G2); nunca reutilizar el de un
   manifiesto anterior como proxy de una nueva captura.
5. Manifiesto nuevo e independiente en `fixtures/g<N>/sources/`;
   los manifiestos históricos no se modifican.
6. Verificar contra hash publicado por la fuente cuando exista
   (p.ej. EBA publica `.sha256`).
7. Registrar `succession_state` respecto a la observación previa
   (contrato §9) sin interpretación jurídica.

## Anti-reglas

- Git history no es source history: el timestamp de commit nunca se
  convierte en `retrieved_at`.
- Una re-extracción de bytes históricos NO es una nueva observación:
  es mismo `content_id` + nueva `normalization_version`.
