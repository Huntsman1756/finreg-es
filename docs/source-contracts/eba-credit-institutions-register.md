# EBA — Credit Institutions Register

Contrato: `fixtures/contracts/eba-credit-institutions-register.json`

- **Qué acredita**: listado de entidades de crédito del EEE (CRD IV art. 10 — H3: verificar
  campos publicados, p. ej. LEI y permiso de captación de depósitos).
- **Complementariedad con PSD2**: exactamente el complemento del registro PSD2; juntos no
  forman sin embargo una enumeración completa de "prestadores de servicios de pago"
  (ver nota siguiente).
- **Lag entre fuentes (C2)**: el fixture asm-009 modela un CIR aún activo para una entidad
  revocada en BdE (asm-008). Política congelada: efectos legales opuestos admisibles ⇒
  `INDETERMINATE`, con ambos claims en `assertions` y `response_freshness = min(...)`.
- **Negativos**: `EXPLICIT_NEGATIVE_ONLY` (completitud y cadencia sin verificar, H3).
- **No sustituye al registro nacional**: la autorización nacional es el hecho primario; el
  CIR es corroboración EU con su propio perfil de staleness.
