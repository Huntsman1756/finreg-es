# G0.3 — Matriz de cobertura

## Firma

La cobertura **no** es un par `REGISTER → ACTIVITY`; es una función:

```
coverage(register, entity_class, activity, jurisdiction, territorial_basis, effective_date)
    -> { status: IN_SCOPE | OUT_OF_SCOPE | UNKNOWN, matched_rule_id, reason }
```

## Evaluación congelada

1. **Reglas `OUT` explícitas** del contrato ganan (p. ej. bancos fuera del registro PSD2,
   `bde-out-fps-inbound`). `OUT_OF_SCOPE` bloquea negativos **y** positivos desde esa fuente.
2. **Guardas fail-closed** sobre las declaraciones del contrato: clase excluida, actividad no
   declarada, jurisdicción no cubierta ⇒ `OUT_OF_SCOPE`.
3. **Reglas `IN`** ⇒ `IN_SCOPE`.
4. **Sin regla aplicable** ⇒ `UNKNOWN`. `UNKNOWN` es conservador: bloquea negativos y evita
   afirmar cobertura no verificada (p. ej. ESMA frente a entidades financieras bajo
   notificación, H1).

Las reglas llevan vigencia (`valid_from`/`valid_to`) evaluada contra `effective_date`.

## Producción de negativos (`CONFIRMED_NOT_AUTHORISED`)

Solo por:

**A. Evidencia negativa explícita** — `revoked` / `withdrawn` / `forbidden` / estado
inactivo explícito, con la semántica del estado verificada (H5).

**B. Enumeración completa**, que exige **simultáneamente**:
- entidad identificada `EXACT`;
- actividad, clase, jurisdicción y base territorial dentro del scope (`IN_SCOPE`);
- periodo temporal cubierto;
- ninguna excepción aplicable;
- snapshot completo conservado (`enumeration_snapshot_sha256`,
  `enumeration_retrieved_at`, `enumeration_source_as_of`, `coverage_rule_id`,
  `coverage_ruleset_version`).

La puerta `can_produce_enumeration_negative()` verifica: capability de la fuente incluye
`COMPLETE_ENUMERATION`, scope `IN_SCOPE`, identidad `EXACT`, snapshot presente y coherente
con la regla de cobertura. En cualquier otro caso el resultado del assessment es
`NO_ENTITLEMENT_EVIDENCED` o `INDETERMINATE` — **nunca** `NOT_FOUND` ⇒ negativo.

## Staleness de negativos

- `max_negative_staleness_days <= max_positive_staleness_days` (validado por contrato).
- El negativo por enumeración caduca: consumido más allá de su staleness ⇒ `INDETERMINATE`
  (fixture asm-011, escenario S8b).
- La caducidad se mide sobre `freshness_at = source_as_of ?? retrieved_at` de la evidencia,
  no sobre la fecha de efecto jurídico.

## Ejemplos congelados

| Consulta | Resultado |
|----------|-----------|
| `EBA_PSD2_REGISTER × CREDIT_INSTITUTION` | `OUT_OF_SCOPE` (W2: exclusión de bancos) |
| `BDE_REGISTRO_ENTIDADES × FPS inbound` | `OUT_OF_SCOPE` (W3/H6) |
| `EBA_CIR × PAYMENT_INSTITUTION` | `OUT_OF_SCOPE` (excluida + guarda) |
| `BdE × INVESTMENT_SERVICES` | `OUT_OF_SCOPE` (actividad no declarada) |
| `ESMA_MICA × CREDIT_INSTITUTION` | `UNKNOWN` (H1: ni cubierto ni excluido) |
| `CNMV_MICA_CASP_LIST × FUND_MANAGER_SGIIC` | `UNKNOWN` (regla CASP-only) |

Implementación: `finreg_es/coverage.py`; contratos en `fixtures/contracts/`.
