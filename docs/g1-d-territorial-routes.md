# G1-D — Territorialidad: freeze jurídico (D1) + matriz de rutas (D2)

## Objetivo

Congelar el modelo legal y la matriz territorial **antes** de cualquier
regla de derivación. Este documento es D1+D2: fuentes, hipótesis y
matriz. No implementa derivación ni genera aserciones territoriales.

## Modelo semántico (congelado)

```text
entry_mechanism
= mecanismo jurídico de base (cómo la entidad obtuvo su entitlement
  en origen)
  AUTHORISATION / NOTIFICATION / REGISTRATION

territorial_basis
= base territorial en el Estado miembro consultado
  DOMESTIC / BRANCH / FREEDOM_TO_PROVIDE_SERVICES

legal_basis
= incluye tanto la base como la activación territorial
  ej. MiCA 63 + 65; autorización PI + PSD2 art. 28
```

El procedimiento territorial **activa** un entitlement de origen; no lo
redefine. Ejemplos canónicos:

```text
CASP art.63 + LP España:
  entry_mechanism  = AUTHORISATION
  territorial_basis = FREEDOM_TO_PROVIDE_SERVICES
  legal_basis       = MiCA 63 + 65

PI PSD2 + FPS España:
  entry_mechanism  = AUTHORISATION
  territorial_basis = FREEDOM_TO_PROVIDE_SERVICES
  legal_basis       = autorización PI + PSD2 art. 28
```

Prohibido: usar `NOTIFICATION` para describir "la comunicación del
passport" cuando el mecanismo base es `AUTHORISATION`. `NOTIFICATION`
es el mecanismo de base del art. 60 MiCA (y equivalentes), no un
sinónimo de "hubo comunicación entre autoridades".

## D1 — Freeze jurídico y fuentes

| Fuente | Snapshot | Verificación |
|---|---|---|
| Reglamento (UE) 2023/1114 (MiCA) ES | `raw/eurlex-mica-2023-1114-es.html` (manifest-g1-c1) | arts. 59(7), 60(10), 63, 65(4) verificados en texto congelado |
| Directiva (UE) 2015/2366 (PSD2) ES | `raw/doue-psd2-2015-2366-es.pdf` (manifest-g1-d1) | DOUE L 337/35; texto operativo verificado en PDF (art. 28, agentes, sucursal, LPS) |
| Reg. Delegado (UE) 2017/2055 ES | `raw/doue-rd-2017-2055-es.pdf` (manifest-g1-d1) | DOUE L 294/1; identidad documental verificada (catálogo BdE + LSU EUR-Lex); verificación a nivel de artículo diferida (fuentes subset CID) |
| Sede electrónica BdE, trámite transfronterizo | `raw/bde-actividad-transfronteriza-pago-ue.html` (manifest-g1-d1) | procedimiento operativo verificado (2 meses objeción sucursal, LPS comunicación, agentes, modificaciones 1 mes) |
| Lista CNMV PSC criptoactivos | `raw/cnmv-psc-criptoactivos.pdf` + `extracted/cnmv-psc-extract.json` | categorías territoriales reales: LP, SUCURSAL, LIMITED LP |
| EBA PSD2 register spec + RTS/ITS | `raw/eba-psd2-json-data-specification.xlsx`, `raw/eu-2019-410.pdf`, `raw/eu-2019-411.pdf` (manifests G1-B) | congelados desde G1-B |
| Reg. de Ejecución (UE) 2019/410, 2019/411 | `raw/eu-2019-410.pdf`, `raw/eu-2019-411.pdf` | congelados desde G1-B (pormenores de notificación a EBA) |

Hallazgos jurídicos congelados:

```text
MiCA art. 59(7): los PSC pueden prestar servicios en toda la Unión,
  mediante establecimiento (incl. sucursal cuando aplique) o libre
  prestación; sin exigencia de presencia física en el Estado de acogida.

MiCA art. 60(10): exime a las entidades art.60 de los arts. 62, 63,
  64, 67, 83 y 84 — el art. 65 NO está en la lista → el procedimiento
  transfronterizo sigue aplicable a entidades art.60. Señal textual
  congelada; efecto operativo preregistrado como H12 (ver matriz).

MiCA art. 65(4): el prestador puede comenzar a prestar en el Estado de
  acogida al recibir la comunicación de la autoridad de origen, o a más
  tardar 15 días naturales tras presentar la información.

PSD2 art. 28: la entidad comunica a su AC de origen Estados y
  servicios; para agentes/sucursales, la actividad sólo puede empezar
  tras su inscripción (registro en el Estado de acogida).

BdE (transposición operativa): sucursal → notificación + 2 meses sin
  objeción del supervisor de destino + comunicación de inicio; LPS →
  comunicación previa al BdE; agentes → comunicación + inscripción;
  modificaciones → notificación ≥ 1 mes antes.
```

**No congelado / pendiente:** EUR-Lex devolvió stubs anti-bot para la
versión consolidada de PSD2 (02015L2366-20250117) y del Reg. 2017/2055;
los archivos descargados fueron descartados (13.692 bytes idénticos,
shell genérico). Se usó el espejo DOUE de BOE (texto oficial original,
bytes inmutables). La consolidación posterior de PSD2 no toca art. 28
(el corrigendum DOUE L 191/7, 16.6.2020, corrige art. 37(2)).

## H12 — Hipótesis preregistradas

```text
H12-A PSD2/FPS:
  home entitlement ACTIVE + servicio exacto + host=ES +
  procedimiento passport completado
  → puede sostener ENTITLED_TO_PROVIDE en España con
    territorial_basis = FREEDOM_TO_PROVIDE_SERVICES.
  entry_mechanism permanece = el de origen (AUTHORISATION).

H12-B MiCA/LP:
  home entitlement MiCA + servicio + España + fecha efectiva de la
  ruta (art. 65(4): recepción de comunicación o ≤15 días naturales)
  → puede sostener entitlement territorial con
    territorial_basis = FREEDOM_TO_PROVIDE_SERVICES,
    legal_basis incluye MiCA 65.

H12-C MiCA/branch:
  sucursal y LP son rutas territoriales distintas aunque descansen en
  el mismo entitlement de origen; territorial_basis = BRANCH. No son
  conflictos entre sí ni con la ruta doméstica.

H12-D multi-route:
  AUTHORISATION+FPS, AUTHORISATION+BRANCH, y varias rutas
  territoriales simultáneas → COMPATIBLE_MULTI_ROUTE, salvo
  contradicción real en hechos equivalentes.

H12-E LIMITED_LP:
  no emitir nada hasta demostrar con fuente primaria qué significa
  «LIMITED PSC EN RÉGIMEN DE LP». Prohibido inferirlo del label.
  Estado actual: categoría observada como epígrafe en la lista CNMV,
  sin filas en el extract y sin fuente primaria que la defina.
```

## D2 — Matriz territorial (source × route × trigger × service × date)

| Ruta | Fuente de origen | Mecanismo base | territorial_basis | Trigger territorial (procedimiento completado) | Servicio | Fecha efectiva | ¿Emite entitlement? | Limitaciones |
|---|---|---|---|---|---|---|---|---|
| PSD2 FPS | registro home NCA (BdE/EBA) | AUTHORISATION | FREEDOM_TO_PROVIDE_SERVICES | notificación art. 28 completada (home→host; EBA registro refleja passport services) | servicio PSD2 exacto declarado para ES | fecha de inicio tras comunicación (sin plazo fijo como MiCA; el registro EBA es la evidencia pública) | SÍ si trigger + servicio + host demostrados | el country-code EBA solo ≠ trigger; requiere evidencia de procedimiento completado |
| PSD2 branch/establecimiento | registro home NCA + registro host (BdE «con establecimiento») | AUTHORISATION | BRANCH | notificación + 2 meses sin objeción + comunicación de inicio de actividades; **inscripción** | servicio PSD2 exacto | fecha de inicio declarada tras objeción/inscripción | SÍ sólo con inscripción demostrada | sin inscripción → procedimiento incompleto → no emite |
| PSD2 agents | registro home NCA + inscripción de agentes | AUTHORISATION | BRANCH/FPS según canal | comunicación + inscripción del agente | servicio PSD2 exacto | post-inscripción | diferido: sin evidencia de inscripción de agente en corpus | requiere fuente de inscripción (BdE) |
| MiCA LP (art. 65) | registro ESMA/NCA origen + lista CNMV | AUTHORISATION (63) o NOTIFICATION (60) | FREEDOM_TO_PROVIDE_SERVICES | comunicación art. 65 home→host (CNMV lista «PSC EN RÉGIMEN DE LP» como evidencia pública de procedimiento completado) | servicio MiCA exacto (letra a–j) | `cnmv_services_from` (fecha CNMV «desde la que puede prestar») | SÍ si trigger CNMV + servicio + fecha | no usar `ae_authorisationNotificationDate` como fecha territorial; `ac_serviceCode_cou=ES` solo ≠ trigger |
| MiCA branch (art. 59(7)) | lista CNMV «PSC QUE PRESTA SERVICIOS EN ESPAÑA A TRAVÉS DE SUCURSAL» | AUTHORISATION (63) | BRANCH | categoría CNMV sucursal (evidencia pública de establecimiento) | servicio MiCA exacto | `cnmv_services_from` | SÍ si trigger + servicio + fecha | distinto de LP aunque mismo entitlement base; no colapsar |
| art. 60 cross-border | ESMA CASP (entidad art.60, home≠ES) + lista CNMV territorial | NOTIFICATION | FREEDOM_TO_PROVIDE_SERVICES | art. 65 sigue aplicable (60(10) no lo exime) → mismo trigger que MiCA LP | servicio MiCA dentro de equivalencia art.60 | `cnmv_services_from` | preregistrado por H12; **no hay fila real aún** en extract CNMV | verificar en D3 que exista caso real antes de regla positiva |
| LIMITED_LP | lista CNMV «LIMITED PSC EN RÉGIMEN DE LP» | DESCONOCIDO | DESCONOCIDO | DESCONOCIDO | — | — | NO — abstención siempre | sin fuente primaria que defina el régimen; epígrafe observado sin filas |
| multi-route | cualquier combinación anterior | el de cada ruta | el de cada ruta | cada ruta con su propio trigger | por servicio | por ruta | cada ruta emite su propia aserción | `COMPATIBLE_MULTI_ROUTE` salvo contradicción real en hechos equivalentes |

### Semántica de campos ESMA (congelada desde G1-C)

```text
ac_serviceCode        = qué servicio
ac_serviceCode_cou    = país declarado para ese servicio
ac_serviceCode_cou    ≠ entitlement jurídico territorial por sí solo
```

Diferencia D vs C: en D el country-code puede **combinarse** con
evidencia de procedimiento territorial (categoría CNMV LP/sucursal,
passport services EBA). Nunca solo.

## Criterios fail-closed del gate D (congelados)

```text
0  country-code → entitlement directo
0  LP → DOMESTIC
0  branch → FPS (ni FPS → branch)
0  LIMITED_LP resuelto sin fuente primaria
0  home authorisation perdida al añadir territorialidad
0  conversión silenciosa de mecanismo (passport ≠ NOTIFICATION)
0  conflicto automático entre rutas compatibles
0  aserción territorial positiva sin trigger de procedimiento
   completado demostrado
0  fallback de fecha territorial a ae_authorisationNotificationDate
replay G0 / G1-A / G1-C byte-idéntico
```

## Secuencia restante (fuera de este commit)

```text
D3  corpus real preregistrado
    PSD2 FPS / MiCA LP / MiCA branch / art.60 cross-border /
    LIMITED_LP unresolved / multi-route
D4  derivation delta
D5  assessment + divergence audit
```

## Estado

```text
D1  DONE — freeze jurídico: MiCA 59(7)/60/65 verificado en texto;
    PSD2 art.28 (DOUE L 337) y RD 2017/2055 (DOUE L 294) congelados
    como bytes oficiales; procedimiento operativo BdE congelado;
    categorías CNMV territoriales ancladas
D2  DONE — matriz territorial congelada; semántica
    entry_mechanism / territorial_basis / legal_basis fijada
D3+ PENDIENTE — ninguna regla de derivación territorial existe aún;
    derivation.py intacto desde G1-C
```
