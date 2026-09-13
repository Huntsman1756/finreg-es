# G1-C — MiCA arts. 60/63: dos vías jurídicas, un `CONFIRMED_ENTITLED`

## Objetivo

Validar `ASSESSMENT_SEMANTICS_V2` con dos mecanismos jurídicos
distintos que producen el mismo resultado público:

```text
art. 63  PSC específico              → AUTHORISATION
art. 60  entidad financiera elegible → NOTIFICATION (condición
         procedimental explícita; no STATUTORY_ENTITLEMENT)
```

Sin resolver territorialidad (eso es G1-D) y sin `STATUTORY_ENTITLEMENT`.

## C1 — Evidencia congelada

```text
eurlex-mica-2023-1114-es.html   Reglamento (UE) 2023/1114, texto ES
                                (arts. 59, 60, 63, 109 verificados)
cnmv-psc-criptoactivos.pdf      lista oficial CNMV de PSC
esma-mica-page.html             página ESMA interim MiCA register
esma-mica-casps.csv             CASPs autorizados (346 filas, 15 ES)
esma-mica-ncasp.csv             entidades no conformes
esma-mica-description_of_the_fields_in_the_interim_mica_register.csv
                                diccionario oficial de campos
```

Estructura ESMA CASPS.csv: `ae_competentAuthority`,
`ae_homeMemberState`, `ae_lei_name`, `ae_lei`, `ae_commercial_name`,
`ac_authorisationNotificationDate`, `ac_authorisationEndDate`,
`ac_serviceCode` (letra + descripción, separador `|`),
`ac_serviceCode_cou` (países de servicio — dato de passport, G1-D).

## C2 — Matriz art. 60 (extraída del texto congelado)

| Entidad | Autorización previa | Servicios MiCA permitidos | Notificación | Competente |
|---|---|---|---|---|
| Entidad de crédito | Directiva propia | todos | 40 días hábiles antes | AC origen |
| Depositario central de valores | Regl. 909/2014 | **sólo custodia y administración** (equivalente a servicio de liquidación B.3) | 40 días | AC origen |
| Empresa de servicios de inversión | Dir. 2014/65/UE | **equivalentes** a sus servicios MiFID (tabla a–g del art. 60.3) | 40 días | AC origen |
| Entidad de dinero electrónico | Dir. 2009/110/CE | **sólo custodia/admin + transferencia sobre los EMT que emita** | 40 días | AC origen |
| Soc. gestora OICVM / gestor FIA | Dir. 2009/65/CE, 2011/61/UE | equivalentes a gestión de carteras + accesorios | 40 días | AC origen |
| Organismo rector del mercado | Dir. 2014/65/UE | **sólo gestión de plataforma de negociación** | 40 días | AC origen |

Consecuencia de diseño: prohibida la regla
`entity ∈ art.60 → todos los crypto services`. La regla es
`entity_class × crypto_service` con equivalencia explícita.

## C3 — Mapping registro → mecanismo

```text
PSC (ESPAÑA)                 → art. 63 / AUTHORISATION
entidad de crédito/ESI/… ES  → art. 60 / NOTIFICATION
PSC EN RÉGIMEN DE LP         → DEFER G1-D (territorialidad)
ESMA ac_serviceCode_cou≠ES   → DEFER G1-D
```

## C4 — Casos preregistrados (corpus real)

```text
C-01  PSC español art.63 — BIT2ME (Bitcoinforme S.L., ESMA CASP)
      → CONFIRMED_ENTITLED / AUTHORISATION, servicios a,c,d,e,f,g,j

C-02  entidad de crédito ES art.60 — BBVA (ESMA CASP, CNMV)
      → CONFIRMED_ENTITLED / NOTIFICATION, servicios a,e,j

C-03  art.60 con servicio dentro del perímetro — CAIXABANK
      (a,e,g,j — todos dentro de entidad de crédito)
      → CONFIRMED_ENTITLED / NOTIFICATION

C-04  art.60 + servicio fuera de equivalencia — hipotético guardado:
      EMI consultada por servicio distinto de custodia/transferencia
      sobre EMT propio → 0 entitlement positivo (NO_ENTITLEMENT_
      EVIDENCED o INDETERMINATE según haya o no otra evidencia)

C-05  presencia registral + identidad insuficiente
      → INDETERMINATE

C-06  PSC EN RÉGIMEN DE LP / ac_serviceCode_cou con ES siendo
      homeState extranjero → INDETERMINATE +
      TERRITORIAL_ENTITLEMENT_UNRESOLVED (remite a G1-D)

C-07  multi-role: PROSEGUR CUSTODIA DE ACTIVOS DIGITALES —
      PI bajo RDL 19/2018 (BdE 6950) Y CASP MiCA (ESMA) →
      dos EntitlementAssertions coexistiendo, entitlements
      independientes por régimen
```

## Fronteras

```text
G1-C  mecanismo jurídico × servicio (por qué vía y para qué)
G1-D  proyección territorial (passport PSD2 + MiCA, dos familias)
G1-E  negative/withdrawal/expiry semantics (incl. NCASP list)
```

## Estado

```text
C1  DONE — evidencia congelada (manifest-g1-c1.json)
C2  DONE — matriz art. 60 por entity_class × servicio
C3  DONE — mapping registro → mecanismo
C4  casos preregistrados; pendiente extracción CNMV PDF para
    cross-check de categoría declarada (PSC vs entidad financiera)
C5/C6 pendientes
```
