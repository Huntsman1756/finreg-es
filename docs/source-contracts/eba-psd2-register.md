# EBA — PSD2 Register

Contrato: `fixtures/contracts/eba-psd2-register.json`

- **Base legal verificada**: Reg. (UE) 2019/518, arts. 16–18 (registro de PSI/PDE y sus
  agentes del EEE; pasaporte por Estado miembro y modalidad sucursal/FPS).
- **Exclusión crítica (W2)**: no incluye entidades de crédito. Codificada como regla `OUT`
  `eba-psd2-out-credit-institutions` + guarda genérica `excluded_entity_classes`. Es el
  ejemplo canónico del enunciado: la ausencia de un banco jamás demuestra que no pueda
  prestar servicios de pago.
- **Fuente clave para cross-border**: para entidades inbound (p. ej. EMI lituana que presta
  en ES), este registro acredita el pasaporte (fixture asm-004: `FREEDOM_TO_PROVIDE_SERVICES`).
- **Negativos**: `EXPLICIT_NEGATIVE_ONLY`. Un negativo por enumeración exige snapshot masivo
  completo + `enumeration_snapshot_sha256` + vigencia dentro de
  `max_negative_staleness_days` (fixtures asm-011: vencido ⇒ `INDETERMINATE`).
- **Pendientes (H4)**: inclusión de AISP registrados, campo LEI, descarga masiva, cadencia.
