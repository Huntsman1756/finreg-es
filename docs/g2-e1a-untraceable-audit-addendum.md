# G2-E1-A — Addendum de auditoría: exclusión `untraceable`

Addendum **inmutable** a
`docs/g2-e1-bitemporal-assessment-contract.md` (congelado en
`5232495`). No modifica retroactivamente E1: la implementación E2
(`finreg_es/bitemporal.py`, `7bb44bd`) reveló una ambigüedad de
serialización del contrato y este documento es el sucesor
documental que la resuelve.

## Cambio

`BitemporalAssessmentResult.evidence` añade tres campos a los
cuatro conjuntos congelados en E1 §4:

```text
evidence
  usable_assertion_ids                      # E1
  excluded_after_known_at_assertion_ids     # E1
  usable_reported_fact_ids                  # E1
  excluded_after_known_at_fact_ids          # E1
  excluded_untraceable_assertion_ids        # E1-A
  excluded_untraceable_fact_ids             # E1-A
  diagnostics                               # E1-A (p.ej.
                                            #  no_source_assertions:<id>)
```

## Motivo

E1-R2 distingue semánticamente dos causas de exclusión:

```text
"observado después de K"          → excluded_after_known_at_*
"sin provenance temporal trazable" → excluded_untraceable_*
```

El contrato E1 ya exigía que un item sin `source_assertions`
vinculadas nunca fuese observable (fail-closed), pero el esquema de
resultado sólo enumeró cuatro buckets: la representación concreta
de los no trazables quedó incompleta. Meterlos en
`excluded_after_known_at_*` habría sido incorrecto — un item sin
fuentes no es literalmente "posterior a K".

## Semántica

```text
no cambia observable()        (misma regla E1-R1/R2)
no cambia ningún probe E0     (18/18 siguen binding)
no cambia V3                  (assessment/reason intactos)
sólo hace explícita la causa de exclusión
```

Invariante de auditoría resultante:

```text
usable_* + excluded_after_known_at_* + excluded_untraceable_*
    = universo de evidencia de la query
```

(verificado por test en `tests/g2/test_g2e_bitemporal.py`).

## Compatibilidad

```text
additive
corpus E0 actual => buckets untraceable vacíos
```

## Estado

```text
G2-E1-A  FROZEN  (este documento; sucesor documental de E1, no
                  reinterpretación)
```
