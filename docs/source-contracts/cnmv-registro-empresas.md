# CNMV — Registros de empresas (ESI / EAF / gestoras)

Contrato: `fixtures/contracts/cnmv-registro-empresas.json`

- **Qué acredita**: inscripción y situación de ESI, EAF y sociedades gestoras, incluidas
  entidades extranjeras que operan en España en sucursal o en libertad de servicios (H6).
- **Qué NO acredita**: clases bancarias y de pago (BdE), servicios cripto (listado MiCA).
- **Negativos**: solo estados explícitos. Los listados inbound FPS se consideran
  **no-enumerativos** hasta verificar H6 (W3): la ausencia de una entidad lituana en el
  listado de extranjeras no demuestra nada.
- **Etiquetas del listado**: no se deriva el mecanismo jurídico de etiquetas simplificadas
  (premisa del encargo); el ground truth de G0.5 se determina manualmente contra fuente
  primaria.
- **Temporalidad**: `source_as_of` pendiente (H8); el fixture de aserciones demuestra el caso
  `UNAVAILABLE` (asm-007): `freshness_at` cae a `retrieved_at`.
