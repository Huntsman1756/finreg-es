# G5-A — Preregistro: Searchable Universe

Baseline: `main` @ `7d65a38b27a6cab0e4e9211d7f3a257e641fa029`
(v0.1.0, tag object `2e8e611ea8730979ab9f5e0a8081302344a7d1cf`).
Rama: `feat/regulatory-record-g5`.

## Pregunta del gate (falsable)

> ¿Mantiene la arquitectura FinReg sus garantías de identidad,
> provenance y determinismo al pasar de 20 entidades seleccionadas a
> una **fracción material del universo regulado español** a nivel de
> identidad y búsqueda?

v0.1.0 demostró que el modelo funciona con 20 fichas excelentes.
G5-A demuestra que el **universo es buscable**: cualquier entidad
regulada relevante resuelve a una entidad canónica (o a una
resolución explícitamente ambigua), aunque su ficha tenga cobertura
parcial.

## Modelo de dos niveles (declarado)

```text
UNIVERSO BUSCABLE                    FICHA ENRIQUECIDA (G5-B, sucesor)
────────────────────────────         ──────────────────────────────
identidad + regulador                permissions / branches
+ nº registro oficial                passporting / agents / funds
+ NIF/LEI cuando exista              administrators / audits
+ tipo + estado básico + fuente      sanctions / warnings / timeline
```

G5-A construye **solo** el nivel de universo buscable. Las fichas
enriquecidas de las 20 entidades actuales quedan intactas como
**corpus golden de regresión**: no se reemplazan ni se degradan.

## Universo objetivo (declarado a priori)

| Fuente | Ámbito |
|---|---|
| CNMV | ESI, SGIIC, EAF y demás categorías relevantes del registro |
| BdE | entidades de crédito, EDE, entidades de pago, sucursales, otros registros oficiales |
| DGSFP | aseguradoras españolas, sucursales, EEE operando en España (vía OpenDGSFP completo) |
| EBA | payment institutions relevantes para ES |
| ESMA | CASP MiCA |

Ya congelado y reutilizable (no se recaptura sin motivo):
`fixtures/g1` y `fixtures/g2` — BdE `bde-registro-entidades-credito`,
`bde-registro-entidades`, `bde-registro-servicios-pago`,
`bde-registro-con/sin-establecimiento`, `bde-registro-psp-excluidos`;
EBA `eba-psd2-*.zip`; ESMA `esma-mica-casps.csv`, `esma-mica-ncasp.csv`;
`bde-mfi-es.csv`.

Requiere captura nueva (manifiesto sucesor, nunca sobreescritura):
listados completos CNMV por categoría, export completo OpenDGSFP.

## Resultados válidos (declarados a priori)

- Una fuente objetivo puede resultar `SOURCE_UNAVAILABLE` o
  `LIST_NOT_PUBLISHED`: válido si queda registrado con evidencia y la
  cobertura se mide contra las fuentes efectivamente disponibles.
- La cobertura se mide **por fuente** contra el conteo declarado por
  la propia fuente cuando existe; donde no existe, contra el conteo
  observado en la captura, declarando la limitación.
- Filas no parseables = finding clasificado con conteo, nunca drop
  silencioso.
- Una entidad del universo puede tener ficha con superficies
  `NO_EVIDENCE` / `SURFACE NOT COVERED`: es el resultado correcto,
  no un defecto.
- Las 10 entidades de la prueba de producto (U-06) pueden resolver a
  `AMBIGUOUS` o `KNOWN_ABSENT` con motivo declarado — válido; lo
  inaceptable es el cero-resultados silencioso.
- El `bundle_sha256` de la proyección **va a cambiar** respecto a
  v0.1.0 (hay más entidades): lo inaceptable es la divergencia entre
  dos builds consecutivos sobre los mismos inputs.

## Casos preregistrados

### U-01 Inventario y congelado de fuentes de universo

Para cada fuente objetivo: (a) reutilizar el snapshot ya congelado
citando su manifiesto, o (b) captura nueva con manifiesto sucesor
(`retrieved_at`, `sha256`, `bytes`, `source_as_of` cuando la fuente
lo publique), o (c) `SOURCE_UNAVAILABLE` con evidencia.
**Esperado:** toda fuente objetivo queda en uno de los tres estados;
sin cuarta vía.

### U-02 Extracción de identidad por fuente

Parse de cada listado a registros de identidad: nombre oficial,
identificadores (nº registro + esquema, NIF, LEI cuando exista),
tipo, estado básico, fuente. Se registra `parse_success_rate` por
fuente y el conteo de filas rechazadas con causa.
**Esperado:** PASS con tasas por fuente en el informe; filas
rechazadas siempre clasificadas.

### U-03 Resolución canónica

Joins entre fuentes **únicamente** sobre identificadores oficiales
exactos (nº registro + esquema, NIF, LEI). Prohibido el join por
similitud de nombre para hechos; nombres colisionados producen
candidatos de desambiguación, no merges.
**Esperado:** 0 fuzzy canonical joins (verificable en código + test).

### U-04 Auditoría de duplicados

Cada entidad canónica fusionada cita el identificador oficial
compartido que la justifica. Duplicados canónicos inexplicados = 0.
**Esperado:** PASS; cada duplicado residual queda clasificado con
motivo o se corrige la resolución.

### U-05 Cobertura del universo

≥95% del universo objetivo descubierto, medido por fuente contra su
conteo declarado u observado (con la limitación declarada donde no
exista conteo oficial). 100% de las entidades incluidas lleva
identificador oficial estable donde la fuente lo ofrece.
**Esperado:** tabla de cobertura por fuente en el informe.

### U-06 Contrato de búsqueda

Resolución exacta por: nombre, alias conocido, NIF, LEI, nº CNMV,
código BdE, clave DGSFP. Prueba de producto — estas 10 cadenas
deben producir entidad o resolución explícitamente ambigua/ausente
con motivo, nunca cero-resultados silencioso:

```text
Santander · BBVA · Renta 4 · MyInvestor · Revolut
Mapfre · AXA · Alantra · Abanca Gestión · Pecunia
```

**Esperado:** cada cadena → `RESOLVED` | `AMBIGUOUS(motivo)` |
`KNOWN_ABSENT(motivo)`, con evidencia en el informe.

### U-07 Regresión del corpus golden

Las 20 entidades v0.1.0 conservan `entity_id` estable y sus fichas
enriquecidas se reconstruyen sin degradación. Hechos nuevos sobre
ellas provenientes de listados de universo son admisibles **solo**
si son aditivos y citan evidencia (diff declarado en el informe);
jamás sustituyen ni eliminan hechos golden.
**Esperado:** diff golden = ∅ o estrictamente aditivo documentado.

### U-08 Escala operativa

Medición sobre el build resultante: nº de entidades, nº de páginas,
tiempo de build, tamaño `dist/`, tamaño índice Pagefind, transfer
de ficha identidad vs enriquecida. Si el número de páginas hace el
build inviable, la decisión (p.ej. fichas identidad vs indexación
sin página) se declara en el informe — es un resultado del gate, no
un cambio de criterio.
**Esperado:** métricas registradas; Pagefind/build operativo.

### U-09 Determinismo

Dos builds consecutivos sobre los mismos inputs → mismo
`bundle_sha256`.
**Esperado:** `sha_run1 == sha_run2`.

### U-10 Provenance

Toda aserción de identidad del universo cita artefacto fuente +
sha256. Ninguna entidad aparece sin fuente.
**Esperado:** PASS verificable por muestreo + test estructural.

### U-11 Reporte

`docs/gates/G5-A-REPORT.md` con veredicto por caso U-01..U-10,
tabla de cobertura por fuente, métricas de escala y límites
declarados.
**Esperado:** existe y cierra el gate con GO / CONDITIONAL / NO-GO.

## Fuera de scope (declarado)

- G5-B (detail scale-out: enriquecimiento automático de fichas):
  requiere su propio preregistro.
- Nuevas features de frontend, comparador, alertas, API, gráficos.
- Dominio propio, rename de repo/directorio, redesign visual.
- Ratings, scores, rankings, recomendaciones — permanentemente.
- Merge a `main` / tag / release hasta que el gate lo determine.
- Reescritura de historia; los manifiestos históricos no se tocan.

## Sucesor declarado

**G5-B — Detail Scale-Out**: enriquecer fichas con las superficies
ya probadas en el corpus golden (permissions, branches, passporting,
agents, funds, administrators, audits, sanctions, warnings,
timeline), midiendo parse success, coverage por superficie,
requests/entidad, bytes, anomalías, schema drift, false joins y
false adverse attribution. Se preregistrará cuando G5-A cierre.
