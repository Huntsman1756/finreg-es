# Source Capability Matrix — Regulatory Record ES (G4)

Auditado el 2026-09-18. "Probed" = verificado en vivo en esta sesión;
"contract" = ya cubierto por `fixtures/contracts/*`; "upstream" = consumido
vía artefacto de otro repo del autor (ver `G4-REUSE-MATRIX.md`).

Leyenda de evidencia temporal:
`as-of declared` = la fuente declara la fecha de situación servida ·
`as-of queryable` = acepta fecha y reconstruye estado ·
`observed-only` = sólo sabemos lo que vimos cuando lo vimos ·
`windowed` = registro vivo con ventana limitada (p. ej. sanciones).

## CNMV

| Superficie | URL/patrón | Estado | Temporalidad | Notas |
|---|---|---|---|---|
| ESI nacionales — ficha | `Portal/Consultas/ESI/esis.aspx?nif={nif}&vista={n}` | **probed** | observed-only | `vista=0..17`: datos generales, administradores(4), socios(7), agentes(8), sucursales ES(9), EEE, no-EEE, LPS EEE, LPS no-EEE, programa(17), atención cliente, auditorías. `fs` → **HTTP 400** (param rechazado) |
| ESI extranjeras LPS | `ESI/esisextranjeraslp.aspx?tipo=CLP&numero={n}` | **probed** | observed-only | `fs` aceptado pero **ignorado**: sólo se ecoa en canonical/hreflang; texto visible idéntico |
| ESI extranjeras sucursal | `ESI/esisextranjeras...aspx` (familia) | pending | — | mismo patrón probable |
| SGIIC (gestoras IIC) | `iic/sgiic.aspx?nif={nif}` | **probed** | **`fs` honored** | `fs=01/01/2015` devuelve dirección y capital históricos distintos; sin input de fecha visible en la página |
| IIC (SICAV/sociedades) | `iic/sociedadiic.aspx?nif={nif}&vista={n}&fs={dd/mm/yyyy}` | **probed** | **`fs` honored + fecha declarada** | input `wFecha$txtFecha` muestra la fecha servida; `fs=08/06/2020 ≡ fs=09/06/2020` (nearest-before); `fs` pre-registro no error (comportamiento degenerado por medir) |
| ECR gestoras | `ecr/gestora.aspx?nif={nif}` | pending | probable `fs` (familia ecr/) | listado `listadoentidad.aspx?id=4&tipoent=0` |
| Listados | `listadoentidad.aspx?id={fam}&tipoent={n}` | probed | current enumeration | id=1 ESI-family, id=2 SGIIC, id=4 ECR-gestoras; HTML denso, paginación por repeater |
| Búsqueda unificada | `BusquedaPorEntidad.aspx` | pending | — | postback ASP.NET; resolver nombre→(nif, familia) |
| Sanciones | registro sanciones CNMV | pending | **windowed** | ventana móvil: una sanción que sale del registro ≠ nunca existió |
| Advertencias ("chiringuitos") | WebAPI `PaffNoAutorizadas` | **upstream AlertaFin** | snapshot+provenance | dataset `g0/normalized/notices.jsonl` con notice_id estable |
| MiCA CASP list | `portal/consultas/criptoactivos.aspx` | contract | observed-only | contrato `cnmv-mica-casp-list.json` |

**Veredicto preliminar `fs`** (detalle: `CNMV-HISTORICAL-SURFACE.md`):
es una capacidad **real pero limitada a la familia IIC/ECR**, con semántica
nearest-before, no una "API histórica" general de CNMV. Las fichas ESI no la
aceptan. Ninguna vista probada enumera explícitamente snapshots disponibles.

## Banco de España

| Superficie | Estado | Temporalidad | Notas |
|---|---|---|---|
| Registro de entidades (CSV `utf-8-sig`) | contract | observed-only + `fecha de referencia` declarada | **clasificación estadística, no autorización** (regla congelada) |
| Registro servicios de pago (XLSX) | contract | observed-only | actividades declaradas por fuente |
| Registro con establecimiento | contract | observed-only | — |
| Históricos/variaciones de registro | pending | BdE publica "variaciones" con fecha — candidato a eventos oficiales | verificar cobertura real en G0 |
| Oficinas/sucursales | pending | — | — |

## EBA

| Superficie | Estado | Temporalidad | Notas |
|---|---|---|---|
| PSD2 register (JSON EAV, zip ~20MB) | contract | snapshots completos; diff estructural ya probado (G2-B) | entidades PSD2 salvo crédito y CASP; NCA provenance por registro |
| Credit Institutions Register | contract | observed-only | metadatos de registro |

## ESMA

| Superficie | Estado | Temporalidad | Notas |
|---|---|---|---|
| MiCA CASP register (CSV) | contract | observed-only | presencia ≠ evidencia negativa (regla H1) |

## DGSFP / EIOPA / BdE-Eurosystem / GLEIF (seguros)

| Superficie | Estado | Temporalidad | Notas |
|---|---|---|---|
| Crosswalk completo | **upstream OpenDGSFP** | snapshot + export versionado | `data/derived/v0.1/opendgsfp-0.1.jsonl`; EXACT/CONFLICT/UNRESOLVED; passporting first-class |

## GLEIF (transversal)

| Superficie | Estado | Temporalidad | Notas |
|---|---|---|---|
| LEI reference data | contract + upstream | LEI status con fechas oficiales; field-level history parcial | complementa identidad; no es autorización |

## BOE

| Superficie | Estado | Temporalidad | Notas |
|---|---|---|---|
| Documentos BOE (sanciones, resoluciones, altas/bajas) | **upstream official-sources-esp** | `published_at` oficial por documento | candidatos a `OFFICIAL_EVENT`/`OFFICIAL_DOCUMENT_DERIVATION`; **name-only joining prohibido** — se requiere identificador exacto o adjudicación |
| Legislación consolidada | upstream | — | contexto normativo |

## Reglas de uso ya derivadas

1. `fs` CNMV sólo se cita como `OFFICIAL_AS_OF_STATE` en superficies que lo
   honran **y** declaran la fecha servida (familia IIC/ECR). Donde se ignora o
   rechaza, la evidencia es `observed-only`.
2. Ningún dato histórico reconstruido vía `fs` se convierte en evento fechado:
   es un *estado a fecha*, no un *evento con fecha jurídica*.
3. Sanciones CNMV: el registro vivo es `windowed`; la historia verificable se
   extiende con BOE (documento fechado), nunca inferiendo vacío.
4. BdE CSV = clasificación estadística: prohibido promoverlo a autorización
   (regla congelada de FinReg).
5. Listados CNMV `listadoentidad` son enumeración **actual**; sirven de
   universe pero no de historia.
