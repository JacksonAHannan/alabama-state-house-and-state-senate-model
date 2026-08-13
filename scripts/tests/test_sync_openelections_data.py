from pathlib import Path

import pytest

from sync_openelections_data import CYCLES, sync


def _make_fake_source_repo(root: Path) -> Path:
    source_repo = root / "openelections-data-al"
    for _cycle, relpath in CYCLES:
        path = source_repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"county,precinct,office,district,party,candidate,votes\nFake,P1,President,,DEM,X,{relpath}\n")
    return source_repo


def test_sync_copies_every_cycle_file(tmp_path):
    source_repo = _make_fake_source_repo(tmp_path)
    dest_dir = tmp_path / "data" / "raw" / "openelections"

    report = sync(source_repo, dest_dir)

    assert len(report) == len(CYCLES)
    for cycle, relpath in CYCLES:
        dest_path = dest_dir / Path(relpath).name
        assert dest_path.exists()
        assert dest_path.read_text() == (source_repo / relpath).read_text()


def test_sync_raises_when_source_file_missing(tmp_path):
    source_repo = _make_fake_source_repo(tmp_path)
    (source_repo / CYCLES[0][1]).unlink()
    dest_dir = tmp_path / "dest"

    with pytest.raises(FileNotFoundError):
        sync(source_repo, dest_dir)
