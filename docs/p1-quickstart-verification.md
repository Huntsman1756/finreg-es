# P1 — verificación del quickstart (evidencia de ejecución real)

Fecha: 2026-09-16. Ejecutado sobre `git worktree` limpio del tag
`g3-consumability-closed` (`fda00ad`), venv nuevo fuera del repo,
cwd ajeno al checkout. Sistema operativo: Windows 11, Python 3.11.

## Secuencia ejecutada (literal)

```text
git worktree add <tmp>/repo g3-consumability-closed
cd <tmp>/repo
python -m build --no-isolation --outdir dist .
    → finreg_es-0.0.1.tar.gz + finreg_es-0.0.1-py3-none-any.whl
python -m venv <tmp>/venv
<tmp>/venv/Scripts/python -m pip install
    "<tmp>/repo/dist/finreg_es-0.0.1-py3-none-any.whl[cli]"
    → finreg-es 0.0.1 + typer 0.27.2 (+deps) desde el índice
cd <tmp>   (cwd ajeno al checkout y al repo)
./venv/Scripts/finreg.exe --help
    → 5 comandos: assess, assess-bitemporal, evidence, explain,
      changes — exit 0
./venv/Scripts/finreg.exe assess-bitemporal --entity-id E3-001
    --activity MONEY_REMITTANCE --jurisdiction ES
    --valid-at 2020-07-22 --known-at 2026-09-13
    → CONFIRMED_ENTITLED / ACTIVE_ENTITLEMENT_EVIDENCED
      evidence_set_id = derived-assertions-g1-e-002@sha256:2fb08d67…
```

## Resultado

```text
quickstart  PASS — el flujo documentado funciona tal cual sobre el
            tag congelado; ninguna fricción de producto encontrada.
ejemplos    docs/examples/{assess-bitemporal,evidence-assertion,
            changes-blocked}.json = stdout verbatim; regeneración
            posterior byte-idéntica (sha256 en manifest.json).
```

## Notas / findings

- **Fricción de producto: ninguna.** El console script, el bundle
  `_data` y la resolución de defaults funcionaron desde un cwd y
  venv totalmente ajenos al repo.
- Instalar el extra `[cli]` descarga typer del índice — es el
  flujo real de usuario; la suite offline no lo ejerce (el test E1
  lo cubre con `.pth` declarado).
- Nota de entorno (no de producto): en shells POSIX-emulados sobre
  Windows (Git Bash/MSYS), pip no resuelve paths `/tmp/...` — el
  quickstart documentado usa paths nativos del shell (`dist\…` /
  `dist/…`) que funcionan en cmd/PowerShell/bash-POSIX reales.

## Veredicto P1

```text
PASS — P1-A..D ejecutados; P1-E queda blocked/opcional.
```
