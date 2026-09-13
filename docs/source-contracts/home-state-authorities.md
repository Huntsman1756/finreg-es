# Autoridad home-state (plantilla + instancias)

Contrato plantilla: `fixtures/contracts/home-state-authority-template.json`

- **Cuándo se necesita**: entidades inbound cuya autorización de origen debe confirmarse en
  el Estado miembro de origen (p. ej. EMI lituana → Lietuvos Bankas; ESI francesa → ACPR).
- **Qué aporta**: el hecho de la autorización de origen, su alcance y sus límites. **No**
  sustituye al marco español para el régimen territorial en ES; para el pasaporte, los
  registros EU (EBA/ESMA) son la fuente agregada.
- **Instanciación**: G0.5 creará un contrato por cada NCA home usada en el corpus,
  documentando formato bruto, capacidad de snapshot y disponibilidad de `source_as_of`
  (si no existe: `reliability = UNAVAILABLE`, `freshness_at = retrieved_at`).
- **Identidad**: `HOME_STATE_ID` es el identificador estable del registro de origen; para
  entidades extranjeras el NIF español no existe, y el LEI es nullable.
