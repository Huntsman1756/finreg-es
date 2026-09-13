# Procedencia de los schemas vendorizados

| Fichero | URL upstream exacta | Versión | SHA-256 | Licencia |
|---------|--------------------|---------|---------|----------|
| `OpenLineage-2.0.2.schema.json` | `https://openlineage.io/spec/2-0-2/OpenLineage.json` | OpenLineage spec 2.0.2 | `69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2` | Apache-2.0 |
| `JobTypeJobFacet-2.0.2.schema.json` | `https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json` | OL facets 2.0.2 | `0716fc27d8f4ac450e64bfd25de002523f313d03e510bbc90d212d3af6259d1c` | Apache-2.0 |
| `LICENSE-OpenLineage-Apache-2.0.txt` | `https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/LICENSE` | upstream `main` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` | — |

Proyecto upstream: [OpenLineage](https://github.com/OpenLineage/OpenLineage)
(Linux Foundation / LF AI & Data), licencia Apache License 2.0.

El pin es **byte-exacto**: los tests fijan los SHA-256 anteriores y
fallan si el contenido vendored se sustituye. La validación es 100 %
offline — ningún test ni el exportador resuelven estas URLs en
ejecución.

Los schemas `facets/v1/finreg-*.schema.json` son **propios** (FinReg-ES),
no upstream.
