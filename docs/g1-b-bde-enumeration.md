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

## Estado

```text
B1  PASS (evidencia congelada, 15 snapshots)
B2  universe matrix inicial — en curso
H10-A  STRONGLY PLAUSIBLE para clases domestic + branch;
       OPEN para FPS (notificación ≠ inscripción previa)
H10-B  estructura capability-level existe (ACTIVIDADES con normativa);
       exhaustividad normativa por verificar
H10-C  OPEN — depende de clase × régimen × fecha; no global
```

## Próximos pasos

```text
B3  comparar categorías públicas vs rutas legales (47 tipos vs
    mecanismos); huecos conocidos: FPS recién notificado, agentes,
    distribuidores, híbridas
B4  casos reales positivos + ausentes (slice preregistrado)
B5  decidir H10-A/B/C por clase, no globalmente
B6  sólo si COMPLETE_ENUMERATION queda probado para algún slice:
    diseñar regla negativa acotada (entity_class × activity ×
    territorial_basis × ventana temporal)
```
