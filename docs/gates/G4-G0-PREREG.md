# G4-G0 — Preregistro: viabilidad del "Regulatory Record ES"

Preregistrado el 2026-09-18, antes de cualquier evaluación de corpus.
Documento congelado: los criterios de abajo no se ajustan tras ver
resultados; si el contrato es incorrecto, se documenta un sucesor.

## Afirmación falsable

> Para un corpus diverso de entidades financieras españolas, las fuentes
> oficiales públicas permiten sostener una ficha regulatoria
> (identidad + registro + autorizaciones + hechos) con provenance
> completa, sin joins canónicos falsos y con historia fechable o
> acotable mejor que `retrieved_at` propio.

## Corpus congelado

Artefacto: `fixtures/g4/corpus/entities.json` (mismo commit).

Selección: slots explícitos cuando ya conozco el identificador;
slots por regla determinista cuando la entidad concreta debe resolverse
contra una superficie oficial **antes de evaluar** (la resolución queda
registrada en el corpus; una regla que no resuelve es un *finding* del
corpus, no un auto-fail del gate).

| Slot | Entidad / regla | Rasgo cubierto |
|---|---|---|
| ESI-1 | `A87515540` ALANTRA CAPITAL MARKETS SV (`esis.aspx`) | veterana, sucursales/passporting |
| ESI-2 | `B22526768` 101 FUTURES ASSET MANAGEMENT AV | reciente (reg. 24/07/2025) |
| ESI-3 | `A64911100` ACTIVOTRADE VALORES SV | programa de actividades |
| ESI-4 | `A-83217281` ABANTE ASESORES DISTRIBUCION AV | grupo, posible cambio de denominación |
| SAN-1 | **regla**: primera entidad del registro público de sanciones CNMV (`verRegSanciones.aspx?page=0`, orden de página) resoluble a ficha CNMV por NIF → **resuelta: `A28867000` GESCONSULT, S.A., SGIIC** (Resolución 17/07/2026, BOE 03/08/2026; ficha `sgiic.aspx`) | sancionada |
| SGIIC-1 | `A83133421` A&G FONDOS SGIIC (`sgiic.aspx`) | `fs` ya observado |
| SGIIC-2 | `A85853927` ABACO CAPITAL SGIIC | boutique |
| SGIIC-3 | `A79389672` ABANCA GESTION DE ACTIVOS SGIIC | grupo bancario, organización |
| SGIIC-4 | `A48883748` ACACIA INVERSION SGIIC | veterana |
| SGIIC-5 | `A84144625` ALTAMAR PRIVATE EQUITY SGIIC | passporting EEE |
| BDE-1..5 | **regla**: primeras 5 entidades ES (`CA_OwnerID=ES_BE`, `EntityType ∈ {PSD_PI, PSD_EMI}`) del fixture EBA PSD2 congelado (`fixtures/g0.5/sources/raw/h4-eba-psd2-20260913.zip`, 330 291 records), orden por `EntityCode` → **resueltas**: `ES_BE!6702` GLOBAL PAYMENTS MONEYTOPAY EDE · `ES_BE!6705` SEFIDE EDE · `ES_BE!6707` PECUNIA CARDS EDE · `ES_BE!6709` UP AGANEA EDE · `ES_BE!6712` BIP & DRIVE EDE | payment/e-money, cross-border |
| INS-1..5 | **regla**: de `opendgsfp-0.1.jsonl` (`schema_version: opendgsfp/0.1`, `data_sha256:056de1e6…`), orden por `dgsfp:clave` → **resueltas**: `C0001` (LEI) · `C0002` (LEI) · `C0003` (sin LEI) · `C0004` (sin LEI) · `E0006` (`EEA_BRANCH`, situación "Cancelada") | seguros, gaps de identidad, branch |

Requisitos de diversidad cubiertos por los slots: veterana (ESI-1,
SGIIC-4), reciente (ESI-2), sanción (SAN-1), warning/clone (cross-check
del corpus completo contra `notices.jsonl` de AlertaFin), programa
(ESI-3), sucursales (ESI-1, INS-5), passporting (SGIIC-5, BDE-*),
cambio de nombre (candidato ESI-4/SGIIC-2 — se marca si la ficha lo
muestra), baja/cancelada (INS-5 `Cancelada`), con LEI / sin LEI
(INS-1..4), identidad conflictiva (`UNRESOLVED`/`CONFLICT` en INS-*).

## Método

1. **Snapshot congelado por request**: URL, fecha pedida, HTTP status,
   bytes crudos, `sha256(bytes)`, `sha256(normalized)`, parse, resultado.
   Directorio `fixtures/g4/sources/` con manifiesto.
2. **Presupuesto**: ≤ 150 requests CNMV (espaciados ≥ 1 s), ≤ 20 al
   resto. Si una fuente devuelve 403/5xx → `SOURCE_UNAVAILABLE`, se
   registra y se reintenta una vez al final.
3. **`fs`**: sólo en superficies que lo honran (matriz de fuentes);
   fechas `current, -1y, -3y, -5y` por entidad IIC; para ESI se
   confirma el rechazo 400 una vez por ficha.
4. **Identidad**: resolución exact-first del modelo FinReg
   (NIF > LEI > registro-ID). Nombre nunca produce `EXACT`.
5. **Hechos**: cada fact material clasificado como
   `EXPLICIT_OFFICIAL_EVENT | OFFICIAL_AS_OF_STATE |
   OFFICIAL_DOCUMENT_DERIVATION | OBSERVED_CHANGE`.
6. **Warnings/clones**: cross-check contra `notices.jsonl` de
   AlertaFin; una suplantación de una entidad del corpus **no** es una
   advertencia contra ella.
7. **Historial**: cada cambio relevante se fecha por (a) evento
   oficial fechado, (b) estado as-of de fuente (`fs`, fecha de
   registro, fecha de baja), (c) intervalo entre observaciones —
   en ese orden de preferencia, nunca inventando la fecha.

## Atributos "core de ficha" (denominador del 90%)

`legal_name, nif, registry_number, registration_date, status,
domicile, regulator, entity_class, authorised_services/permissions,
territorial_scope, source_as_of_or_observed_at`.

Por entidad se cuenta cuántos se sostienen con fuente oficial +
provenance navegable. `UNKNOWN` correcto cuenta como sostenido si el
sistema lo declara explícitamente.

## Cambios históricos seleccionados (denominador del 80%)

Por entidad se seleccionan **antes de mirar resultados** los cambios
esperables: cambio de domicilio, cambio de denominación, variación de
capital, alta/baja de administrador, alta/baja de sucursal o agente,
alta/baja de servicio autorizado, cambio de estado. Cada cambio
encontrado se clasifica: `dated_by_official_event` ·
`bounded_by_asof_state` · `bounded_by_observations` · `unbounded`.
Éxito = cualquier clase distinta de `unbounded`.

## Gates (idénticos a los del encargo, formalizados)

```text
PASS      ⇔  ≥90% atributos core sostenidos con fuente oficial
          ∧  ≥80% cambios seleccionados fechados/acotados mejor
             que retrieved_at
          ∧  0 false canonical entity joins
          ∧  0 false adverse warning/clone attribution
          ∧  100% facts materiales con provenance navegable
          ∧  UNKNOWN/INDETERMINATE preservados
CONDITIONAL ⇔  estado actual fuerte + identidad/provenance fiable
          ∧  histórico sólo parcial → contrato redefinido:
             "estado oficial + historial oficial disponible +
              cambios detectados por observaciones propias"
FAIL      ⇔  fuzzy merges frecuentes necesarios
          ∨  cambios esenciales no fechables/acotables
          ∨  fuentes inestables (403/5xx persistente)
          ∨  valor añadido marginal sobre registros oficiales
```

## Resultados válidos (declarados antes de ejecutar)

- `fs` funciona sólo en IIC/ECR → resultado válido: histórico
  oficial asimétrico por vertical (CONDITIONAL probable).
- 0 warnings/clones sobre el corpus → válido: se reporta 0, no se
  fabrican casos.
- Entidad con identidad `UNRESOLVED` → válido y deseable: cuenta
  como caso de identidad conflictiva.
- Corpus slot sin resolver → finding, no fail.
- G0 FAIL → fin de la productización; se conserva el informe.

## Artefactos comprometidos

```text
fixtures/g4/corpus/entities.json            corpus congelado
fixtures/g4/sources/manifest.json           snapshots + sha256
fixtures/g4/sources/raw/*                   bytes crudos
fixtures/g4/probes/*.json                   resultado parseado por probe
docs/gates/G4-G0-REPORT.md                  veredicto + métricas
```

## Kill criteria (stop inmediato)

- Rate-limiting/bloqueo persistente de CNMV → documentar y decidir
  entre corpus reducido (declarado) o FAIL por inestabilidad.
- Descubrir que `fs` devuelve contenido mezclado (parte histórico,
  parte current) → finding grave, reevalúa el uso de `fs` en producto.
