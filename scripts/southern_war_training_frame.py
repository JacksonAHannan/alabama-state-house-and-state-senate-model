"""Content digest of the post-2016 Southern WAR training frame.

The v3 model consumes one query over ``mart_southern_war_training_with_finance``
(see ``retrain_post2016_southern_war_v2.load_training``).  Declaring a digest of
that frame, rather than of the whole warehouse file, lets the release gate
distinguish "the inputs the approved run consumed changed" from "some unrelated
table in the 5.8 GB warehouse changed".  The digest excludes ``build_run_id``,
which changes whenever the preparation target is rerun even with identical
content; the run id is recorded separately in the manifest.
"""
from __future__ import annotations

import hashlib

import pandas as pd

import retrain_post2016_southern_war_v2 as v2

EXCLUDED_COLUMNS = ("build_run_id",)


def training_frame_digest(frame: pd.DataFrame) -> str:
    """SHA-256 of a deterministic CSV serialization of the training frame."""
    ordered = frame.drop(columns=[c for c in EXCLUDED_COLUMNS if c in frame.columns])
    ordered = ordered.sort_values(v2.RACE_KEYS, kind="mergesort").reset_index(drop=True)
    text = ordered.to_csv(index=False, float_format="%.12g", lineterminator="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def live_training_frame_digest() -> tuple[str, str]:
    """Return (digest, warehouse_build_run_id) for the current warehouse."""
    frame, run = v2.load_training()
    return training_frame_digest(frame), str(run["build_run_id"])
