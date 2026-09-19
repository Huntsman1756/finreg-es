# G4-G2 — Preregistro: aplicación web estática (apps/web) + primera ficha E2E

Preregistrado tras G4-G1 CONDITIONAL/GO (`35366e8`), antes de
scaffoldear `apps/web`. Contrato de stack: ADR-007 + WEB-ARCHITECTURE.
Documento congelado.

## Afirmación falsable

> Con `projections/public/` como única fuente de datos, un sitio Astro
> estático renderiza el corpus completo (20 fichas + índices) en HTML
> sin hidratación obligatoria, con búsqueda Pagefind funcional, y la
> ficha expone la jerarquía del contrato (identidad → autorizaciones →
> presencia → regulatory record → timeline → fuentes) con los enums y
> `UNKNOWN`/`NO HISTORICAL EVIDENCE` explícitos.

## Casos preregistrados

| Caso | Esperado |
|---|---|
| W01 | Build estático: `out/` contiene HTML para `/`, `/buscar/`, `/cambios/`, `/metodologia/`, `/fuentes/`, `/datos/`, `/aviso-legal/`, `/privacidad/`, `/reguladores/` + una página por entidad en `/entidad/<id>/` (20) |
| W02 | Ficha ESI-4 (`/entidad/esi-a83217281/`): muestra impersonations con la redacción "no guarda relación con…" — el clon figura como suplantación **de** la entidad, nunca como advertencia **contra** ella |
| W03 | Ficha ESI-1: `NO HISTORICAL EVIDENCE` visible en la sección historia; servicios con instrumentos/clientes visibles |
| W04 | Ficha SAN-1: sanción visible con fecha de registro + referencia BOE; estados `fs` en timeline etiquetados `OFFICIAL_AS_OF_STATE` con `requested_fs` |
| W05 | Ficha INS-5: `DEREGISTERED`/Cancelada con fecha de baja mostrada como acotada `[desconocida, 2026-09-13]` — ninguna fecha exacta inventada |
| W06 | Búsqueda: Pagefind indexa el sitio; `/buscar/?q=abante` resuelve a la ficha ESI-4 (verificable con Pagefind UI o API estática) |
| W07 | `entities.json`/`manifest.json` servidos como estáticos descargables desde `/datos/` |
| W08 | 0 `<script>` requerido para contenido: fichas legibles con JS deshabilitado |
| W09 | Cero texto de rating/score/recomendación en el HTML generado (grep sobre `out/`) |
| W10 | Breadcrumbs + `noindex` sólo donde aplique; sitemap generado |
| W11 | axe/WCAG 2.2 AA: 0 violaciones críticas en ficha + home (vía test automatizado si la toolchain lo permite, si no → chequeo manual documentado) |

## Gates

```text
PASS ⇔  W01–W10 automatizables verificados ∧ W11 documentado
CONDITIONAL ⇔  sitio funcional con un gap declarado (p.ej. Pagefind
     diferido o W11 parcial)
FAIL ⇔  necesidad de backend/server-side ∨ datos fuera de
     projections/public ∨ contenido que sobreinterprete evidencia
```

## Resultados válidos

- Fichas con secciones vacías por `NO_EVIDENCE` → válido: se muestran
  como ausencia declarada, no se ocultan los denominadores.
- Búsqueda que devuelve 0 resultados para término ausente → válido.
- Visual sobrio "registro público" — sin valoración estética en el
  gate; el gate mide completitud/veracidad/accesibilidad, no estilo.

## Artefactos comprometidos

```text
apps/web/                    Astro SSG (verificación: npm run build)
apps/web/src/pages/          rutas del contrato
apps/web/src/components/     ficha, timeline, warning panel, coverage
apps/web/public/data/        copia de projections/public/ en build
tests/e2e/                   smoke tests del HTML generado
```

## Kill criteria

- El sitio requiere fetch runtime a APIs o DB → STOP: viola el
  contrato estático; se revisa la proyección.
- Pagefind no satisface la búsqueda → declarar CONDITIONAL y evaluar
  alternativa estática en gate sucesor (no cambiar de stack a ciegas).
