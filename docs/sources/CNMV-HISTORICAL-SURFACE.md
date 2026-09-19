# CNMV — superficie histórica `fs` (probe preliminar G4)

Fecha del probe: 2026-09-18. User-Agent estándar, GET directo, ~15 requests
totales (probe pequeño deliberado). Evidencia cruda en `/tmp/cnmv-probe`
(no congelada — el corpus congelado se produce en G0 con manifiesto+sha256).

## Pregunta

¿`fs` (fecha de situación) de cnmv.es reconstruye estado histórico real,
y en qué superficies?

## Resultados por superficie

| URL | `fs` aceptado | `fs` cambia contenido | Fecha servida declarada | Veredicto |
|---|---|---|---|---|
| `ESI/esis.aspx?nif=…` (ESI nacional) | **no — HTTP 400** | — | — | rechazado |
| `ESI/esisextranjeraslp.aspx?tipo=CLP&numero=…` | sí (200) | **no** — sólo se ecoa en `canonical`/`hreflang`/`form action` | no | ignorado |
| `iic/sociedadiic.aspx?nif=…&vista=1` | sí | **sí** — dirección e información pública periódica cambian | **sí**: input `ctl00$ContentPrincipal$wFecha$txtFecha` muestra `value="YYYY-MM-DD"` | **honrado + declarado** |
| `iic/sgiic.aspx?nif=…` | sí | **sí** — dirección y capital social difieren vs current | no hay input de fecha en esta ficha | honrado, sin eco visible de fecha |

## Observaciones

1. **Cambio de contenido real** (`sociedadiic`, nif `A61742771`):
   - `fs=09/06/2020` → info. periódica muestra 2020-T1/2019-S2/2019-T3
     (vs 2026/2025 en current).
   - `fs=01/01/2015` → domicilio `PEDRO I PONS 9-11` (vs `Avenida Diagonal
     682` current).
2. **Nearest-before**: `fs=08/06/2020` produce texto visible idéntico a
   `fs=09/06/2020` → la fuente sirve estado a fecha o el snapshot
   inmediatamente anterior disponible.
3. **Sin clamp inferior**: `fs=01/01/1990` (anterior a la inscripción
   30/11/2001) devuelve 200 con *otro* domicilio (`AVENIDA DIAGONAL 618`)
   y "No se han encontrado datos disponibles" en info. periódica → la
   superficie sirve el estado más antiguo disponible sin error ni aviso.
   **Riesgo**: fechas pre-inscripción devuelven contenido que podría
   malinterpretarse como estado válido en 1990. Mitigación: contrastar
   siempre contra `Fecha registro oficial`.
4. **SGIIC** (`nif=A83133421`): `fs=01/01/2015` → `BALBINA VALVERDE, 15`
   y capital `1.640.000,00` vs current `CASTELLANA 92` y `1.140.000,00`.
   La ficha no muestra la fecha servida → la declaración temporal viene
   sólo de la URL pedida (trazabilidad nuestra, no de la fuente).
5. **No es API**: HTML de aplicación ASP.NET; parsear es frágil y cada
   familia tiene plantilla distinta. `vista=N` parametriza pestañas en
   `esis.aspx` (0=general, 4=admins, 7=socios, 8=agentes, 9=sucursales ES,
   17=programa).
6. **Rate limiting observado**: dos 403 en `IIC/IndiceIIC.aspx` y un 404 en
   `listadoentidad.aspx?id=3` tras ~10 requests rápidos; espaciar probes.

## Preguntas abiertas para G0

- [ ] ¿`vista=N` honra `fs` en IIC (p. ej. administradores a fecha)?
- [ ] ¿`ecr/gestora.aspx` y depositarios honran `fs`?
- [ ] ¿Existe fecha mínima o lista de snapshots por entidad?
- [ ] ¿Qué hace `fs` con fechas entre snapshots (consistencia
      nearest-before en más casos)?
- [ ] ¿Hay forma canónica de saber qué fecha exacta se sirvió cuando la
      página no ecoa el input (`sgiic.aspx`)?
- [ ] ¿Las altas/bajas de registro tienen superficie histórica propia
      (distinta de `fs`)?

## Implicación para el producto

`fs` permite ofrecer "ficha a fecha" en el vertical IIC/SGIIC con
`OFFICIAL_AS_OF_STATE` real. En ESI/EAF no existe esa vía: el histórico
será `OBSERVED_CHANGE` entre snapshots propios + eventos oficiales
documentales (BOE). El contrato de producto debe reflejar esta
asimetría — no prometer "histórico CNMV" uniforme.
