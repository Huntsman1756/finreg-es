# G3-D — Contrato del smoke externo black-box (preregistro)

**Estado:** FROZEN antes de producción (task `g3-d-preregister`;
la ejecución es `g3-d-external-smoke`). Deriva de
`docs/g3-scope.md` (G3-D: "un cliente consulta FinReg sin conocer
internals") y de los contratos de superficie ya congelados:
`docs/g3-b-adapter-contract.md` (CLI/MCP) y
`docs/g3-c-projection-contract.md` (proyección + Datasette).

## 1. Tesis (falsable)

```text
Un consumidor black-box puede utilizar las superficies públicas de
FinReg —CLI, MCP y Datasette— y recorrer de una respuesta hasta su
evidencia oficial sin importar ni conocer módulos internos del
motor.
```

## 2. Frontera de fase

G3-D **no** es G3-E: el smoke prueba el checkout actual. No se
instala wheel, no se crean console scripts ni ejecutable `finreg`;
eso es packaging de G3-E. El harness lanza los comandos públicos
documentados desde el checkout:

```text
CLI       python -m adapters.cli <comando> --opts   (canonical JSON en stdout)
MCP       python -m adapters.mcp_server             (server stdio, SDK v2)
Datasette datasette serve -i <proyeccion>           (HTTP/JSON, immutable)
```

## 3. Reglas binding (D1–D4)

```text
D1  cliente black-box
    cero imports de finreg_es.*
    cero imports de adapters.*
    cero sqlite3 directo

D2  interacción sólo mediante:
    CLI subprocess        (stdout = canonical JSON)
    MCP client estándar   (SDK oficial, transporte stdio)
    HTTP/JSON Datasette   (proceso servido con -i)

D3  el cliente puede conocer:
      nombres de operaciones públicas
      parámetros documentados
      ids devueltos por una superficie
    el cliente NO puede conocer:
      paths internos de fixtures para reconstruir respuestas
      schema Python del core
      funciones internas
    (arrancar los procesos con sus paths publicados es operación,
    no conocimiento interno: el cliente no usa esos paths para
    componer respuestas)

D4  no se modifica ninguna superficie (cli/mcp/datasette/
    proyeccion) para conseguir que el smoke pase
```

## 4. Escenarios — una cadena, no tres demos

```text
S1 CLI
   assessment bitemporal real (mismo caso E0-01 que G3-B)
   → assessment + reason + used_assertion_ids + evidence_set_id

S2 MCP
   misma query por protocolo (discover tools → call assess*)
   → mismo business payload canónico que CLI

S3 Datasette
   used_assertion_id obtenido en S1/S2
   → fila en assertions → source_assertions
   → raw_snapshot_sha256 / source_url / retrieved_at
   (provenance E2E: respuesta → evidencia oficial)

S4 longitudinal
   changes por CLI/MCP → record_key de un candidato BLOCKED
   → seguirlo en Datasette → NO_PREREGISTERED_RULE visible
   con su structural_change ligado

S5 fail-closed
   input/id inválido en cada superficie
   → error público estructurado (cero fallback, cero traceback
   interno presentado como resultado de negocio)
```

S3 y S4 demuestran continuidad: los ids emitidos por una superficie
son resolubles en otra — una única superficie coherente, no tres
productos paralelos.

## 5. Harness

```text
tools/smoke_g3d_external.py    el cliente black-box
tests/g3/test_g3d_external_smoke.py
    - lanza el harness como subprocess y verifica su veredicto
    - enforcement estructural de D1: AST scan del harness —
      falla si importa finreg_es/adapters o usa sqlite3
```

El harness se comporta como otro programa: subprocess para CLI,
cliente MCP estándar por stdio (discovery real por protocolo, no
llamada al handler), HTTP para Datasette. Emite un informe
canonical JSON por stdout `{verdict, checks}` y exit 0/1.

## 6. Acceptance criteria (binding)

```text
✓ harness sin imports de código FinReg (D1, enforcement AST)
✓ CLI y MCP: mismo business payload canónico para la misma query
✓ discovery MCP real por protocolo stdio
✓ Datasette consumido por HTTP/JSON, nunca sqlite3
✓ provenance E2E: used_assertion_id → assertion →
  source_assertions → snapshot sha/url/retrieved_at
✓ cambio BLOCKED navegable CLI/MCP → Datasette
✓ error fail-closed observable desde fuera en cada superficie
✓ cero writes durante el smoke (fingerprint antes/después)
✓ full suite verde · tools/audit_g2f_replay.py PASS
✓ G3-B/G3-C no modificados para satisfacer el smoke
```

## 7. Resultados válidos (declarados antes de observar)

```text
PASS       todos los escenarios black-box funcionan
QUALIFIED  funcionan pero existe una limitación pública concreta
           (declarada, no parcheada)
FAIL       hace falta conocer/importar internals para completar
           el recorrido
```

Los tres son resultados registrables. Prohibido mover criterios
tras observar: contrato incorrecto → finding + sucesor documental.

## 8. Artefactos objetivo

```text
tools/smoke_g3d_external.py            harness black-box
tests/g3/test_g3d_external_smoke.py    wrapper pytest + AST D1
```

Nada más: ni cambios en adapters/, ni en fixtures/, ni en
pyproject/CI (las deps de superficie ya están en extras).
