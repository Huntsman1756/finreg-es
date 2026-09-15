# G2 — informe final

Cierre de la fase G2 de FinReg-ES (`g2-longitudinal-evidence-closed`).
G2 demostró una propiedad nueva del sistema — de "¿qué puede hacer
ahora?" a "¿qué podía hacer entonces y por qué cambió?":

> FinReg captura observaciones oficiales versionadas, distingue
> cambios de bytes de cambios estructurales, convierte cambios reales
> en candidatos regulatorios fail-closed y responde consultas
> bitemporales `valid_at × known_at` sobre evidencia versionada sin
> retroproyección.

## Veredicto

```text
G2 — PASS / CLOSED

G2-A  CLOSED   contrato temporal/snapshot congelado
               (docs/g2-snapshot-history-contract.md)
G2-B  CLOSED   diff estructural determinista sobre snapshots
               reales; PORT_PATTERN dictdiffer; gates de
               comparabilidad operando
G2-C  CLOSED   primer Type-B/C real procesado: EBA
               20260914→20260915 → 67 ENTITY_RECORD_APPEARED
               (SUPPORTED) + 312 UNCLASSIFIED_STRUCTURAL_CHANGE
               (BLOCKED, NO_PREREGISTERED_RULE) — fail-closed
               operando como se preregistró
G2-D  CLOSED   PROVEN WITH QUALIFICATION — corpus longitudinal real
               (3 observaciones EBA + re-observaciones BdE/ESMA) con
               expectations preregistradas; superficial en
               profundidad de calendario (límite declarado)
G2-E  CLOSED   5 casos reales congelados (E0) → contrato
               bitemporal (E1 + addendum E1-A) → capa fina sobre V3
               (E2): 18/18 probes
G2-F  CLOSED   este cierre: replay byte-idéntico de la cadena
               autoritativa, invariants verificados, suite verde
```

G2 no se reabre salvo defecto reproducible nuevo.

## Números

```text
18/18  probes bitemporales E0 reproducidos (binding, íntegros)
5      casos reales congelados (DENIZEN ×2, MMG ×2, THUNES)
2      pares reales EBA comparados: 0/0/0 y 67/0/312
379    candidatos G2-C del segundo par: 67 SUPPORTED + 312 BLOCKED
515    tests PASS (suite completa, offline, determinista)
0      divergencias entre oráculo E0 e implementación E2
0      dependencias runtime añadidas (stdlib puro)
0      cambios en semantics.py / derivation.py / temporal.py
0      bytes de fixtures congelados modificados
```

## Cadena autoritativa congelada

```text
Fuentes   manifest-g2-d01            sha256 d40cc685479e2195…
          manifest-g2-acq-2026-09-15 sha256 9f3833984e4ed489…
          raws: h4-eba-psd2-20260913.zip        948429ad… (g0.5)
                eba-psd2-202609141600.zip       8e28bb25…
                eba-psd2-202609150000.zip       a582908c…
G2-B      FINREG_G2_EBA_NORMALIZATION_V1 · compare_observations
          eba-psd2-20260913-vs-20260914  sha256 fe63eef5… (0/0/0)
          eba-psd2-20260914-vs-20260915  sha256 e268e110… (67/0/312)
G2-C      FINREG_G2C_EVENT_RULES_V1 · classify_changes
          events 20260913-20260914       sha256 5a64c295… (0 cand.)
          events 20260914-20260915       sha256 64018957… (379 cand.)
          synthetic-contract-slice       sha256 208bc91d…
G2-E      evidence set: derived-assertions-g1-e-002
          @sha256:2fb08d678a5ee11a… (+ corpus-g1-e-001 d1d4d7b1…,
          claim-ledger-g1-e-001 77241483…)
          fixture E0 FINREG_G2_E0_CASES_V1  artifact_sha 784d489e…
          finreg_es/bitemporal.py → ASSESSMENT_SEMANTICS_V3 intacta
```

Replay: `python tools/audit_g2f_replay.py` — recomputa los 2 pares
desde los zips raw (verificando sha256 contra los manifiestos),
regenera eventos + fixture E0 + export OpenLineage por sus builders
con git-clean exigido, y reevalúa los 18 probes. **Resultado: PASS
integral** en el HEAD de cierre.

## Invariants verificados

```text
raw SHA ≠ structural change        (mismo content_id ⇒ 0 diff, §1)
removed ≠ withdrawal               (completitud del slice, §5)
added ≠ entitlement                (presencia ≠ autorización, G2-C0)
known_at nunca muta valid-time     (effective_from/to, intervals,
                                    covers(), effective_effect_at()
                                    intocables — E1-R3)
evidencia sin provenance           (excluded_untraceable_* +
nunca se vuelve visible             no_source_assertions:<id>, E1-R2/E1-A)
evidence_set_id liga los           (<stem>@sha256:<bytes>, E1-R5)
bytes realmente consumidos
```

## Regresiones

```text
G0/G1 congelados        sin regresión (suite completa verde)
V1/V2/V3                intactas; E2 delega en V3 sin tocarlo
CI real                 run 35017062891 (HEAD eabcc56):
                        test 3.11/3.12/3.13 ✓ + oracles ✓
OpenLineage             regenera byte-idéntico
```

## Límites declarados (no impiden el PASS)

- **Gap de catálogo `DER_CHI_ENT_AUT`** (E0-F02): 276
  Active→Inactive + 2 Inactive→Active en `PSD_AG` quedaron
  `UNCLASSIFIED_STRUCTURAL_CHANGE`/`BLOCKED` — candidato a extensión
  preregistrada futura de G2-C, nunca clasificación retroactiva.
- **Normalizadores G2 incompletos**: sólo EBA tiene
  `FINREG_G2_EBA_NORMALIZATION_V1`; BdE/ESMA/CNMV carecen de
  normalizador longitudinal (sus re-observaciones del 15/09 se
  manifestaron, no se difearon).
- **`known_at` es fecha calendario** (E1-R4): sub-day transaction
  ordering fuera de alcance; requeriría versión sucesora del
  contrato.
- **Evidencia revocada/corregida después de K**: diferida (G2-A §12)
  — el corpus sigue sin tener un caso real.
- **`PSD_AG` como sujeto de query**: ruta delegada del principal
  (G1-D); los agentes alimentan findings, no probes.
- **Sin claim/lease para agentes paralelos**: limitación conocida del
  scheduler de tasks (AGENTS.md); ejecución secuencial asumida.
- **Historia longitudinal superficial en profundidad de calendario**:
  el corpus G2 tiene 3 observaciones EBA en ~48h; la demostración es
  real pero estrecha en tiempo.

## Artefactos de cierre

| Artefacto | Rol |
|-----------|-----|
| `fixtures/g2/` | sources+manifiestos, comparisons, events, e0 — congelados |
| `finreg_es/bitemporal.py` | capa bitemporal (única producción nueva de G2-E) |
| `tools/audit_g2f_replay.py` | replay byte-idéntico de la cadena |
| `docs/g2-*.md` | contratos A/C0/E0/E1/E1-A + inventario D0 + scan B |
| `tests/g2/` | G2-B (diff+oracles), G2-C, G2-E (18 probes + metamórficos) |

## Política heredada hacia G3

```text
1. preregistro antes que implementación (casos + expectations)
2. OSS scan failure-driven antes de capacidad genérica nueva
3. fail-closed: evidencia insuficiente → finding clasificado
4. historia no reescribible: remediación = artefacto sucesor
5. `g2-acquire-next` sigue ready tras el cierre — es operación
   continua del sistema, no razón para mantener G2 abierto
```
