# G1-B — BdE: enumeración y negative_evidence_capability

Workstream G1-B de `docs/g1-scope.md`. Investigación de evidencia;
ningún cambio de reglas/contratos hasta B5.

## Hipótesis (refinamiento de H10 preregistrado)

```text
H10-A — POPULATION COMPLETENESS
Para una clase regulatoria concreta y un régimen concreto,
¿toda entidad legalmente habilitada en España debe aparecer
en algún registro público identificable del BdE?

H10-B — CAPABILITY COMPLETENESS
Dada una entidad presente en ese universo,
¿el registro público permite determinar exhaustivamente
qué actividad concreta puede prestar?

H10-C — NEGATIVE SUFFICIENCY
¿la ausencia de una entidad/actividad en esa enumeración,
para una fecha y régimen concretos,
permite derivar NOT_ENTITLED?
```

Resultados posibles preregistrados:

```text
COMPLETE_ENUMERATION   → obligación jurídica de inclusión
                       + publicación exhaustiva
                       + alcance temporal/capability suficiente
EXPLICIT_NEGATIVE_ONLY → prueba positivos; ausencia no cierra rutas
NO_NEGATIVE_INFERENCE  → la clase puede operar fuera del universo
```

Regla de lectura: "registered to operate" ≠ "register exhaustively
encodes every permitted service". H10-B exige que el campo de
actividad sea normativamente completo para la clase, no sólo
informativo.

## B1 — Evidencia congelada

Capture `g1-b1-2026-09-14` (`fixtures/g1/sources/manifest-g1-b1.json`,
15 snapshots SHA-256):

```text
Declaración oficial (H10-A)
  bde-registros-entidades-landing.html        quién puede operar
  bde-registros-informacion-otros-registros   mapa de listas
  bde-entidades-inscritas-registros-oficiales.pdf  índice por clase
  bde-entidades-extranjeras.html              sucursal vs LPS
  bde-sede-autorizacion-entidades-pago.html   ruta PI ordinaria
  bde-sede-registro-poco-volumen.html         ruta registro simplificado
  bde-sede-registro-aisp.html                 ruta AISP
  bde-sede-registro-exclusion-red-limitada    ruta exclusión art. 3
  bde-rbe-spa-landing.html                    app consulta (JS shell)

Enumeración máquina-legible (H10-B)
  bde-registro-entidades.xlsx                 5 661 entidades, todo el registro
  bde-registro-servicios-pago.xlsx            210 prestadores de pago
  bde-registro-entidades-credito.xlsx         entidades de crédito
  bde-registro-con-establecimiento.xlsx       con establecimiento (≈ sucursales)
  bde-registro-sin-establecimiento.xlsx       sin establecimiento (≈ LPS)
  bde-registro-psp-excluidos.xlsx             excluidos RDL 19/2018
```

## B1 hallazgos

1. **Afirmación oficial de suficiencia** (landing): los registros
   «permiten comprobar quién puede operar legalmente y en qué tipo de
   actividad financiera»; «solo aquellas que cumplen todos los
   requisitos establecidos por la normativa pueden figurar
   oficialmente»; el BdE «publica esta información en cumplimiento de
   una obligación legal». Datos actuales **e históricos**.

2. **Asimetría sucursal/FPS confirmada en fuente primaria**
   (`bde-entidades-extranjeras.html`): las sucursales deben
   inscribirse **antes** de iniciar actividad; en libre prestación de
   servicios pueden iniciar cuando el BdE **recibe la notificación**
   de la autoridad de origen. → `BRANCH` y `FREEDOM_TO_PROVIDE_SERVICES`
   no comparten lógica de exhaustividad: para FPS, la inscripción no
   es condición previa del entitlement (podría haber entidad operando
   legalmente con notificación recibida pero alta aún no publicada).

3. **Rutas jurídicas distintas por clase** (Sede): autorización
   ordinaria EP / registro simplificado bajo volumen / registro AISP /
   registro de exclusión por red limitada — cuatro mecanismos, cuatro
   `entry_mechanism` potenciales.

4. **La enumeración existe y es capability-level**:
   - `DATOS GENERALES`: CÓDIGO BE, NIF, TIPO ENTIDAD (47 códigos),
     LEI, FECHA ALTA, PAÍS ORIGEN, AUTORIDAD COMPETENTE, **FECHA BAJA +
     MOTIVO BAJA + SUCESORAS** (3 283 de 5 661 conservan baja —
     histórico real, no sólo snapshot).
   - `ACTIVIDADES`: por entidad, **NORMATIVA + CÓDIGO ACTIVIDAD +
     ACTIVIDAD + FECHA DE ALTA ACTIVIDAD** — ámbito por entidad con
     base legal.
   - `ACTIVIDAD TRANSFRONTERIZA`: **FORMA DE OPERAR** (Agentes /
     Distribuidores / Libre prestación / Sucursal) × país × actividad.

5. **Censo `TIPO ENTIDAD`** (Registro_Entidades): incluye
   `21` (entidad de crédito comunitaria en LPS, 1 183), `11.2`
   (extracomunitaria LPS), `TESECC/TESECE` (sucursales), `TEEP`,
   `TEEDE`, `TEPSIC`, `TEEPEX`, `TEEFEP/TEEPH` (híbridas),
   `PSP_excluidos` aparte, más ICI/prestamistas/tasadores/cripto
   (registro cripto cerrado — nota oficial congelada).

## B2 — Matriz de universo (slice inicial)

```text
clase / régimen            entry_mech.   registro público BdE      inscripción previa  ausencia interpretable?
domestic PI (TEEP)         AUTHORISATION ServicioPagos DATOS+ACT.   sí (art. LPSE)      candidata fuerte
domestic EMI (TEEDE)       AUTHORISATION idem                        sí                  candidata fuerte
AISP (TEPSIC)              REGISTRATION  idem                        sí                  candidata
small-volume PI (TEEPEX)   REGISTRATION  idem (art.14 RDL 19/2018)   sí (simplificado)   candidata
foreign EU branch (TESEPC) NOTIFICATION  idem                        SÍ — antes de operar candidata
foreign EU FPS (cod 21/LPS) NOTIFICATION Entidades + ACT.TRANSFR.    NO — basta notificación recibida  DÉBIL
```

## B3 — Clasificación por ruta jurídica + comprobaciones mecánicas

### Los 47 `TIPO ENTIDAD` por ruta legal

```text
A. AUTORIZACIÓN PROPIA (domestic, inscripción tras autorización)
   TEEP PI · TEEDE EMI · TEBP/TEBL/TEBN/TEBR banca · TECA cajas ·
   TECC/TECCC/TECRC/TECRNC/TEOCC cooperativas · TECO crédito oficial ·
   TEEFC EFC · TESAF arrendamiento · TESCH créd. hipotecario ·
   TESGR garantía recíproca · TESDEC dominantes · TEEF/TESF/TESFC/
   TESFMC financiación · TESR reafianzamiento · TESMMD mediadoras
   dinero · TEST tasación · TEECVM/TEECVT cambio moneda · TEECCP L25/91

B. REGISTRO (régimen simplificado / específico)
   TEPSIC AISP · TEEPEX exenta art.14 RDL 19/2018 · ICI/PI inmobiliario

C. PASAPORTE / CROSS-BORDER
   TESECC/TESECE sucursal CI UE/no-UE · TESEPC sucursal EP UE ·
   TESEDC sucursal EDE UE · TESEFC sucursal filial · SICI sucursal ICI ·
   21/11.2 CI comunitaria/extra. en LPS · 19 filial comunitaria LPS ·
   ICILPS ICI en LPS · TEOR oficina representación · TEBEX banca ext.

D. ACTORES DERIVADOS (capacidad delegada, anclada al principal)
   Agentes → app propia app.bde.es/age_www (no independientes)
   Distribuidores → Listado_de_distribuidores.xls (distribución/
   reembolso de dinero electrónico por cuenta de la EDE declarante)

E. EXCLUSIONES (notificación de exclusión, no autorización)
   PSP_excluidos.xlsx — art. 3 RDL 19/2018: red limitada / telecom.
   EXCLUDED_ACTIVITY_NOTIFIED ≠ AUTHORISATION ≠ NOT_ENTITLED

F. HÍBRIDAS
   TEEFEP / TEEPH / TEEFPH — EFC o mixtas con facultad de pago

G. OTROS / CERRADOS
   CRIPTO (registro cerrado por fin período transitorio — nota oficial)
```

### Cuatro comprobaciones mecánicas sobre `ACTIVIDADES`

```text
1. ¿toda entidad de la clase tiene ≥1 actividad?
   188/190 en ServicioPagos; 2 sin actividad (1 sucursal EP UE,
   1 híbrida EFC-EP) — casi completo, con excepciones nombrables.

2. ¿diccionario jurídico estable de códigos?
   Sí: códigos = taxonomía real de servicios PSD2/LPSE (1,2,3.A-C,
   4.A-C,5.A-B,6,7=PIS,8=AIS) + A/B/C dinero electrónico (Ley 21/2011)
   + A.1-D actividades EFC (Ley 5/2015). Cada fila lleva NORMATIVA.

3. ¿ausencia de actividad = no habilitada?
   Cobertura casi total sugiere que sí para entidades presentes,
   pero queda por demostrar normativamente (B4/B5): la hoja declara
   ámbito autorizado, no afirma exhaustividad por sí misma.

4. ¿historia por actividad reconstruible?
   NO: sólo FECHA DE ALTA ACTIVIDAD; no hay fecha de cese por
   actividad. La historia existe a nivel entidad (FECHA BAJA/MOTIVO),
   no a nivel capability. Además 85 entidades dadas de baja conservan
   sus filas de actividad → ACTIVIDADES refleja ámbito autorizado
   histórico; la vigencia la gobierna FECHA BAJA de la entidad.
```

### Hallazgo estructural: cobertura LPS asimétrica

`Registro_SinEstablecimiento` sólo contiene tipos LPS de **entidad de
crédito** (21, 11.2, 19), ICI y cripto-cerrado. **No existe tipo LPS
para entidad de pago/EDE**: las PI/EMI extranjeras en libre prestación
en España viven en el registro EBA (services_raw por país) y en la
vía notificación-NCA, no en la enumeración pública BdE.

```text
absence in BdE + foreign PI under FPS → NO interpretable
(universo incorrecto; la enumeración de esa ruta es EBA, no BdE)
absence in BdE + domestic PI          → candidata fuerte
```

Esto responde parcialmente a H10-A por la negativa: el universo BdE
**no** cubre todas las rutas legales para prestar servicios de pago
en España. La exhaustividad sólo puede predicarse por slice.

### Tabla de decisión por ruta

```text
ruta              inclusión oblig.  enum. pública  lag publicación  capability repr.  historia  ausencia candidata
domestic PI/EMI   sí (autorización) sí (XLSX)      bajo (obligación) sí (ACTIVIDADES)  entidad   STRONG
AISP              sí (registro)     sí             bajo              sí (código 8)     entidad   STRONG
exenta art.14     sí (reg. simplif.) sí            bajo              sí                entidad   STRONG
EU branch         sí (antes operar) sí             bajo              sí                entidad   STRONG
EU FPS (CI)       notificación      sí (cod 21)    VENTANA FALSA-    parcial           entidad   WEAK
                                                   AUSENCIA posible
EU FPS (PI/EMI)   notificación      NO en BdE      n/a (otro registro) n/a             n/a       NO (vía EBA)
agente            declaración       app separada   n/a               delegada          ?         NO (independiente)
distribuidor      declaración       xls separado   n/a               delegada          ?         NO (independiente)
excluido PSP      notificación exc. xls separado   n/a               n/a               sí        NO (no es ruta PSP)
```

0 códigos sin asignar; rutas conocidas presentes. Agentes/
distribuidores nunca → entitlement independiente. Excluidos nunca →
autorización PSP ni negativo PSP.

## Estado

```text
B1  PASS (evidencia congelada, 17 snapshots)
B2  universe matrix inicial — superado por clasificación B3
B3  47/47 códigos → ruta jurídica · comprobaciones mecánicas hechas
H10-A  por slice: STRONG domestic+branch+registro;
       NO para PI/EMI extranjera en LPS (su enumeración es EBA, no BdE)
H10-B  diccionario jurídico estable; falta fecha de cese por actividad
       → historia por capability no reconstruible (sólo alta + baja
       a nivel entidad)
H10-C  ausencia domestic candidata fuerte; LPS-CI weak (ventana de
       publicación); LPS-PI/EMI no interpretable; agentes/distribuidores/
       excluidos fuera de la inferencia negativa
H10    NO global — sólo por slice (ruta × actividad × fecha)

B4  ejecutado — ver resultados arriba
POPULATION_COMPLETENESS
  domestic PI/EMI/AISP/excluidos  PROVEN en este corpus
    (cross-ref EBA↔BdE: 0 activos ES ausentes; excluidos enrutados)
  PI/EMI extranjera LPS           CONTRADICTED (vive en EBA)
CAPABILITY_COMPLETENESS
  acuerdo código-a-código EBA↔BdE demostrado (B4-04)
  divergencia real existente (B4-03 Fintonic) → no promover
  capability-negative sin resolver T1↔T2 primero
  historia por actividad: NO reconstruible (sin fecha de cese)
PUBLICATION_TIMELINESS
  domestic/branch  SAFE candidato · LPS-CI  LAG_RISK ·
  LPS-PI/EMI  N/A (otro registro)
```

## B4 — Casos adversariales preregistrados (comparador independiente)

Regla anti-circularidad: ningún caso se valida con otro extracto del
mismo XLSX. Comparador primario = snapshot EBA PSD2 congelado
(`h4-eba-psd2-20260913.zip`, reporte NCA→EBA, con `ENT_NAT_REF_COD`
= CÓDIGO BE) + fuentes de ruta específica (PSP_excluidos, age_www,
distribuidores).

**Hecho de cross-ref ya establecido**: todas las entidades ES
`PSD_PI/EMI/EPI/AISP` activas en EBA están presentes en BdE; las
`PSD_EXC` ausentes de ServicioPagos aparecen TODAS en
`PSP_excluidos` → cobertura enrutada, no hueco.

| Caso | Entidad real | Comparador | Esperado |
|---|---|---|---|
| B4-01 ACTIVE_DOMESTIC_PI | 6950 PROSEGUR CUSTODIA ACTIVOS DIGITALES | EBA PSD_PI ACTIVE | presente + actividades coherentes |
| B4-02 ACTIVE_DOMESTIC_EMI | 6722 GETNET EMONEY EDE | EBA PSD_EMI ACTIVE | presente + A/B/C e-money |
| B4-03 ACTIVE_AISP | 6935 FINTONIC AGREGACIÓN | EBA PSD_AISP ACTIVE | presente, mecanismo REGISTRATION |
| B4-04 PARTIAL_CAPABILITY | 6950 PROSEGUR | EBA `PS_03C` único ↔ BdE `3.C` único | acuerdo código-a-código; ausencia de otros códigos = candidata negativa |
| B4-05 RETAINED_WITHDRAWN | 8832 BANKINTER CONSUMER FINANCE | EBA WITHDRAWN + FECHA_BAJA BdE | filas conservadas; 0 entitlement actual |
| B4-06 ACTIVE_BRANCH | 6804 AMERICAN EXPRESS PAYMENT SERVICES (TESEPC) | inscripción previa obligatoria | presencia obligatoria en slice |
| B4-07 FPS_CREDIT_INSTITUTION | E024 REDIEM CAPITAL AB (cod 21) | autoridad origen (FI) | ausencia nunca → negativo (lag) |
| B4-08 FPS_PI_EMI | 329 PI extranjeras activas con servicio ES en EBA (ej. PIPO LU, LU_CSSF) | registro EBA | ausentes de BdE → demuestra que el universo vive en EBA |
| B4-09 DISTRIBUTOR | ERSTE BANK et al. en Listado_distribuidores | registro delegado | capacidad delegada; 0 entitlement propio |
| B4-10 EXCLUDED_PSP | S41C ZALANDO PAYMENTS GMBH | EBA PSD_EXC ACTIVE | EXCLUDED_ACTIVITY_NOTIFIED; ≠ autorización ≠ negativo |

**Divergencia detectada durante la selección (a documentar en B4):**
FINTONIC 6935 — EBA reporta sólo `PS_080` (AIS); BdE le atribuye
códigos `7` (PIS), `8` (AIS) y `1`. Si BdE T1 y EBA T2 discrepan en
el capability set, la regla de conflicto preregistrada en A5
(`CONFLICTING_SOURCE_ASSERTIONS → INDETERMINATE`) es la correcta;
no se resuelve por tier silenciosamente.

**Regla temporal fijada:**

```text
entity FECHA_BAJA != null + filas de actividad conservadas
→ current capability = INACTIVE (la actividad es histórica)

activity rows alone ≠ current entitlement
```

**Taxonomía de resultados por slice (B4/B5):**

```text
POPULATION_COMPLETENESS  PROVEN | NOT_PROVEN | CONTRADICTED
CAPABILITY_COMPLETENESS  PROVEN | NOT_PROVEN | CONTRADICTED
PUBLICATION_TIMELINESS   SAFE_FOR_NEGATIVE | LAG_RISK | N/A
```

### B4 — Resultados de ejecución

```text
B4-01  PROSEGUR 6950     PASS — presente (TEEP), sin baja, EBA ACTIVE
B4-02  GETNET 6722       PASS — presente (TEEDE), A+B+C e-money + 3.C
B4-03  FINTONIC 6935     DIVERGENCIA REAL —
       BdE: tipo TEEP, actividades {7 PIS, 8 AIS, 1}
       EBA: PSD_AISP, services {PS_080=AIS}
       T1 y T2 discrepan en clase Y capability → caso semilla para
       CONFLICTING_SOURCE_ASSERTIONS → INDETERMINATE
B4-04  PROSEGUR 6950     PASS — acuerdo código-a-código exacto:
       EBA PS_03C ↔ BdE 3.C (único servicio en ambos). La ausencia de
       otros códigos coincide con la evidencia independiente →
       capability-absence es candidata negativa FUERTE para este slice
B4-05  BANKINTER 8832    PASS con matiz — 12 filas históricas
       conservadas; BdE FECHA_BAJA 22/02/2019 (motivo:
       "transformación en otro tipo de entidad") ≠ EBA withdrawal
       2026-07-01. FECHA_BAJA BdE tiene semántica de entidad
       (baja/transformación), NO equivalente a retirada de
       autorización. Las dos fechas responden a hechos distintos.
B4-06  AMEX branch 6804  PASS — TESEPC presente con actividad 5
B4-07  REDIEM E024       cod 21 presente; ausencia seguiría siendo
       débil (lag notificación→publicación)
B4-08  FPS_PI_EMI        CONFIRMADO — 588 PI/EMI extranjeras activas
       con servicio ES en EBA; sólo 5 presentes en BdE (probablemente
       dual-listed con sucursal). El universo LPS-PI/EMI no existe
       en la enumeración pública BdE.
B4-09  DISTRIBUIDORES    listado separado con principales (incluye
       entidades extranjeras: Erste Bank, Sparkassen AT) → capacidad
       delegada, nunca independiente
B4-10  ZALANDO S41C      presente en PSP_excluidos + EBA PSD_EXC
       ACTIVE → EXCLUDED_ACTIVITY_NOTIFIED confirmado
```

## Próximos pasos

```text
B3  DONE — 47/47 tipos asignados a ruta legal; 0 códigos sin explicar;
    hallazgo clave: LPS-PI/EMI no enumeradas en BdE
B4  casos preregistrados con comparador EBA independiente;
    pendiente ejecución de los checks mecánicos por caso
B5  decidir H10-A/B/C por clase, no globalmente
B6  sólo si COMPLETE_ENUMERATION queda probado para algún slice:
    diseñar regla negativa acotada (entity_class × activity ×
    territorial_basis × ventana temporal)
```
