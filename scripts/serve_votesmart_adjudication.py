"""Serve a localhost UI for manual adjudication of CMO-relevant Vote Smart items."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import pandas as pd

from votesmart_position_ontology import AXES, DOMAINS, ONTOLOGY_VERSION, validate_effect


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
LEGACY_MANUAL = ROOT / "data" / "manual" / "ideology" / "votesmart_pct_manual_adjudications.csv"
MANUAL = ROOT / "data" / "manual" / "ideology" / "votesmart_pct_multiaxis_v2_manual_adjudications.csv"
AUTO = IDEOLOGY / "votesmart_pct_multiaxis_v2_auto_adjudications.csv"
PAGE = ROOT / "dashboard" / "votesmart_adjudication.html"
DECISION_COLUMNS = [
    "ontology_version", "review_id", "election_year", "normalized_option",
    "decision", "primary_domain", "policy_domains_json", "policy_key", "effects_json", "confidence",
    "response_mode", "reviewer_notes", "reviewed_at_utc",
]


def normalize(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return re.sub(r"^(?:[a-z]|[0-9]+)\)\s*", "", text)


def text_or_empty(value: object) -> str:
    """Return display text without leaking pandas NaN into browser JSON."""
    return "" if pd.isna(value) else str(value)


def review_id(year: object, option: str) -> str:
    return hashlib.sha256(f"{int(float(year))}|{option}".encode()).hexdigest()[:16].upper()


def load_items() -> list[dict]:
    pct = pd.read_csv(IDEOLOGY / "votesmart_pct_coded_responses.csv", low_memory=False)
    audit = pd.read_csv(IDEOLOGY / "votesmart_pct_adjudication_audit.csv")
    crosswalk = pd.read_csv(IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv")
    models = pd.read_csv(IDEOLOGY / "votesmart_pct_group_llm_classifications.csv")
    keys = ["election_year", "section", "question", "option_text"]
    pct = pct.drop(columns=["adjudication_status"], errors="ignore").merge(
        audit[keys + ["adjudication_status"]], on=keys, how="left", validate="many_to_one"
    )
    accepted = crosswalk[crosswalk.accepted][
        ["election_year", "votesmart_candidate_id", "canonical_candidate_id", "canonical_candidate"]
    ].copy()
    accepted.votesmart_candidate_id = pd.to_numeric(accepted.votesmart_candidate_id, errors="coerce")
    pct = pct.merge(accepted, on=["election_year", "votesmart_candidate_id"], how="inner")
    pct = pct[pct.selected.eq(True) & pct.adjudication_status.isin(
        ["model_agreement_requires_rule", "model_disagreement_requires_review"]
    )].copy()
    pct["normalized_option"] = pct.option_text.map(normalize)
    models["normalized_option"] = models.normalized_option.map(normalize)
    model_fields = ["model", "dimension", "affirmative_direction", "scorable", "confidence",
                    "policy_key", "plain_english_policy", "review_reason"]
    model_map = {
        option: group[model_fields].fillna("").to_dict("records")
        for option, group in models.groupby("normalized_option")
    }
    rows = []
    for (year, option), group in pct.groupby(["election_year", "normalized_option"]):
        representative = group.sort_values("candidate", na_position="last").iloc[0]
        candidates = sorted(set(group.canonical_candidate.dropna().astype(str)))
        rows.append({
            "review_id": review_id(year, option), "election_year": int(year),
            "section": text_or_empty(representative.section),
            "question": text_or_empty(representative.question),
            "option_text": text_or_empty(representative.option_text),
            "normalized_option": option,
            "adjudication_status": text_or_empty(representative.adjudication_status),
            "selected_response_count": int(len(group)),
            "candidate_count": int(group.canonical_candidate_id.nunique()),
            "candidates": candidates, "models": model_map.get(option, []),
        })
    rows.sort(key=lambda row: (-row["candidate_count"], -row["selected_response_count"],
                               row["election_year"], row["section"]))
    proposals_path = IDEOLOGY / "votesmart_pct_multiaxis_v2_classifications.csv"
    if proposals_path.exists():
        proposals = pd.read_csv(proposals_path).fillna("")
        proposal_map = {
            str(identifier): group[["stage", "model", "primary_domain", "policy_key",
                                    "plain_english_policy", "substantive", "effects_json",
                                    "confidence", "review_reason"]].to_dict("records")
            for identifier, group in proposals.groupby("review_id")
        }
        for row in rows:
            row["multiaxis_models"] = proposal_map.get(row["review_id"], [])
    else:
        for row in rows:
            row["multiaxis_models"] = []
    legacy_map = {}
    if LEGACY_MANUAL.exists() and LEGACY_MANUAL.stat().st_size:
        legacy = pd.read_csv(LEGACY_MANUAL).fillna("")
        legacy_map = {str(record["review_id"]): record.to_dict()
                      for _, record in legacy.iterrows()}
    for row in rows:
        row["legacy_decision"] = legacy_map.get(row["review_id"], {})
    return rows


def load_decisions() -> dict[str, dict]:
    decisions = {}
    if AUTO.exists() and AUTO.stat().st_size:
        frame = pd.read_csv(AUTO).fillna("")
        decisions.update({str(row["review_id"]): row.to_dict() for _, row in frame.iterrows()})
    if MANUAL.exists() and MANUAL.stat().st_size:
        frame = pd.read_csv(MANUAL).fillna("")
        decisions.update({str(row["review_id"]): row.to_dict() for _, row in frame.iterrows()})
    return decisions


def save_decision(payload: dict) -> None:
    allowed = {column: payload.get(column, "") for column in DECISION_COLUMNS}
    allowed["ontology_version"] = ONTOLOGY_VERSION
    allowed["reviewed_at_utc"] = datetime.now(timezone.utc).isoformat()
    if allowed["decision"] not in {"adjudicated", "non_substantive", "skip"}:
        raise ValueError("invalid decision")
    if allowed["decision"] == "adjudicated":
        if allowed["primary_domain"] not in DOMAINS:
            raise ValueError("adjudicated items require a primary domain")
        effects = json.loads(allowed["effects_json"] or "[]")
        if not isinstance(effects, list):
            raise ValueError("effects must be a list")
        for effect in effects:
            validate_effect(effect)
        allowed["effects_json"] = json.dumps(effects, separators=(",", ":"))
        domains = json.loads(allowed["policy_domains_json"] or "[]")
        if allowed["primary_domain"] not in domains:
            domains.insert(0, allowed["primary_domain"])
        if any(domain not in DOMAINS for domain in domains):
            raise ValueError("invalid policy domain")
        allowed["policy_domains_json"] = json.dumps(list(dict.fromkeys(domains)), separators=(",", ":"))
    else:
        allowed["effects_json"] = "[]"
        if allowed["decision"] == "non_substantive":
            allowed["primary_domain"] = "non_substantive"
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    existing = pd.read_csv(MANUAL).fillna("") if MANUAL.exists() and MANUAL.stat().st_size else pd.DataFrame(columns=DECISION_COLUMNS)
    existing = existing[existing.review_id.astype(str).ne(str(allowed["review_id"]))]
    result = pd.concat([existing, pd.DataFrame([allowed])], ignore_index=True)[DECISION_COLUMNS]
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=MANUAL.parent, suffix=".tmp") as handle:
        result.to_csv(handle, index=False)
        temporary = Path(handle.name)
    temporary.replace(MANUAL)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/items":
            self.send_json({"items": load_items(), "decisions": load_decisions(),
                            "ontology_version": ONTOLOGY_VERSION, "axes": AXES,
                            "domains": DOMAINS,
                            "legacy_decisions_path": str(LEGACY_MANUAL.relative_to(ROOT))})
            return
        if path in {"/", "/index.html"}:
            content = PAGE.read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content))); self.end_headers(); self.wfile.write(content)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/adjudicate":
            self.send_error(404); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            save_decision(payload)
            self.send_json({"ok": True})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def send_json(self, payload: dict, status: int = 200) -> None:
        content = json.dumps(payload, allow_nan=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content))); self.end_headers(); self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(preferred_port: int = 8765) -> ThreadingHTTPServer:
    """Bind locally, using an OS-assigned port if Windows blocks the preferred one."""
    try:
        return ThreadingHTTPServer(("127.0.0.1", preferred_port), Handler)
    except OSError as exc:
        if preferred_port == 0:
            raise
        print(f"Port {preferred_port} is unavailable ({exc}); selecting a free port.")
        return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765,
                        help="preferred localhost port (default: 8765; 0 selects a free port)")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    server = create_server(args.port)
    port = server.server_address[1]
    print(f"Vote Smart adjudication UI: http://127.0.0.1:{port} ({len(load_items())} items)")
    print("Press Ctrl+C to stop. Decisions autosave to", MANUAL)
    server.serve_forever()


if __name__ == "__main__":
    main()
