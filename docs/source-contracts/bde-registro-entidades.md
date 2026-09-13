# BdE — Registro de entidades

Contrato: `fixtures/contracts/bde-registro-entidades.json`

- **Qué acredita**: autorización e inscripción nacional de entidades de crédito, entidades de
  pago, entidades de dinero electrónico y sus agentes (entre otras secciones — H6/H8).
- **Qué NO acredita**: actividades de ESI/EAF/gestoras (CNMV), servicios sobre criptoactivos
  con autorización CASP (ESMA/CNMV-MiCA), ni prestación inbound por FPS (regla `OUT`).
- **Negativos**: solo estados explícitos de la fuente (baja/revocación), previa verificación
  H5 del vocabulario de estados. `EXPLICIT_NEGATIVE_ONLY` con
  `RATIONALE: no complete, authoritative enumeration suitable for negative inference has yet
  been verified` — no porque la fuente sea "solo-consulta": BdE publica datos
  identificativos, histórico/variaciones y listas CSV de determinadas clasificaciones. H8
  decide si ese volcado es completo y apto para negativos.
- **Identidad**: denominación, NIF, número de registro BdE (estabilidad por verificar, H8),
  LEI cuando la fuente lo publique.
- **Agentes (W1)**: las filas de agente no son entitlement independiente; el assessment exige
  `principal_entity_id`.
- **source_as_of**: pendiente (H8); mientras tanto `freshness_at = retrieved_at` con
  `source_date_reliability = UNAVAILABLE` cuando no se declare fecha.
