"""Render publication-ready, reproducible charts for the CMO ideology article."""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
OUT = RESEARCH / "charts"

INK = "#15181c"
MUTED = "#66717d"
GRID = "#d8dde3"
PAPER = "#f8fafc"
BLUE = "#3d77a8"
BLUE_DARK = "#24557d"
RED = "#d34b45"
GOLD = "#c58a25"
PURPLE = "#8064a2"


def setup_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": .7,
        "grid.alpha": .75,
        "savefig.facecolor": PAPER,
        "savefig.bbox": "tight",
    })


def title(fig: plt.Figure, headline: str, deck: str) -> None:
    fig.suptitle(headline, x=.06, y=.975, ha="left", fontsize=22, fontweight="bold")
    fig.text(.06, .925, deck, ha="left", va="top", fontsize=11.5, color=MUTED)


def footer(fig: plt.Figure, source: str) -> None:
    fig.text(.06, .025, source, ha="left", va="bottom", fontsize=8.5, color=MUTED)
    fig.text(.94, .025, "Jackson Hannan", ha="right", va="bottom", fontsize=8.5, color=MUTED)


def save(fig: plt.Figure, stem: str) -> list[Path]:
    paths = []
    for suffix in ["png", "svg"]:
        path = OUT / f"{stem}.{suffix}"
        fig.savefig(path, dpi=200 if suffix == "png" else None)
        paths.append(path)
    plt.close(fig)
    return paths


def short_name(name: str) -> str:
    aliases = {
        "BARBARA BIGSBY BOYD": "Barbara Boyd",
        "VIVIAN DAVIS FIGURES": "Vivian Figures",
        "JOHN 'Jody' LETSON": "Jody Letson",
        "John (Jody) Letson": "Jody Letson",
        "LARRY MEANS": "Larry Means",
        "Larry Means": "Larry Means",
    }
    return aliases.get(name, name.title() if name.isupper() else name)


def ideology_scatter() -> list[Path]:
    data = pd.read_csv(RESEARCH / "article_ideology_scatter.csv")
    data = data.loc[data.cycle.le(2018) & data.np_score.notna()].copy()
    sensitivity = pd.read_csv(RESEARCH / "article_ideology_sensitivity.csv")
    overall = sensitivity.loc[
        sensitivity["sample"].eq("all_matched_through_2018")
        & sensitivity.specification.eq("oof_total")
    ].iloc[0]

    fig, ax = plt.subplots(figsize=(10, 6.6))
    fig.subplots_adjust(left=.10, right=.96, top=.84, bottom=.16)
    colors = {2010: BLUE_DARK, 2014: GOLD, 2018: PURPLE}
    for cycle, group in data.groupby("cycle"):
        ax.scatter(
            group.al_dem_caucus_conservative_percentile,
            group.candidate_cmo_total_oof,
            s=np.where(group.incumbent.astype(bool), 58, 39),
            c=colors.get(int(cycle), MUTED), alpha=.77,
            edgecolor=PAPER, linewidth=.7, label=str(int(cycle)), zorder=3,
        )

    # Geography-refit ranges are estimate-sensitivity bars, not confidence intervals.
    sensitive = data.loc[data.cmo_geography_range.fillna(0).ge(5)]
    for row in sensitive.itertuples():
        ax.vlines(
            row.al_dem_caucus_conservative_percentile,
            row.cmo_geography_low, row.cmo_geography_high,
            color=RED, linewidth=1.6, alpha=.85, zorder=2,
        )

    labels = {
        "ALPERSON-BARBARA-BIGSBY-BOYD", "ALPERSON-ANTHONY-DANIELS",
        "ALPERSON-BARBARA-A-DRUMMOND", "ALPERSON-VIVIAN-DAVIS-FIGURES",
        "ALPERSON-LARRY-MEANS", "ALPERSON-JOHNNY-MACK-MORROW",
        "ALPERSON-RICHARD-LINDSEY", "ALPERSON-CRAIG-FORD",
    }
    offsets = {
        "ALPERSON-ANTHONY-DANIELS": (6, 7),
        "ALPERSON-BARBARA-A-DRUMMOND": (-76, -16),
        "ALPERSON-BARBARA-BIGSBY-BOYD": (6, 7),
        "ALPERSON-JOHNNY-MACK-MORROW": (-104, 12),
        "ALPERSON-LARRY-MEANS": (7, -2),
        "ALPERSON-RICHARD-LINDSEY": (-78, 8),
    }
    labeled = (data.loc[data.person_id.isin(labels)]
               .sort_values("candidate_cmo_total_oof")
               .groupby("person_id", as_index=False).tail(1))
    for row in labeled.itertuples():
        ax.annotate(
            short_name(row.candidate),
            (row.al_dem_caucus_conservative_percentile, row.candidate_cmo_total_oof),
            xytext=offsets.get(row.person_id, (6, 5)), textcoords="offset points",
            fontsize=8.5, color=INK,
        )

    ax.axhline(0, color=INK, linewidth=1)
    ax.set_xlim(-2, 102)
    ax.set_xlabel("Conservative percentile within the contemporary Alabama Democratic caucus →")
    ax.set_ylabel("Out-of-fold candidate margin overperformance (points)")
    ax.legend(title="Election", frameon=False, ncol=3, loc="lower left")
    ax.text(
        .50, .98,
        f"Spearman ρ = {overall.spearman_cmo_vs_np_score:.2f}\n"
        f"clustered 95% interval [{overall.cluster_bootstrap_95_low:.2f}, "
        f"{overall.cluster_bootstrap_95_high:.2f}]",
        transform=ax.transAxes, ha="center", va="top", fontsize=10,
        bbox={"boxstyle": "round,pad=.45", "facecolor": "white", "edgecolor": GRID},
    )
    title(
        fig, "Conservatism was not a universal CMO advantage",
        "Clean Shor–McCarty matches through 2018. Red bars show geographic-allocation sensitivity, not confidence intervals.",
    )
    footer(fig, "Sources: project OOF CMO estimates; Shor–McCarty state-legislator ideal points.")
    return save(fig, "01_ideology_vs_cmo")


def repeat_trajectories() -> list[Path]:
    data = pd.read_csv(RESEARCH / "article_repeat_candidate_trajectories.csv")
    people = [
        "ALPERSON-LARRY-MEANS", "ALPERSON-JOHN-JODY-LETSON",
        "ALPERSON-DEXTER-GRIMSLEY", "ALPERSON-BARBARA-BIGSBY-BOYD",
    ]
    data = data.loc[data.person_id.isin(people)].copy()
    display = {
        "ALPERSON-LARRY-MEANS": "Larry Means",
        "ALPERSON-JOHN-JODY-LETSON": "Jody Letson",
        "ALPERSON-DEXTER-GRIMSLEY": "Dexter Grimsley",
        "ALPERSON-BARBARA-BIGSBY-BOYD": "Barbara Boyd",
    }

    fig, axes = plt.subplots(2, 2, figsize=(10, 7.4), sharey=True)
    fig.subplots_adjust(left=.09, right=.96, top=.78, bottom=.13, hspace=.40, wspace=.18)
    for ax, person_id in zip(axes.flat, people):
        group = data.loc[data.person_id.eq(person_id)].sort_values("cycle")
        ax.plot(group.cycle, group.legislative_dem_margin, marker="o", color=BLUE, linewidth=2, label="Legislative D margin")
        ax.plot(group.cycle, group.core_index_margin, marker="o", color=RED, linewidth=2, label="Top-ticket baseline")
        for row in group.itertuples():
            ax.vlines(row.cycle, row.core_index_margin, row.legislative_dem_margin, color=GOLD, linewidth=4, alpha=.38)
            ax.annotate(
                f"CMO {row.candidate_cmo_total_oof:+.0f}",
                (row.cycle, row.legislative_dem_margin), xytext=(0, 8),
                textcoords="offset points", ha="center", fontsize=8, color=INK,
            )
        ax.axhline(0, color=INK, linewidth=.8)
        ax.set_title(display[person_id], fontsize=12)
        ax.set_xticks(group.cycle.unique())
        ax.set_ylim(-65, 70)
    axes[0, 0].set_ylabel("Democratic margin (points)")
    axes[1, 0].set_ylabel("Democratic margin (points)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .855), ncol=2, frameon=False)
    title(
        fig, "Sometimes the candidate held steady while the party moved",
        "Gold connectors show raw legislative overperformance versus the same-cycle top-ticket baseline; labels report contextual OOF CMO.",
    )
    footer(fig, "Source: project candidate-cycle model and canonical top-ticket baselines.")
    return save(fig, "02_repeat_candidate_trajectories")


def matched_pairs() -> list[Path]:
    data = pd.read_csv(RESEARCH / "article_matched_pair_decomposition.csv")
    data = data.loc[data.both_ideology_scores_available.astype(bool)].copy()
    data = data.sort_values("cmo_difference")
    data["label"] = data.focal_candidate.map(short_name) + " vs. " + data.comparison_candidate.map(short_name)

    fig, ax = plt.subplots(figsize=(10, 6.2))
    fig.subplots_adjust(left=.32, right=.95, top=.82, bottom=.16)
    y = np.arange(len(data))
    ax.hlines(y, 0, data.cmo_difference, color=GRID, linewidth=7, zorder=1)
    ax.scatter(data.cmo_difference, y, s=75, color=BLUE, zorder=3, label="Observed CMO gap")
    ax.scatter(data.resource_adjusted_cmo_difference, y, s=55, color=GOLD, marker="D", zorder=3, label="Resource-adjusted gap")
    ax.axvline(0, color=INK, linewidth=1)
    ax.set_yticks(y, data.label)
    ax.set_xlabel("Focal candidate CMO advantage (margin points)")
    ax.legend(frameon=False, loc="lower right")
    for i, row in enumerate(data.itertuples()):
        direction = (
            "more conservative" if row.np_score_difference_focal_minus_comparison > .10
            else "more progressive" if row.np_score_difference_focal_minus_comparison < -.10
            else "similar broad ideology"
        )
        ax.text(
            max(row.cmo_difference, row.resource_adjusted_cmo_difference) + .8, i,
            direction, va="center", fontsize=8.5, color=MUTED,
        )
    title(
        fig, "Large CMO gaps often survived without large ideology gaps",
        "Five matched comparisons with ideology estimates for both candidates. Positive values favor the named focal candidate.",
    )
    footer(fig, "Sources: project matched comparisons, finance features, and Shor–McCarty scores.")
    return save(fig, "03_matched_pair_gaps")


def issue_heatmap() -> list[Path]:
    data = pd.read_csv(RESEARCH / "article_issue_heatmap.csv")
    dimensions = [
        "economic_ideology", "labor_position", "guns_position",
        "abortion_position", "social_ideology",
    ]
    candidates = [
        "Larry Means", "Johnny Mack Morrow", "Craig Ford", "Henry A. White",
        "Tammy Irons", "Darrell Turner", "Alli Summerford", "Felicia Stewart",
        "David “Coach” Burkette", "David \"Coach\" Burkette",
        "Barbara A. Drummond", "Vivian Davis Figures", "Billy Beasley",
        "Randall White", "Alan Harper", "Linda Meigs", "Kim Caudle Lewis",
        "James C. Fields Jr.", "Rex Cheatham",
    ]
    data = data.loc[data.dimension.isin(dimensions)].copy()
    data["candidate_display"] = data.candidate.map(short_name)
    requested = {name.replace("“", '"').replace("”", '"') for name in candidates}
    data = data.loc[data.candidate_display.str.replace("“", '"').str.replace("”", '"').isin(requested)]
    matrix = data.pivot_table(index="candidate_display", columns="dimension", values="coded_value", aggfunc="first")
    matrix = matrix.reindex(columns=dimensions).dropna(how="all")
    matrix = matrix.loc[matrix.mean(axis=1, skipna=True).sort_values().index]

    cmap = LinearSegmentedColormap.from_list("ideology", [BLUE_DARK, "#dce7ef", "#ffffff", "#f4ddd9", RED])
    fig, ax = plt.subplots(figsize=(10, max(5.8, .43 * len(matrix) + 2.2)))
    fig.subplots_adjust(left=.23, right=.96, top=.82, bottom=.18)
    masked = np.ma.masked_invalid(matrix.to_numpy(dtype=float))
    image = ax.imshow(masked, cmap=cmap, vmin=-2, vmax=2, aspect="auto")
    ax.set_yticks(np.arange(len(matrix)), matrix.index)
    labels = ["Economic", "Labor", "Guns", "Abortion", "Other social"]
    ax.set_xticks(np.arange(len(dimensions)), labels)
    ax.tick_params(axis="x", rotation=0)
    ax.grid(False)
    for i in range(len(matrix)):
        for j in range(len(dimensions)):
            value = matrix.iloc[i, j]
            ax.text(j, i, "—" if pd.isna(value) else f"{value:+.0f}", ha="center", va="center", fontsize=9, color=MUTED if pd.isna(value) else INK)
    cbar = fig.colorbar(image, ax=ax, fraction=.025, pad=.025)
    cbar.set_ticks([-2, 0, 2], labels=["Progressive", "Mixed", "Conservative"])
    title(
        fig, "The overperformer profile was a bundle, not a single ideology",
        "Only time-eligible candidate-cycle evidence is shown. Blank cells are unknown—not moderate positions.",
    )
    footer(fig, "Source: sourced candidate evidence ledger; codes range from -2 (progressive) to +2 (conservative).")
    return save(fig, "04_issue_bundle_heatmap")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup_style()
    paths = []
    for builder in [ideology_scatter, repeat_trajectories, matched_pairs, issue_heatmap]:
        paths.extend(builder())

    manifest = []
    for path in sorted(paths):
        manifest.append({
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    pd.DataFrame(manifest).to_csv(OUT / "chart_manifest.csv", index=False)
    print(f"Rendered {len(paths)} chart files and chart_manifest.csv")


if __name__ == "__main__":
    main()
