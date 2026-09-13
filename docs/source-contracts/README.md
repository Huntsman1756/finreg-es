# G0.1 — Contratos de fuentes

Cada fuente tiene (a) un contrato máquina-legible en `fixtures/contracts/*.json` y (b) una
ficha narrativa aquí. El contrato es la unidad congelada; la ficha explica decisiones y
pendientes.

## Campos del contrato

| Campo | Significado |
|-------|-------------|
| `authority` / `register_name` / `official_url` | Identificación de la fuente. |
| `legal_basis` | Base jurídica del registro (artículo concreto cuando esté verificado). |
| `entity_classes_covered` / `excluded_entity_classes` | Clases cubiertas y **excluidas explícitamente** (p. ej. bancos fuera del registro PSD2). |
| `activities_covered` | Actividades del vocabulario G0 que el registro acredita. |
| `jurisdictions` / `territorial_regimes` | Ámbito geográfico (`ES` o `EEA`) y regímenes territoriales. |
| `update_cadence` | Cadencia declarada/observada; `UNKNOWN` si no verificada (H4/H7/H8). |
| `max_positive_staleness_days` / `max_negative_staleness_days` | **Política propia** de FinReg (estado `PROPOSED`), no hecho de la fuente. Los negativos caducan estrictamente antes que los positivos. |
| `supports_source_as_of` | ¿La fuente declara fecha de actualización? `null` = pendiente de verificar. Si es `true`, exige verificación `VERIFIED` con URL. |
| `negative_evidence_capability` | `COMPLETE_ENUMERATION` \| `EXPLICIT_NEGATIVE_ONLY` \| `NO_NEGATIVE_INFERENCE`. |
| `identity_fields` | Campos identificativos que la fuente aporta (mínimo `legal_name`). |
| `raw_format` / `supports_bulk_snapshot` | Formato bruto y capacidad de snapshot masivo (prerequisito de negativos por enumeración). |
| `coverage_rules` | Reglas `IN`/`OUT` que materializan la matriz G0.3 por registro. |
| `verification` | Estado por campo: `VERIFIED` (exige `source_url`), `PENDING` (hipótesis H1–H8), `PROPOSED` (decisión política propia). |

## Regla de capacidad negativa

`negative_evidence_capability` **nunca** se asigna por defecto a `COMPLETE_ENUMERATION`:

- **BdE y CNMV**: `EXPLICIT_NEGATIVE_ONLY`. `RATIONALE: no complete, authoritative
  enumeration suitable for negative inference has yet been verified.` No se afirma que la
  fuente sea "solo-consulta": BdE publica datos identificativos, histórico/variaciones y
  listas CSV de determinadas clasificaciones. Lo que falta demostrar (H8) es que exista un
  volcado completo, jurídicamente adecuado y exhaustivo del registro necesario para sostener
  negativos de FinReg. Si H8 lo verifica, la capacidad se promueve a `COMPLETE_ENUMERATION`
  sin cambiar el modelo.
- **Listado MiCA CNMV**: `NO_NEGATIVE_INFERENCE` — lag respecto de ESMA, completitud sin
  verificar y posibles omisiones de entidades financieras por notificación (H1/H2).
- **Registros EBA/ESMA**: `EXPLICIT_NEGATIVE_ONLY` en G0; upgrade a
  `COMPLETE_ENUMERATION` solo cuando G0.5 verifique descarga masiva + completitud del feed.
- La ausencia en un registro se interpreta como `NO_ENTITLEMENT_EVIDENCED`, jamás como
  `CONFIRMED_NOT_AUTHORISED` (G0.3).

## Registro PSD2 y entidades de crédito (W2)

El registro EBA PSD2 excluye a las entidades de crédito (Reg. (UE) 2019/518; marco único
CRD). La regla `eba-psd2-out-credit-institutions` hace que `coverage(...)` devuelva
`OUT_OF_SCOPE` para bancos: ninguna inferencia negativa ni positiva puede originarse ahí
para esa clase. Que un banco no figure en PSD2 **no dice nada** sobre sus servicios de pago.

## Fichas

- `bde-registro-entidades.md`
- `cnmv-registro-empresas.md`
- `cnmv-mica-casp.md`
- `eba-psd2-register.md`
- `eba-credit-institutions-register.md`
- `esma-mica-register.md`
- `home-state-authorities.md`
