# ADR-006 — Resolución de identidad: exact-first, nombres sólo generan candidatos

Fecha: 2026-09-18 · Estado: aceptado.

## Decisión

Se mantiene y extiende el orden de resolución de FinReg
(`docs/identity-model.md`):

```text
1. identificador exacto de regulador (CNMV_REGISTRY_ID, BDE, DGSFP clave,
   EBA EntityCode, EIOPA code)
2. NIF exacto (checksum validado)
3. LEI exacto (ISO 17442, mod 97-10 validado)
4. crosswalk de IDs con scope de autoridad (merge_basis upstream)
5. relación oficial predecessor/successor explícita
6. relación adjudicada manualmente (con evidencia)
```

Nombre normalizado, dirección, dominio y demás metadata generan
**candidatos** (`CANDIDATE_MATCH`), nunca merges. Estados de resolución:

```text
EXACT | CONFLICT | UNRESOLVED | CANDIDATE
```

## Motivo / evidencia G0

- La probe real demostró el riesgo: `webtrader.alantrafx.com (CLON)`
  suplanta a *ALANTRA EQUITIES SV reg 245*; un join por nombre
  "alantra" habría atribuido la suplantación a ALANTRA CAPITAL MARKETS
  (reg 258) — false adverse attribution. La atribución correcta usa el
  número de registro que la propia CNMV publica en la nota.
- `PECUNIACO.COM` vs PECUNIA CARDS EDE: similitud de nombre →
  candidato; sin marcador clon ni observación explícita, no se afirma.
- OpenDGSFP ya modela `EXACT/CONFLICT/UNRESOLVED` con `merge_basis`
  por join — se consume su semántica, no se reimplementa.

## Consecuencias

- rigour/nomenklatura (si se adoptan en capa de candidatos) quedan
  fuera de la cadena de identidad exacta.
- `SAME_ENTITY` exige identificador determinista o adjudicación
  documentada; el umbral no se relaja por volumen de coincidencias.
- IDs de distintos namespaces no se equiparan (`dgsfp:clave:C0001` ≠
  `bde:supervisor_code:C0001` salvo crosswalk upstream).
