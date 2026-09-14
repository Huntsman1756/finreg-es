# G2-D0 — Historical snapshot inventory (exploratorio)

Inventario estrictamente documental de las observaciones reales
disponibles. Cero semántica nueva, cero interpretación jurídica.
Pregunta central:

> ¿Tenemos dos observaciones independientes de la misma serie
> normalizadas bajo el mismo contrato?

**Respuesta: NO. No existe ningún par longitudinal real en la
historia actual.** Todas las capturas son de 2026-09-13/14 y cada
serie tiene exactamente una versión de contenido.

## 1. Método

- 10 manifiestos congelados (`fixtures/g0.5`, `fixtures/g1`) —
  `retrieved_at` vive a nivel manifiesto (run), `source_as_of`
  por item cuando la fuente lo declara.
- `content_sha256` por fichero, agrupado sobre todos los
  manifiestos → 0 ficheros con 2 SHAs distintos.
- `git log --follow` + `git rev-parse` por blob: los "multi-versión"
  aparentes eran renombres g0.5→g1 con blob idéntico
  (ej. `h7-esma-casps.csv` ≡ `esma-mica-casps.csv`,
  `c01cde9c…` en ambos commits). Confirmado: falso positivo de
  tracking, no contenido distinto.

## 2. Series y observaciones

| Serie | content_id | Observaciones (manifest@retrieved_at) | source_as_of |
|-------|-----------|---------------------------------------|--------------|
| EBA PSD2 register (`h4-eba-psd2-20260913.zip`) | `948429ad…` | g0.5@09-13, g1-c-run@09-13, g1-d-run@09-14, g1-e-run@09-14 | `2026-09-13T08:00:04Z` |
| BdE registro-servicios-pago.xlsx | `ea889fa1…` | g1-b1@09-14, g1-d-run@09-14, g1-d-run-002@09-14, g1-e-run@09-14 | `2026-09-10` |
| BdE registro-con-establecimiento.xlsx | `72faee42…` | g1-b1@09-14, g1-d-run(-002)@09-14, g1-e-run@09-14 | `2026-09-10` |
| BdE registro-entidades.xlsx | `b6f91f84…` | g1-b1@09-14, g1-d-run(-002)@09-14 | `2026-09-10` |
| BdE registro-entidades-credito.xlsx | `c2237eac…` | idem | `2026-09-10` |
| BdE registro-sin-establecimiento.xlsx | `820dc61b…` | idem | `2026-09-10` |
| BdE registro-psp-excluidos.xlsx | `2f953a48…` | idem | `2026-09-10` |
| ESMA MiCA casps.csv (`h7-esma-casps.csv` ≡ mismo contenido) | `0af299b1…` | g0.5@09-13, g1-c1@09-14, g1-d-run(-002)@09-14 | `2026-09-14` |
| ESMA MiCA ncasp.csv | `fb778670…` | g1-c1@09-14, g1-d-run(-002)@09-14 | `2026-09-14` |
| CNMV psc-criptoactivos.pdf (`h2-cnmv-mica-list.pdf` ≡ mismo) | `08305d48…` | g0.5@09-13, g1-c1@09-14, g1-d-run(-002)@09-14 | `2026-09-14` |
| BaFin/Finanstilsynet detail HTML | 4 ficheros | g1-d2@09-14, g1-d-run-002@09-14 | `2026-09-14` |
| EBA landing (`-landing` ≡ `-landing-v2` ≡ `h4-page`, mismo contenido) | `d7cd7dfe…` | g0.5@09-13, g1@09-13, g1-b1@09-14, g1-d-run(-002)@09-14 | — |

Duplicados internos reales (mismo `content_id`, nombres distintos):
`h7-esma-casps.csv`/`esma-mica-casps.csv`,
`h2-cnmv-mica-list.pdf`/`cnmv-psc-criptoactivos.pdf`,
`eba-psd2-register-landing.html`/`-v2`/`h4-eba-psd2-page.html`,
`h8-bde-entities-categories.pdf`/`bde-entidades-inscritas-registros-oficiales.pdf`,
`h6-bde-register-page.html`/`bde-registros-entidades-landing.html`.

## 3. Clasificación de las re-declaraciones entre manifiestos

Los mismos `content_id` aparecen en manifiestos con `retrieved_at`
09-13 y 09-14. Según el contrato G2-A §1 serían dos observaciones del
mismo contenido **sólo si hay prueba de captura independiente**.
Los manifiestos g1-* re-declaran bytes congelados de la captura g0.5;
no hay log de descarga que demuestre una segunda captura real el
09-14. Veredicto: **re-referencia, no re-captura probada**. Sirven
como Type-A débil si se acepta `retrieved_at` de manifiesto como
observación; si no, ni siquiera eso.

## 4. Sucesiones reales que SÍ existen (nivel artefacto, no observación)

```text
g1-e-negative-corpus → -002 → -003
  mismo raw, mismo extractor_version (G1E_CORPUS_EXTRACT_V1),
  succeeds/succession_reason explícitos
  = misma observación + sucesor semántico documentado

corpus-g1-d → corpus-g1-d-002
derived-assertions-g1-d-001 → -002
derived-assertions-g1-e-001 → -002
```

Son instancias reales del "falso histórico #3" en positivo:
re-extracción/remediación produce **sucesión de artefacto**, nunca
nueva observación. Útiles como evidencia de que la cadena de
sucesión funciona; no son pares longitudinales de fuente.

## 5. Veredicto por tipo de evidencia (objetivos de G2-B)

```text
A  identical content across observations
   PARTIALLY_REPRESENTABLE — re-declaraciones entre manifiestos
   con retrieved_at distinto y mismo SHA; débil mientras no haya
   re-captura probada

B  record/field genuinely changed
   NOT_REPRESENTABLE_IN_CURRENT_HISTORY

C  added/removed records entre capturas completas
   NOT_REPRESENTABLE_IN_CURRENT_HISTORY

D  same source_as_of + different content
   NOT_REPRESENTABLE_IN_CURRENT_HISTORY

B07 real (extractor v1 × v2 sobre mismo raw)
   NOT_REPRESENTABLE — las sucesiones de corpus comparten
   extractor_version; nunca hubo re-extracción bajo otra
   normalization_version
```

No se fabrican. B01–B12 siguen siendo el contrato del differ; los
casos reales B/C/D quedan pendientes de adquisición.

## 6. Plan de adquisición para pares reales

Para G2-D formal hace falta al menos una segunda captura probada por
serie. Prioridad por valor demostrativo:

```text
1. EBA PSD2 register   — publica exports fechados (el zip actual ya
   lleva fecha en el nombre); re-captura en fecha futura da par real
   con source_as_of distinto → NORMAL_SUCCESSION, y si hay altas/
   bajas/cambios de ENT_AUT, casos B/C reales.

2. BdE registro-servicios-pago.xlsx — registro vivo, actualización
   periódica; la fuente ya declara source_as_of (09-10).

3. ESMA MiCA casps.csv — registro vivo; source_as_of declarado.

4. CNMV — capturas puntuales; útil sobre todo como caso negativo de
   completitud (§10 del contrato G2-A).
```

Cualquier re-captura genera un manifiesto nuevo con `retrieved_at`
propio; aunque el SHA sea idéntico, ya es una segunda observación
probada (Type A fuerte).

## 7. Hallazgo colateral: retrieved_at a nivel manifiesto

`retrieved_at` vive en el manifiesto, no por item. Para series con
capturas en días distintos dentro del mismo run eso es impreciso.
No es defecto reproducible del comportamiento actual (cada manifiesto
es una captura coherente), pero G2 debería considerar `retrieved_at`
por item cuando una captura real dure más de un día o se reutilicen
bytes de otra observación. Registrado como observación, no como
defecto.

## 8. Estado

```text
G2-A   CLOSED        contrato congelado (dfb10d4)
G2-D0  DONE          inventario: sin pares longitudinales reales
G2-B   READY         differ = B01–B12 sintéticos + Type-A débil real
                     + differential testing dictdiffer/deepdiff
G2-D   BLOCKED       requiere re-capturas futuras (plan §6)
```
