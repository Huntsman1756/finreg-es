# CNMV — Listado MiCA (CASPs)

Contrato: `fixtures/contracts/cnmv-mica-casp-list.json`

- **Por qué es un contrato separado**: su debilidad es de identidad, no de cobertura. Si el
  listado no publica NIF, LEI ni número estable (H2, premisa del encargo), sus
  `identity_fields` son solo `legal_name`.
- **Consecuencia G0.2**: toda resolución de identidad que parte de este listado produce
  `AMBIGUOUS` (al menos `SINGLE_CANDIDATE_NAME_MATCH`). El pipeline debe pasar por
  `ESMA_MICA_REGISTER` (fuente portadora de identificadores) y adoptar identificadores
  mediante `adopt_identifiers_from_source` (regla W6), o acudir a la autoridad home-state.
- **Capacidad negativa**: `NO_NEGATIVE_INFERENCE`. La ausencia en el listado no permite
  concluir nada: lag respecto de ESMA, completitud sin verificar, y posible no-inclusión de
  entidades financieras que prestan CAS por notificación (H1).
- **Temporalidad (C4)**: los regímenes transitorios MiCA tienen fecha de cierre (H1:
  verificar). Las aserciones heredadas llevan `effective_to`; vencida la ventana, el
  assessment produce `NO_ENTITLEMENT_EVIDENCED` (o `INDETERMINATE` si la evidencia es
  conflictiva), nunca `CONFIRMED_NOT_AUTHORISED` automático (fixture asm-006, escenario S7).
