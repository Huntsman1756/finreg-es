# Post-G0 — evaluación Frictionless (sin implementación)

Evaluación acotada, **sin tocar runtime**. Pregunta preregistrada:

> ¿Frictionless aporta un contrato tabular interoperable sobre las
> fuentes BdE/EBA/CNMV/ESMA sin duplicar `SourceContract`?

Frontera preregistrada: `SourceContract` = autoridad FinReg de semántica
(cobertura, evidencia negativa, staleness, base jurídica). Frictionless
sólo podría ser representación estructural tabular — nunca reemplazo.

## Criterio de decisión preregistrado

```text
ADOPT        representa fielmente las fuentes probadas
             Y elimina trabajo estructural real sin duplicar semántica.
WRAP/EXPORT  aporta interoperabilidad, SourceContract sigue siendo SSOT.
REJECT       sólo crea una segunda descripción de las mismas columnas
             sin consumidor ni beneficio demostrable.
```

## Método

`frictionless 5.19.0` (instalado sólo para la evaluación; no es
dependencia del proyecto ni del extra `tooling`). `describe`/`validate`
sobre los snapshots congelados reales.

## Evidencia por fuente

### 1. EBA PSD2 — `h4-eba-psd2-20260913.zip` (19,9 MB)

El payload es `download-PSDMD-*.json` de **218 MB**: array de arrays de
objetos con estructura EAV anidada (`Properties: [{ENT_NAM: ...}, ...]`,
`Services: [{ES: "PS_03C"}]`). **No es tabular.**

- `describe` → `type: json`, sin schema ni fields.
- Un Table Schema requeriría primero la proyección entidad→fila — que
  *es* el adapter FinReg. Frictionless no elimina trabajo estructural:
  el trabajo estructural ya está hecho y el descriptor lo presupondría.
- Veredicto parcial: **no representable**.

### 2. BdE MFI — `h8-bde-mfi-es.csv` (243 kB)

CSV real: `utf-8-sig` (BOM), separador `,`, última cabecera con padding
de ~120 espacios.

- `describe` → schema limpio: 8 fields `string`, encoding correcto.
- `validate` → PASS, 0 errores.
- **Pero** Frictionless *normaliza silenciosamente* el header:
  `CÓDIGO DE SUPERVISOR` aparece sin padding. El descriptor describe la
  tabla lógica, no los bytes — el quirk que FinReg registra como
  `COPY_OR_EMPTY` desaparece del modelo.
- Veredicto parcial: representable, con normalización oculta.

### 3. ESMA MiCA CASPs — `h7-esma-casps.csv` (167 kB) — la fuente sucia

CSV real: `utf-8-sig`, **coma final en cada fila** (columna 16 vacía),
celdas multivalor separadas por `|`, fechas `dd/mm/yyyy`.

- `describe` → 16 fields; el fantasma aparece como `field16: any`.
- `validate` → **FAIL**: `blank-label` en la posición 16. Detecta suciedad
  estructural real — aunque FinReg ya la conoce y la tolera.
- `ac_serviceCode`/`ac_serviceCode_cou` multivalor `|`: Table Schema no
  tiene tipo para ello (`array` espera texto JSON); fiel = `string` +
  regla FinReg. La semántica de splitting sigue siendo nuestra.
- `authorisationEndDate` vacío→null sí es expresable (`missingValues`),
  y `dd/mm/yyyy` vía `date` + `format` — puntos genuinamente cubiertos.
- Veredicto parcial: representable con caveats declarados.

### Fuera de muestra — CNMV ESI FPS

`h6-cnmv-esi-fps.html` (1,9 MB): HTML de detalle sin `<table>`, parseado
por regex sobre spans. Fuera del dominio de Frictionless — la frontera
no es hipotética.

## Medición contra criterios

| Criterio | Resultado |
|----------|-----------|
| Schema expressiveness | **Parcial (2/4)**. CSVs sí, con normalizaciones/caveats; EBA JSON y CNMV HTML no |
| Validation | Detecta `blank-label` (real, ya conocido); en BdE nada nuevo; en EBA nada tabular |
| Round-trip | No: describe tabla lógica, no bytes. La fidelidad byte-exacta ya la da el manifest sha256 |
| Duplication | Nombres/tipos/nulls duplican lo estructural de `SourceContract`+`FIELD_TRACES`; lo semántico sigue inexpresable |
| Integration cost | `frictionless` 5.x arrastra dependencias pesadas (pydantic, jinja2, tabulate, typer, requests…) para un export marginal; hand-written descriptors = ~30 líneas × 2 CSVs |
| Interoperability value | Bajo hoy: **ningún consumidor** Frictionless; 2 de 4 fuentes describibles, ambas con notas |

## Veredicto

```text
REJECT (ahora), con WRAP/EXPORT documentado como la forma
que tomaría si aparece un consumidor real.
```

Motivo literal del criterio preregistrado: crearía una segunda
descripción de las mismas columnas sin consumidor ni beneficio
demostrable, y no cubre 2 de las 4 fuentes reales (la mayor, EBA PSD2,
ni siquiera es tabular).

Si algún día un portal/catálogo consume Frictionless: el export es
trivial para el subconjunto CSV (`BdeMfi`, `EsmaCasps`), declarando
explícitamente la columna fantasma y el padding normalizado. Coste
estimado: descriptores hand-written, cero dependencia runtime — como el
piloto OpenLineage.

## Lo que NO se hizo

- Ningún cambio en `finreg_es/`, `SourceContract` ni parsers.
- `frictionless` no entra en `pyproject.toml` ni en el extra `tooling`
  (instalación local de evaluación, removida tras la medición).
