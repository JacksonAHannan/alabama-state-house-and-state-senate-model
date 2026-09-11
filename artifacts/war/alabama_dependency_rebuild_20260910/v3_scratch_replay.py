"""Scratch replay of the approved Southern v3 fit against the current warehouse.

Writes only under artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch/.
Compares every CSV output (minus the model_run_id column) with the approved bundle.
Investigation only: nothing under data/processed or project_docs is written.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import retrain_post2016_southern_war_v3 as v3  # noqa: E402

SCRATCH = Path(__file__).resolve().parent / "v3_scratch"
APPROVED = ROOT / "data/processed/war/post2016_southern_war_v3"


def streaming_sha256(path: Path) -> str:
    """Same digest as v3.sha256 without reading the 5.8 GB warehouse into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


v3.sha256 = streaming_sha256
v3.OUT = SCRATCH / "post2016_southern_war_v3"
v3.METHOD_REPORT = SCRATCH / "POST2016_SOUTHERN_WAR_V3.md"
v3.AUDIT_REPORT = SCRATCH / "POST2016_SOUTHERN_WAR_V3_VALIDATION.md"
SCRATCH.mkdir(parents=True, exist_ok=True)
for path in (v3.OUT, v3.METHOD_REPORT, v3.AUDIT_REPORT):
    assert not path.exists() or path.is_relative_to(SCRATCH)

started = time.time()
v3.main()
elapsed = time.time() - started


def digest_without_run_id(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    rows = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        header = handle.readline()
        columns = header.rstrip("\r\n").split(",")
        drop = columns.index("model_run_id") if "model_run_id" in columns else None
        digest.update(",".join(c for i, c in enumerate(columns) if i != drop).encode())
        for line in handle:
            rows += 1
            if drop is None:
                digest.update(line.encode())
            else:
                parts = line.rstrip("\r\n").split(",")
                # model_run_id is the first column and never contains commas
                digest.update(",".join(parts[:drop] + parts[drop + 1:]).encode())
    return digest.hexdigest(), rows


scratch_manifest = json.loads((v3.OUT / "manifest.json").read_text(encoding="utf-8"))
approved_manifest = json.loads((APPROVED / "manifest.json").read_text(encoding="utf-8"))
comparison = []
for entry in approved_manifest["outputs"]:
    name = Path(entry["path"]).name
    approved_digest, approved_rows = digest_without_run_id(APPROVED / name)
    scratch_digest, scratch_rows = digest_without_run_id(v3.OUT / name)
    comparison.append({
        "output": name,
        "approved_rows": approved_rows,
        "scratch_rows": scratch_rows,
        "identical_without_run_id": approved_digest == scratch_digest,
        "approved_digest": approved_digest,
        "scratch_digest": scratch_digest,
    })
result = {
    "approved_run_id": approved_manifest["model_run_id"],
    "scratch_run_id": scratch_manifest["model_run_id"],
    "approved_warehouse_run": approved_manifest["warehouse_build_run_id"],
    "scratch_warehouse_run": scratch_manifest["warehouse_build_run_id"],
    "approved_input_hashes": approved_manifest["input_hashes"],
    "scratch_input_hashes": scratch_manifest["input_hashes"],
    "input_hash_differences": sorted(
        k for k in approved_manifest["input_hashes"]
        if approved_manifest["input_hashes"][k] != scratch_manifest["input_hashes"].get(k)
    ),
    "code_hash_differences": sorted(
        k for k in approved_manifest["code_hashes"]
        if approved_manifest["code_hashes"][k] != scratch_manifest["code_hashes"].get(k)
    ),
    "diagnostics_equal": approved_manifest["diagnostics"] == scratch_manifest["diagnostics"],
    "configuration_equal": approved_manifest["configuration"] == scratch_manifest["configuration"],
    "outputs": comparison,
    "all_outputs_identical_without_run_id": all(c["identical_without_run_id"] for c in comparison),
    "elapsed_seconds": round(elapsed, 1),
}
(SCRATCH / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k not in ("approved_input_hashes", "scratch_input_hashes", "outputs")}, indent=1))
for c in comparison:
    print(f"{c['output']:45s} rows {c['approved_rows']:>6}/{c['scratch_rows']:<6} identical={c['identical_without_run_id']}")
