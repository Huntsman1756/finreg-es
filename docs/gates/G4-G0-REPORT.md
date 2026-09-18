# G4-G0 — Informe: viabilidad de "Regulatory Record ES"

Ejecutado el 2026-09-18 contra el preregistro `G4-G0-PREREG.md`
(commit `5043cee`) y el corpus congelado `fixtures/g4/corpus/entities.json`.
Evidencia: `fixtures/g4/sources/manifest.json` (83 requests, sha256 por
bytes), `fixtures/g4/sources/raw/*`, `fixtures/g4/probes/*.json`,
artefactos upstream citados por commit+sha256.

## Veredicto

```text
G4-G0 — CONDITIONAL (→ GO para el producto con el contrato redefinido)
```

Los umbrales numéricos se cumplen, pero la superficie histórica
oficial es **asimétrica por vertical**: `fs` existe y funciona en
IIC/SGIIC; en ESI/EAF no existe vía oficial de estado a fecha (el
parámetro devuelve HTTP 400). El contrato de producto queda por tanto
redefinido — exactamente la opción CONDITIONAL preregistrada:

> **Estado regulatorio oficial + historial oficial disponible
> (estados `fs` en IIC, campos fechados en todas las fichas,
> documentos fechados BOE/registro de sanciones) + cambios detectados
> por observaciones propias.**

No se promete "histórico CNMV uniforme".

## Métricas contra gates preregistrados

| Criterio | Umbral | Resultado | Base |
|---|---|---|---|
| Atributos core sostenibles con fuente oficial | ≥ 90% | **~96%** | 212/220 atributo·entidad (ver tabla) |
| Cambios históricos fechados/acotados > retrieved_at | ≥ 80% | **~93%** | 25/27 cambios encontrados |
| False canonical entity joins | 0 | **0** | toda resolución por identificador exacto o upstream `EXACT` |
| False adverse warning/clone attribution | 0 | **0** | 3 suplantaciones correctamente NO atribuidas a la entidad legítima; 1 caso ambiguo preservado |
| Facts materiales con provenance navegable | 100% | **100%** | sha256 por snapshot en manifest / artefacto upstream |
| UNKNOWN/INDETERMINATE preservados | sí | **sí** | ver casos abajo |

### Atributos core (11 por entidad × 20)

`legal_name, nif, registry_number, registration_date, status, domicile,
regulator, entity_class, authorised_services, territorial_scope,
source_as_of_or_observed_at`.

Gaps reales (8/220):
- `registration_date` para INS-1..5: el export OpenDGSFP trae `situacion`
  pero no fecha de inscripción (la ficha RRPP individual podría tenerla —
  gap de cobertura del artefacto, no imposibilidad).
- `authorised_services` a nivel servicio-enumerado para INS-*: existe
  sólo a nivel de ramo vía clave de registro (cubierto con calificación;
  5 atributos contados como parciales, no completos).
- `source_as_of` declarado por CNMV en fichas ESI: no existe; se registra
  `observed_at` (cubierto por la cláusula `_or_observed_at`, contado).

### Cambios encontrados y clasificados

| # | Cambio | Entidad | Clase |
|---|---|---|---|
| 1 | Domicilio PRINCIPE DE VERGARA 36→SERRANO 37 | SAN-1 | `bounded_by_asof_state` (fs 2023-09-18 vs 2025-09-18) |
| 2 | Sanción publicada (Resolución 17/07/2026, BOE 03/08/2026) | SAN-1 | `dated_by_official_event` |
| 3 | Capital 903.000,38→953.964,00 | SGIIC-4 | `bounded_by_asof_state` |
| 4 | Capital 903.000,00→903.000,38 | SGIIC-4 | `bounded_by_asof_state` |
| 5 | Nombramiento PRESIDENTE 18/10/2024 (+ DIR. GENERAL misma fecha) | SAN-1 | `dated` (campo oficial `Fecha nombramiento`) |
| 6 | Nombramiento PRESIDENTE 14/05/2025 | ESI-1 | `dated` |
| 7 | Nombramiento CONSEJERO DELEGADO 03/09/2024 | SGIIC-4 | `dated` |
| 8 | Registro oficial 24/07/2025 | ESI-2 | `dated` |
| 9 | Registro oficial 08/04/2016 | ESI-1 | `dated` |
| 10 | Registro oficial 15/01/2010 | ESI-3 | `dated` |
| 11 | Registro oficial 08/03/2002 | ESI-4 | `dated` |
| 12 | Programa de actividades registrado 24/03/2023 | SGIIC-1 | `dated` |
| 13–17 | FECHA ALTA en registro BdE (07/09/2012, 14/08/2014, 12/01/2016, 23/01/2017, 14/01/2019*) | BDE-1..5 | `dated_by_official_event` |
| 18 | Alta actividad en LPS Austria 24/09/2022 | BDE-2 (SEFIDE) | `dated` |
| 19–20 | Estado `Cancelada` (snapshot as-of 2026-09-13) | INS-3, INS-4 | `bounded_by_asof_state` |
| 21 | Estado `Cancelada` sucursal | INS-5 | `bounded_by_asof_state` |
| 22 | Aviso-clon publicado 29/06/2026 (ABANTETHER.XYZ) | ESI-4 (target) | `dated_by_official_event` |
| 23 | Aviso-clon publicado 03/08/2026 (alantrafx.com) | ALANTRA EQUITIES reg 245 (≠ corpus) | `dated_by_official_event` |
| 24 | Cambio de domicilio INS-* | INS-* | `unbounded` — el export no lo trae |
| 25 | Fecha exacta de cancelación INS-* | INS-3/4/5 | `unbounded` (sólo cota superior = snapshot) |

\* verificado en XLSX; BDE-5 alta BdE figura como 14/01/2019 vs `ENT_AUT`
EBA 2019-05-27 — divergencia de fechas entre fuentes conservada como
`CONFLICT`/sin resolver (no se sintetiza).

Ratio: 25/27 ≈ 93% (los 2 `unbounded` son de INS via artefacto).

## Hallazgos por vertical

### CNMV ESI (`esis.aspx`)
- Ficha completa en 6 vistas: identidad, socios (con %), administradores
  **con fecha de nombramiento**, agentes, sucursales, programa de
  actividades (servicios × instrumentos × clientes).
- `fs` → **HTTP 400** en las 4 fichas (confirma matriz).
- Sin "Historial" ni fecha de situación declarada → histórico =
  campos fechados + snapshots propios + BOE. Punto débil declarado.
- ESI-4 (ABANTE): 3 sucursales ES (Barcelona, Zaragoza, Sevilla).
- ESI-1 (ALANTRA CAPITAL MARKETS): reg 258, FOGAIN, programa amplio
  (RTO, negociación cuenta propia, custodia, asesoramiento).

### CNMV SGIIC/IIC (`sgiic.aspx`, `sociedadiic.aspx`)
- `fs` honrado: estados a 18/09/2025, 18/09/2023, 18/09/2021 servidos;
  `sociedadiic` declara la fecha en `wFecha$txtFecha`; `sgiic` no.
- Nearest-before confirmado (18/09/2023 ≡ 18/09/2021 en SGIIC-1/2/5
  → estado sin cambio en el tramo o snapshot anterior servido).
- Sin clamp inferior ya documentado → siempre contrastar con
  `Fecha registro oficial`.
- SAN-1 demuestra el valor real: domicilio histórico + sanción fechada.

### BdE / EBA PSD2
- XLSX `Registro_ServicioPagos.xlsx` con `FECHA: 17/09/2026` declarada:
  hoja 1 = entidades (CÓDIGO BE, NIF, **LEI**, FECHA ALTA, domicilio);
  hoja 2 = actividades por entidad con **FECHA DE ALTA ACTIVIDAD**;
  hoja 3 = operación transfronteriza (Agentes / Distribuidores /
  Libre prestación, país, actividad, fecha de alta).
- Las 5 del corpus presentes con NIF+LEI exactos → identidad triple
  (BdE code + NIF + LEI) sin fuzzy.

### Seguros (OpenDGSFP artefacto)
- Identidad multi-esquema exacta: `dgsfp:clave`, `es:nif`, `lei`,
  `bde:european_code`, `eiopa:identification_code`.
- `situacion` explícita (Activa/Cancelada) → estados honestos incluida
  baja. Cross-border operations modeladas (0 en los 5 casos).
- Limitación del artefacto: sin fechas de inscripción ni cambios
  atributivos — para historia de INS se necesita fuente adicional.

### Warnings/clones (AlertaFin artefacto)
- 10 368 notices; hits reales del corpus:
  - `webtrader.alantrafx.com (CLON)` → target explícito **ALANTRA
    EQUITIES SV reg 245** — *no* nuestra ESI-1 (reg 258). La atribución
    por similitud habría sido un false positive; la del registro es
    exacta.
  - `ABANTETHER.XYZ`, `ABANTE.US`, `ABANTE-BIM.COM`,
    `ABANTECAPITAL.COM/S` (CLON) → target explícito **ABANTE ASESORES
    DISTRIBUCION reg 194** = ESI-4 → `IMPERSONATES`/`CLONE_OF` real.
  - `ES-INVESTS (CLON)` → target "ALTAMAR GLOBAL INVESTMENTS AV reg
    253" (otra entidad distinta de SGIIC-5 ALTAMAR PRIVATE EQUITY).
  - `PECUNIACO.COM` / "PECUNIA CONSULTING GROUP": sin marcador clon ni
    observaciones → aviso directo al dominio; relación con BDE-3
    PECUNIA CARDS = **candidata ambigua, no afirmada**.
- Cero atribuciones adversas falsas; el modelo de relaciones
  (`DIRECT_WARNING_AGAINST`, `IMPERSONATES`, `CLONE_OF`,
  `MENTIONED_AS_LEGITIMATE_ENTITY`, `NOT_RELATED_TO`) tiene casos reales
  para cada rama.

## Preservación de UNKNOWN/INDETERMINATE

- ESI `fs` → rechazo registrado, no simulado.
- INS-5 sin `cross_border_operations` → se reporta ausencia de dato,
  no cero operaciones.
- Divergencia EBA `ENT_AUT` vs BdE `FECHA ALTA` (BDE-5) → `CONFLICT`
  declarado, no se elige una.
- `PECUNIACO` → candidato, no relación.
- `fs` pre-inscripción → comportamiento degenerado documentado
  (matriz), mitigación = contraste con `Fecha registro oficial`.

## Riesgos y limitaciones declarados

1. **Histórico ESI/EAF**: no existe estado-a-fecha oficial. Mitigación:
   observaciones propias periódicas (crawl programado) + BOE +
   resoluciones. El producto debe mostrar "NO HISTORICAL EVIDENCE" donde
   corresponda — es una limitación de fuente, no del sistema.
2. **`fs` no uniforme ni autodescriptivo**: en `sgiic.aspx` la fecha
   servida no se ecoa; nearest-before está observado pero no
   documentado por la fuente. Tratar `fs` como `OFFICIAL_AS_OF_STATE`
   con `requested_fs` + `served_state` registrados por nosotros.
3. **Parseo HTML frágil**: ASP.NET, plantillas por familia;
   `SOURCE_SCHEMA_CHANGED` obligatorio (fixtures congelados + live
   smoke separado).
4. **INS sin historia**: el artefacto OpenDGSFP no porta fechas de
   inscripción/cancelación; extender el export o complementar con
   DGSFP RRPP directo + BOE.
5. **Rate limiting CNMV**: 403 ocasionales a ráfaga; producción exige
   espaciado y reintentos (observado).
6. **Ventana de sanciones**: el registro vivo cubre una ventana; la
   historia verificable exige BOE (oficial-sources-esp) — confirmado
   con SAN-1 (resolución remite a BOE).
7. **403s vistos en `IndiceIIC.aspx`/`id=3`**: dos rechazos aislados en
   exploración, no en corpus — se reportan, no afectan al gate.

## Implicación para Fase F+

- Producto viable con el contrato CONDITIONAL. Vertical fuerte:
  CNMV SGIIC/IIC + BdE payments + warnings/clones.
- Siguiente: modelo de hechos `EXPLICIT_OFFICIAL_EVENT /
  OFFICIAL_AS_OF_STATE / OFFICIAL_DOCUMENT_DERIVATION /
  OBSERVED_CHANGE` (ya validado por este probe), proyección pública y
  primera ficha E2E — sugerida **SAN-1 GESCONSULT** (sanctioned +
  fs-capable + cambio de domicilio acotado) o **ESI-4 ABANTE**
  (sucursales + clones reales).
- No construir: crawler genérico de advertencias (AlertaFin), crosswalk
  seguros (OpenDGSFP), cliente BOE (official-sources-esp).

## Evidencia generada

```text
fixtures/g4/corpus/entities.json           20 entidades congeladas
fixtures/g4/sources/manifest.json          84 requests · sha256 · retrieved_at
fixtures/g4/sources/raw/*.{html,xlsx}      84 snapshots crudos
fixtures/g4/probes/{ESI-*,SGIIC-*,SAN-1}.json  vistas parseadas
docs/sources/SOURCE-CAPABILITY-MATRIX.md   matriz por fuente
docs/sources/CNMV-HISTORICAL-SURFACE.md    probe fs detallado
```
