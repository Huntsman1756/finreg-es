# G0.4 — Semántica regulatoria

## Clave de consulta y cardinalidad

La consulta regulatoria es `(entity_id, activity, jurisdiction)` (+ `territorial_basis`
opcional y `as_of`). **No** hay cardinalidad 1:1: una consulta se resuelve con `0..N`
`REGULATORY_ENTITLEMENT_ASSERTION`.

## Átomo: REGULATORY_ENTITLEMENT_ASSERTION

```
assertion_id, register_id, entity_id, entity_class,
activity, jurisdiction,
legal_effect, entry_mechanism, territorial_basis, legal_basis,
scope,
effective_from, effective_to,
source_assertions[],          # provenance por claim (G0.6 profundiza)
derived_by,                   # {rule_id, ruleset_version, effective_from} o null
principal_entity_id           # obligatorio para PSP_AGENT (W1)
```

## Tres dimensiones separadas (nunca un `permission_type` único)

| Dimensión | Valores |
|-----------|---------|
| `legal_effect` | `ENTITLED_TO_PROVIDE` \| `NOT_ENTITLED` \| `UNKNOWN` |
| `entry_mechanism` | `AUTHORISATION` \| `NOTIFICATION` \| `REGISTRATION` \| `EXEMPTION` \| `STATUTORY_ENTITLEMENT` |
| `territorial_basis` | `DOMESTIC` \| `BRANCH` \| `FREEDOM_TO_PROVIDE_SERVICES` \| `OTHER` |

Los atributos regulatorios pertenecen a la **aserción** sobre
`(activity, jurisdiction, territorial_basis)`, no a la `ENTITY`. Una misma persona jurídica
puede tener simultáneamente capacidades con mecanismos distintos (fixtures ent-001: banco con
`AUTHORISATION` bancaria, servicios de pago derivados y CAS por `NOTIFICATION`).

## Campos derivados

Proceden de reglas versionadas (`derived_by: rule_id + ruleset_version + effective_from`),
nunca rellenados a mano. Fixture: `credit-institution-implies-payment-services@1.0.0`
(asm-002). Cambiar la regla = nueva versión de ruleset.

## Temporalidad

| Campo | Definición |
|-------|------------|
| `retrieved_at` | Cuándo capturamos la fuente |
| `source_as_of` | Fecha declarada por la propia fuente (con `source_date_reliability`: `TRUSTED`/`SUSPECT`/`UNAVAILABLE`) |
| `effective_from` / `effective_to` | Vigencia jurídica del hecho |
| `observed_current` | La fuente lo mostraba vigente en la captura |

- `freshness_at = source_as_of ?? retrieved_at`.
- `response_freshness = min(freshness_at de los claims necesarios para la decisión)`.
- La caducidad usa el perfil de staleness del **registro** de la aserción (positivo vs.
  negativo). `source_as_of` es declaración de la fuente, no verdad verificada; la detección
  `content_hash(t1) != content_hash(t2) AND source_as_of(t1) == source_as_of(t2)` ⇒ `SUSPECT`
  (puede ser corrección editorial, no error: se marca, no se descarta).

## Dos niveles ante una ventana cerrada (C4)

Hay que distinguir el nivel de **aserción** del nivel de **agregación**:

- **Nivel de aserción.** Una `REGULATORY_ENTITLEMENT_ASSERTION` con `effective_to` vencido
  concluye `NOT_ENTITLED` + `ENTITLEMENT_EXPIRED`. Se expone en
  `assertion_evaluations[].effective_legal_effect_at_as_of` / `.reason` (el efecto de fuente
  sigue disponible en `source_legal_effect`). La aserción evaluada **conserva su
  `SOURCE_ASSERTION` completo** (con `raw_value` / `raw_snapshot_sha256`): no soportar el
  assessment no implica perder evidencia.
- **Nivel de agregación.** Esa expiración **no** es evidencia negativa explícita y **no**
  puede producir `CONFIRMED_NOT_AUTHORISED`: podría existir otra vía vigente de habilitación.
  El resultado agregado es `NO_ENTITLEMENT_EVIDENCED` (reason `ENTITLEMENT_EXPIRED`) o
  `INDETERMINATE`, salvo que la matriz de cobertura permita demostrar el negativo completo.

Test que fija la distinción: `tests/semantics/test_assessment.py::
test_expired_positive_alone_yields_entitlement_expired_c4`.

## Motor de assessment

Entrada: identidad resuelta (gate C1), aserciones del `entity_id`, contratos cargados,
política de staleness del registro, `as_of`.

1. **Gate de identidad**: sin `EXACT` ⇒ `INDETERMINATE` + reason de identidad. Nunca negativo.
2. **Admisibilidad**: scope de fuente no `OUT_OF_SCOPE`; ventana `effective_from/to` vigente;
   agente con principal (W1); evidencia no caducada según política del registro.
3. **Veredictos**:
   - `ENTITLED` y `NOT_ENTITLED` admisibles ⇒ **`INDETERMINATE`** (`CONFLICTING_ASSERTIONS`, C2).
   - Solo `NOT_ENTITLED` explícito fresco ⇒ **`CONFIRMED_NOT_AUTHORISED`**.
   - ≥ 1 `ENTITLED` admisible ⇒ **`CONFIRMED_AUTHORISED`** (con `response_freshness`).
   - Solo `UNKNOWN` ⇒ `INDETERMINATE` (`UNINTERPRETABLE_EVIDENCE`).
   - Sin aserciones (o todas vencidas/caducadas) ⇒ **`NO_ENTITLEMENT_EVIDENCED`**
     (`NO_ASSERTIONS_IN_SCOPE` / `ENTITLEMENT_EXPIRED`) o `INDETERMINATE`
     (`ALL_EVIDENCE_STALE`). **Nunca** `NOT_FOUND` ⇒ negativo.

## Salida (contrato de salida G0.7)

```json
{
  "entity": "ent-001",
  "activity": "PAYMENT_SERVICES",
  "jurisdiction": "ES",
  "as_of": "2026-09-13",
  "identity_resolution": "EXACT",
  "assessment": "CONFIRMED_AUTHORISED",
  "reason": "SUPPORTED_BY_ACTIVE_ASSERTIONS",
  "assertions": [
    {
      "legal_effect": "ENTITLED_TO_PROVIDE",
      "entry_mechanism": "AUTHORISATION",
      "territorial_basis": "DOMESTIC",
      "legal_basis": "PSD2 art. 1(5)(a); Ley 10/2014 ...",
      "effective_from": "1999-06-14",
      "effective_to": null,
      "derived_by": {"rule_id": "credit-institution-implies-payment-services", "ruleset_version": "1.0.0"},
      "evidence": [{"authority": "Banco de Espana", "register_id": "BDE_REGISTRO_ENTIDADES", "raw_value": "...", "raw_snapshot_sha256": "..."}]
    }
  ],
  "assertion_evaluations": [
    {
      "assertion_id": "asm-006",
      "source_legal_effect": "ENTITLED_TO_PROVIDE",
      "effective_legal_effect_at_as_of": "NOT_ENTITLED",
      "reason": "ENTITLEMENT_EXPIRED"
    }
  ],
  "response_freshness": "2026-08-31",
  "diagnostics": []
}
```

Implementación: `finreg_es/semantics.py`; fixtures `fixtures/regulatory/`; escenarios
`fixtures/regulatory/scenarios.json`. Los hashes usan `FINREG_CANONICAL_JSON_V1`
(ver `docs/g0-scope.md`); no se afirma compatibilidad RFC 8785.
