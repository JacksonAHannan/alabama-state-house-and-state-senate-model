"""Build the caucus compatibility page and provide its current data payload."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer
from sklearn.manifold import MDS
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research" / "cmo_ideology" / "democratic_clusters"
OUTPUT = ROOT / "artifacts" / "site" / "caucuses.html"
PREFIX = "primitive_conservative_"

ISSUE_LABELS = {
    "abortion_access": "Abortion access",
    "anti_discrimination": "Anti-discrimination",
    "civil_social_liberty": "Christian sexual morality",
    "criminal_punishment": "Criminal punishment",
    "education_market_choice": "School choice",
    "environmental_protection": "Environmental protection",
    "government_ethics_transparency": "Ethics and transparency",
    "gun_access": "Gun access",
    "gun_purchase_regulation": "Gun purchase rules",
    "healthcare_access": "Health-care access",
    "labor_capital_alignment": "Labor or management",
    "market_governance": "Market autonomy",
    "marriage_equality": "Marriage equality",
    "public_spending": "Public spending",
    "tax_burden": "Tax burden",
    "voting_access": "Voting access",
    "welfare_conditionality": "Benefit conditions",
    "welfare_generosity": "Material support",
}


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def constellation_coordinates(
    members: pd.DataFrame, profiles: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Project the party-specific clustering space into two dimensions."""
    output, metadata = members.copy(), {}
    output["constellation_x"] = output["constellation_y"] = np.nan
    output["constellation_coverage"] = np.nan
    for party, index in output.groupby("party").groups.items():
        party_profiles = profiles[profiles.party.eq(party)]
        features = [
            column
            for column in party_profiles
            if column.startswith(PREFIX) and party_profiles[column].notna().any()
        ]
        raw = output.loc[index, features].astype(float)
        normalized = (raw - raw.mean()) / raw.std(ddof=0).replace(0, 1)
        matrix = KNNImputer(
            n_neighbors=min(7, max(2, len(raw) - 1)), weights="distance"
        ).fit_transform(normalized)
        matrix = StandardScaler().fit_transform(matrix)
        model = MDS(
            n_components=2,
            metric=True,
            n_init=8,
            max_iter=1000,
            eps=1e-6,
            dissimilarity="euclidean",
            random_state=20260821,
        )
        coordinates = model.fit_transform(matrix)
        coordinates -= coordinates.mean(axis=0)
        ideological_mean = matrix.mean(axis=1)
        if np.corrcoef(coordinates[:, 0], ideological_mean)[0, 1] < 0:
            coordinates[:, 0] *= -1
        if coordinates[np.argmax(np.abs(coordinates[:, 1])), 1] < 0:
            coordinates[:, 1] *= -1
        scale = np.max(np.abs(coordinates), axis=0)
        coordinates /= np.where(scale == 0, 1, scale)
        output.loc[index, ["constellation_x", "constellation_y"]] = coordinates
        output.loc[index, "constellation_coverage"] = raw.notna().sum(axis=1) / len(
            features
        )
        metadata[party] = {
            "dimensions": len(features),
            "stress": float(model.stress_),
            "candidate_cycles": len(raw),
        }
    return output, metadata


def payload() -> dict:
    members = pd.read_csv(
        SOURCE / "democratic_candidate_cluster_membership.csv", low_memory=False
    )
    profiles = pd.read_csv(SOURCE / "democratic_cluster_profiles.csv")
    diagnostics = pd.read_csv(SOURCE / "cluster_model_diagnostics.csv")
    sensitivity = pd.read_csv(SOURCE / "cluster_sensitivity.csv")
    era = pd.read_csv(SOURCE / "cluster_era_composition.csv")
    performance = pd.read_csv(SOURCE / "democratic_cluster_summary.csv")
    issues = sorted(
        {column.removeprefix(PREFIX) for column in profiles if column.startswith(PREFIX)}
    )
    members, constellation = constellation_coordinates(members, profiles)
    member_columns = [
        "canonical_candidate_id",
        "canonical_name",
        "person_id",
        "party",
        "cycle",
        "chamber",
        "district",
        "cluster_id",
        "cluster_label",
        "cluster_dimensions_observed",
        "era",
        "winner",
        "incumbent",
        "candidate_cmo",
        "candidate_federal_overperformance",
        "candidate_presidential_overperformance",
        "constellation_x",
        "constellation_y",
        "constellation_coverage",
        *[PREFIX + issue for issue in issues if PREFIX + issue in members],
    ]
    selected = diagnostics[diagnostics.selected.eq(True)]
    return {
        "members": records(members[member_columns]),
        "profiles": records(profiles),
        "diagnostics": records(selected),
        "sensitivity": records(sensitivity),
        "era": records(era),
        "performance": records(performance),
        "issues": [
            {
                "key": issue,
                "label": ISSUE_LABELS.get(issue, issue.replace("_", " ").title()),
            }
            for issue in issues
        ],
        "constellation": constellation,
    }


def build() -> str:
    """Retain the former public URL without maintaining a second dashboard."""
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0; url=ideology-performance.html#candidate-explorer">
<link rel="canonical" href="ideology-performance.html#candidate-explorer">
<title>Ideology and caucuses · Jackson Hannan</title></head>
<body><p>The caucus explorer is now part of the
<a href="ideology-performance.html#candidate-explorer">ideology and performance page</a>.</p>
<script>location.replace('ideology-performance.html#candidate-explorer');</script></body></html>'''


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
