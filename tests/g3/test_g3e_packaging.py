"""G3-E1 — build + install smoke del runtime evidence bundle.

Contrato congelado: ``docs/g3-e0-packaging-contract.md`` S8.

Construye sdist+wheel x2 con ``python -m build --no-isolation``
(el backend hatchling y el frontend build son tooling del entorno
de test, instalado por CI — no runtime deps), crea venvs NUEVOS
fuera del repo e instala el WHEEL (nunca ``pip install -e``).

Propiedad offline de la suite: el wheel se instala con
``--no-deps`` (cero acceso a red). El venv ``base`` no ve site-
packages del exterior — asi se prueba el fallo limpio
``missing_extra``; el venv ``extras`` recibe un ``.pth`` al
site-packages del entorno de test, donde typer/mcp ya estan
instalados como tooling — equivalente declarado y offline de
``pip install "finreg-es[cli]"`` (los paquetes del wheel siguen
resolviendo desde el venv propio).

Todo subproceso corre con cwd=tmp_path (fuera del repo) y entorno
sin PYTHONPATH: ningun path de salida puede resolver contra el
checkout por accidente.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_EVIDENCE_SET_ID = (
    "derived-assertions-g1-e-002"
    "@sha256:2fb08d678a5ee11a398af7a4a990521d1ca5fde20012ffd8e8af63f058bfc1e7"
)
EXPECTED_TOOLS = {
    "assess",
    "assess_bitemporal",
    "evidence",
    "explain",
    "changes",
}
# E0-01 = fixtures/g2/e0/bitemporal-cases.json cases[0].probes[0]
E0_QUERY = {
    "entity_id": "E3-001",
    "activity": "MONEY_REMITTANCE",
    "jurisdiction": "ES",
    "valid_at": "2020-07-22",
    "known_at": "2026-09-13",
}

REPORT: dict = {"checks": {}}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean_env() -> dict:
    env = dict(os.environ)
    for var in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(var, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run(cmd, cwd, timeout=300) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _venv_python(vdir: Path) -> Path:
    return vdir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _venv_script(vdir: Path, name: str) -> Path:
    return vdir / (
        f"Scripts/{name}.exe" if os.name == "nt" else f"bin/{name}"
    )


def _venv_site_packages(vdir: Path) -> Path:
    if os.name == "nt":
        return vdir / "Lib" / "site-packages"
    return next((vdir / "lib").glob("python*/site-packages"))


def _bundle_files() -> list[Path]:
    """Los originales del repo que S4 congela como bundle minimo."""
    files = []
    for d in ("fixtures/contracts", "fixtures/g2/events", "fixtures/g3/projection"):
        files += sorted((ROOT / d).rglob("*"))
    files.append(ROOT / "fixtures/g1/derived-assertions-g1-e-002.json")
    return [p for p in files if p.is_file()]


def _wheel_manifest(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as z:
        return {
            n: _sha256(z.read(n))
            for n in z.namelist()
            if not n.endswith("/")
        }


def _sdist_manifest(path: Path) -> dict[str, str]:
    with tarfile.open(path) as t:
        return {
            m.name: _sha256(t.extractfile(m).read())
            for m in t.getmembers()
            if m.isreg()
        }


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build x2 desde el mismo checkout: sdist + wheel-from-sdist."""
    outs = []
    for i in (1, 2):
        out = tmp_path_factory.mktemp(f"dist{i}")
        r = _run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(out),
                str(ROOT),
            ],
            cwd=out,
            timeout=600,
        )
        assert r.returncode == 0, r.stderr
        outs.append(out)
    return {
        "wheels": sorted(p for o in outs for p in o.glob("*.whl")),
        "sdists": sorted(p for o in outs for p in o.glob("*.tar.gz")),
    }


@pytest.fixture(scope="module")
def venvs(tmp_path_factory, built):
    """Dos venvs nuevos fuera del repo con el wheel instalado."""
    wheel = built["wheels"][0]
    base = tmp_path_factory.mktemp("venvs")
    envs = {}
    for name in ("base", "extras"):
        vdir = base / name
        subprocess.run(
            [sys.executable, "-m", "venv", str(vdir)],
            check=True,
            timeout=600,
            capture_output=True,
        )
        py = _venv_python(vdir)
        r = _run(
            [py, "-m", "pip", "install", "--no-deps", str(wheel)],
            cwd=vdir,
        )
        assert r.returncode == 0, r.stderr
        if name == "extras":
            # Extra declarado sin red: addsitedir hace visible el
            # site-packages del entorno de test (donde typer/mcp ya
            # son tooling) procesando sus .pth internos — p.ej.
            # pywin32.pth, necesario para pywintypes en Windows. El
            # wheel sigue resolviendo primero desde el venv propio.
            pth = _venv_site_packages(vdir) / "zz_e1_tooling.pth"
            pth.write_text(
                "import site; site.addsitedir("
                + repr(sysconfig.get_path("purelib"))
                + ")\n",
                encoding="utf-8",
            )
        envs[name] = {
            "dir": vdir,
            "python": py,
            "finreg": _venv_script(vdir, "finreg"),
        }
    return envs


def test_build_x2_same_content(built):
    assert len(built["wheels"]) == 2 and len(built["sdists"]) == 2
    assert _wheel_manifest(built["wheels"][0]) == _wheel_manifest(
        built["wheels"][1]
    )
    assert _sdist_manifest(built["sdists"][0]) == _sdist_manifest(
        built["sdists"][1]
    )
    # Evidencia adicional (no contractual): mismo SHA del wheel.
    REPORT["wheel_sha256_equal_builds"] = _sha256(
        built["wheels"][0].read_bytes()
    ) == _sha256(built["wheels"][1].read_bytes())


def test_base_import_zero_deps(venvs, tmp_path):
    py = venvs["base"]["python"]
    r = _run(
        [py, "-c", "import finreg_es; print(finreg_es.__file__)"],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert str(venvs["base"]["dir"]) in r.stdout
    assert str(ROOT) not in r.stdout
    r = _run(
        [
            py,
            "-c",
            "import importlib.metadata as m; "
            "assert not [r for r in (m.requires('finreg-es') or []) "
            "if 'extra ==' not in r]",
        ],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr


def test_finreg_base_missing_extra(venvs, tmp_path):
    """Console script del wheel sin [cli]: error estructurado,
    nunca traceback."""
    r = _run([venvs["base"]["finreg"], "--help"], cwd=tmp_path)
    assert r.returncode != 0
    err = json.loads(r.stderr)
    assert err["error"]["code"] == "missing_extra"
    assert "finreg-es[cli]" in err["error"]["message"]
    assert "Traceback" not in r.stderr


def test_bundle_byte_equality(built, venvs, tmp_path):
    """S6: sha256(repo) == sha256(wheel) == sha256(installed), por
    cada fichero del bundle."""
    wheel = built["wheels"][0]
    py = venvs["base"]["python"]
    r = _run(
        [
            py,
            "-c",
            "import adapters; "
            "from pathlib import Path; "
            "print(Path(adapters.__file__).resolve().parent / '_data')",
        ],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    data_dir = Path(r.stdout.strip())
    assert data_dir.is_dir()
    assert str(ROOT) not in str(data_dir)
    with zipfile.ZipFile(wheel) as z:
        for src in _bundle_files():
            rel = src.relative_to(ROOT).as_posix()
            member = f"adapters/_data/{rel}"
            installed = data_dir / "fixtures" / src.relative_to(
                ROOT / "fixtures"
            )
            assert installed.is_file(), member
            repo_sha = _sha256(src.read_bytes())
            assert _sha256(z.read(member)) == repo_sha, member
            assert _sha256(installed.read_bytes()) == repo_sha, member
    REPORT["bundle_files_verified"] = len(_bundle_files())


def test_no_checkout_dependence(venvs, tmp_path):
    """Los defaults resuelven al bundle del venv, no al repo."""
    py = venvs["extras"]["python"]
    r = _run(
        [py, "-c", "import adapters.common as c; print(c.ROOT)"],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    root = Path(r.stdout.strip())
    assert venvs["extras"]["dir"] in root.parents
    assert str(ROOT) not in str(root)
    assert (
        root / "fixtures/g1/derived-assertions-g1-e-002.json"
    ).is_file()


def _cli_bitemporal(finreg: Path, cwd: Path) -> dict:
    args = [finreg, "assess-bitemporal"]
    for k, v in E0_QUERY.items():
        args += ["--" + k.replace("_", "-"), v]
    r = _run(args, cwd=cwd)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_finreg_cli_query_real(venvs, tmp_path):
    """Console script del wheel + [cli]: help y query E0 real."""
    finreg = venvs["extras"]["finreg"]
    r = _run([finreg, "--help"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    payload = _cli_bitemporal(finreg, tmp_path)
    assert payload["assessment"] == "CONFIRMED_ENTITLED"
    assert payload["reason"] == "ACTIVE_ENTITLEMENT_EVIDENCED"
    assert payload["used_assertion_ids"] == ["g1e-asm-006"]
    assert payload["evidence_set_id"] == EXPECTED_EVIDENCE_SET_ID


def test_mcp_discovery_and_parity(venvs, tmp_path):
    """[mcp]: discovery real por stdio + misma query, payload
    canonico identico al del console script."""
    cli_payload = _cli_bitemporal(venvs["extras"]["finreg"], tmp_path)
    payload = asyncio.run(
        _mcp_query(venvs["extras"]["python"], tmp_path)
    )
    assert payload["evidence_set_id"] == EXPECTED_EVIDENCE_SET_ID
    assert payload == cli_payload


async def _mcp_query(python: Path, cwd: Path) -> dict:
    params = StdioServerParameters(
        command=str(python),
        args=["-m", "adapters.mcp_server"],
        env=_clean_env(),
        cwd=str(cwd),
    )
    async with Client(params) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
        assert tools == EXPECTED_TOOLS
        result = await client.call_tool("assess_bitemporal", E0_QUERY)
        assert not result.is_error
        return json.loads(result.content[0].text)


def test_changes_over_bundled_events(venvs, tmp_path):
    finreg = venvs["extras"]["finreg"]
    r = _run(
        [
            finreg,
            "changes",
            "--pair",
            "eba-psd2-20260914-vs-20260915",
        ],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    candidates = payload["results"][0]["candidates"]
    blocked = [
        c
        for c in candidates
        if c.get("admissibility") == "BLOCKED"
        and c.get("blocker") == "NO_PREREGISTERED_RULE"
    ]
    assert len(blocked) == 312


def test_projection_digest_preserved(venvs, tmp_path):
    """El .sqlite instalado reproduce el logical_projection_sha256
    declarado por su manifest — recomputado con el codigo y los
    datos del propio wheel (stdlib only)."""
    code = (
        "import json, sqlite3\n"
        "from pathlib import Path\n"
        "from adapters import sqlite_projection as sp\n"
        "from finreg_es.canonical import sha256_hex\n"
        "data = Path(sp.__file__).resolve().parent / '_data'\n"
        "db = data / 'fixtures/g3/projection/finreg-g3.sqlite'\n"
        "man = json.loads(\n"
        "    db.with_name('manifest.json').read_text(encoding='utf-8'))\n"
        "conn = sqlite3.connect(\n"
        "    'file:' + str(db).replace('\\\\', '/') + '?mode=ro', uri=True)\n"
        "tables = []\n"
        "for t in sp.TABLE_ORDER:\n"
        "    rows, digest = sp._table_digest(conn, t)\n"
        "    tables.append(\n"
        "        {'name': t, 'rows': rows, 'logical_sha256': digest})\n"
        "conn.close()\n"
        "digest = sha256_hex({\n"
        "    'projection_version': man['projection_version'],\n"
        "    'inputs': man['inputs'],\n"
        "    'tables': tables,\n"
        "})\n"
        "print(json.dumps({'digest': digest, 'expected': man['logical_projection_sha256']}))\n"
    )
    r = _run([venvs["base"]["python"], "-c", code], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["digest"] == out["expected"]


def test_report():
    print(json.dumps(REPORT, sort_keys=True, ensure_ascii=False))
