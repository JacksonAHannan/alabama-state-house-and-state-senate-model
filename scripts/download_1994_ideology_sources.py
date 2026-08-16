"""Download public 1994 ideology-source documentation and build a source registry.

Most archival links are finding aids rather than digitized candidate records.
The registry records that distinction explicitly: only candidate-level source
documents may feed the observation table.
"""

from __future__ import annotations

import hashlib
import mimetypes
import urllib.request
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ideology" / "alabama_1994_archival_sources"
REGISTRY = ROOT / "data" / "processed" / "ideology" / "alabama_1994_source_registry.csv"
OBSERVATIONS = ROOT / "data" / "manual" / "ideology" / "alabama_1994_candidate_observations.csv"

SOURCES = (
    {
        "source_id": "AL1994-TRENHOLM-GWEN-PATTON",
        "organization": "Alabama New South Coalition",
        "url": "https://library.trenholmstate.edu/gwen-patton-collection",
        "filename": "trenholm_gwen_patton_collection.html",
        "resource_type": "finding_aid",
        "candidate_level_data_available_online": False,
        "target_material": "ComStoBox 11 #403003 candidate surveys, screenings, endorsements, PAC material; ComStoBox 13 #403006 1994 convention booklet",
        "acquisition_status": "archive_request_required",
    },
    {
        "source_id": "AL1994-ADC-KELLEY-BENNETT",
        "organization": "Alabama Democratic Conference",
        "url": "https://law.justia.com/cases/federal/district-courts/FSupp2/96/1301/2420973/",
        "filename": "kelley_v_bennett_2000.html",
        "resource_type": "legal_corroboration",
        "candidate_level_data_available_online": False,
        "target_material": "1994 Democratic legislative-primary ADC endorsed sample ballots and screening records",
        "acquisition_status": "underlying_ballots_not_digitized",
    },
    {
        "source_id": "AL1994-AUBURN-LWV",
        "organization": "League of Women Voters of Alabama",
        "url": "https://archivesspace.lib.auburn.edu/repositories/2/archival_objects/37754",
        "filename": "auburn_lwv_finding_aid.html",
        "resource_type": "finding_aid",
        "candidate_level_data_available_online": False,
        "target_material": "The Alabama Voter 1994 issues, Capitol Newsletter 1994-1995, voter-service and candidate-comparison material",
        "acquisition_status": "archive_request_required",
    },
    {
        "source_id": "AL1994-AUBURN-BCA",
        "organization": "Business Council of Alabama / ProgressPAC",
        "url": "https://archivesspace.lib.auburn.edu/repositories/2/archival_objects/18941",
        "filename": "auburn_bca_box6_folder22.html",
        "resource_type": "finding_aid",
        "candidate_level_data_available_online": False,
        "target_material": "Box 6 Folder 22, especially 1993-1994 ProgressPAC endorsements, evaluations, questionnaires, and correspondence",
        "acquisition_status": "archive_request_required",
    },
    {
        "source_id": "AL1994-ADAH-SUBJECT-FILES",
        "organization": "Alabama Department of Archives and History",
        "url": "https://archives.alabama.gov/research/finding-aids/v5935f.htm",
        "filename": "adah_public_information_subject_files.html",
        "resource_type": "finding_aid",
        "candidate_level_data_available_online": False,
        "target_material": "SG006938 folders 007 ADC, 032 Alabama Medical PAC, and 039 ANSC; inspect January-November 1994",
        "acquisition_status": "archive_request_required",
    },
    {
        "source_id": "AL1994-JCLC-NEWSLIBRARY",
        "organization": "Jefferson County Library Cooperative",
        "url": "https://www.jclc.org/resources/databases/help/NewsLibrary.pdf",
        "filename": "jclc_newslibrary_help.pdf",
        "resource_type": "database_access_guide",
        "candidate_level_data_available_online": False,
        "target_material": "Birmingham News searches for ADC, ANSC, A-VOTE, FarmPAC, ProgressPAC and legislative endorsement slates in 1994",
        "acquisition_status": "licensed_database_search_required",
    },
    {
        "source_id": "AL1994-ADAH-NEWSPAPERS",
        "organization": "Alabama Department of Archives and History",
        "url": "https://archives.alabama.gov/research/Newspapers.aspx",
        "filename": "adah_newspapers_database.html",
        "resource_type": "database_access_guide",
        "candidate_level_data_available_online": False,
        "target_material": "Statewide and local newspaper endorsement, questionnaire, sample-ballot, and candidate-screening coverage",
        "acquisition_status": "research_room_or_database_access_required",
    },
)

OBSERVATION_COLUMNS = [
    "observation_id", "source_id", "source_document", "source_page", "publication_date",
    "election_year", "election_stage", "chamber", "district", "candidate_name_source",
    "canonical_candidate_id", "organization", "evidence_type", "issue", "position",
    "endorsement_status", "verbatim_excerpt", "coder", "review_status", "notes",
]


def download(url: str, destination: Path) -> tuple[str, int, str]:
    if destination.exists() and destination.stat().st_size:
        content = destination.read_bytes()
        return (hashlib.sha256(content).hexdigest(), len(content),
                mimetypes.guess_type(destination.name)[0] or "application/octet-stream")
    request = urllib.request.Request(url, headers={"User-Agent": "Alabama-CMO-academic-research/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        content = response.read()
        content_type = response.headers.get("Content-Type", "").split(";")[0]
    destination.write_bytes(content)
    return hashlib.sha256(content).hexdigest(), len(content), content_type


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    OBSERVATIONS.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in SOURCES:
        row = dict(source)
        destination = RAW / source["filename"]
        try:
            sha256, byte_count, content_type = download(source["url"], destination)
            row.update(download_status="downloaded", local_path=str(destination.relative_to(ROOT)),
                       sha256=sha256, byte_count=byte_count, content_type=content_type)
        except Exception as exc:  # Preserve the lead even if a host is temporarily unavailable.
            row.update(download_status="failed", local_path="", sha256="", byte_count=0,
                       content_type="", download_error=f"{type(exc).__name__}: {exc}")
        rows.append(row)
    pd.DataFrame(rows).to_csv(REGISTRY, index=False)
    if not OBSERVATIONS.exists():
        pd.DataFrame(columns=OBSERVATION_COLUMNS).to_csv(OBSERVATIONS, index=False)
    print(pd.DataFrame(rows)[["source_id", "download_status", "acquisition_status"]].to_string(index=False))
    print(f"Candidate-level observations currently entered: {len(pd.read_csv(OBSERVATIONS))}")


if __name__ == "__main__":
    main()
