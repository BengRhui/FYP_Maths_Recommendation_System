"""
A script that converts the BKT params from training into a JSON for system use.
"""

import json
import sys
from pathlib import Path

import pandas as pd

# Set up the directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PARQUET_PATH = REPO_ROOT / "research/dataset/0_cleaned/bkt_params.parquet"
OUTPUT_PATH = REPO_ROOT / "ml_engine/saved_models/bkt_params.json"
sys.path.insert(0, str(REPO_ROOT))

# Extract the boundaries set in BKT
from ml_engine.bkt import _MAX_GUESS, _MAX_SLIP, _PRIOR_RANGE

# Rename the parameters
PARAM_RENAME = {
    "prior": "p_init",
    "learns": "p_transit",
    "guesses": "p_guess",
    "slips": "p_slip",
}

# The function to be executed when running the script
def main():

    # Read the parquet
    raw = pd.read_parquet(PARQUET_PATH)

    # Remove the forget parameter and rename the table
    wide = (
        raw[raw["param"] != "forgets"]
        .pivot(index="skill", columns="param", values="value")
        .rename(columns=PARAM_RENAME)
    )

    # Calculate the total number of skills in the dataset
    total_fitted = len(wide)

    # Only retain valid values for each param
    non_degenerate = wide[(wide["p_guess"] <= _MAX_GUESS) & (wide["p_slip"] <= _MAX_SLIP)].copy()
    non_degenerate["p_init"] = non_degenerate["p_init"].clip(*_PRIOR_RANGE)

    # Calculated the average for each param
    pooled = non_degenerate[["p_init", "p_transit", "p_slip", "p_guess"]].mean().round(4)

    # Store the details in dictionary format
    output = {
        "meta": {
            "source": str(PARQUET_PATH.relative_to(REPO_ROOT)),
            "generated_by": str(Path(__file__).relative_to(REPO_ROOT)),
            "method": "pooled mean of every non-degenerate skill fit",
            "total_skills_fitted": int(total_fitted),
            "non_degenerate": int(len(non_degenerate)),
            "degenerate_filter": f"guess <= {_MAX_GUESS} and slip <= {_MAX_SLIP}",
            "prior_clamped_to": list(_PRIOR_RANGE),
        },
        "pooled": {
            "p_init": float(pooled["p_init"]),
            "p_transit": float(pooled["p_transit"]),
            "p_slip": float(pooled["p_slip"]),
            "p_guess": float(pooled["p_guess"]),
        },
    }

    # Output results to JSON
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Pooled {len(non_degenerate)}/{total_fitted} non-degenerate skill fits.")
    print(json.dumps(output, indent=2))
    print(f"\nWritten to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(
        "\nUpdate ml_engine.bkt.BKTParams' defaults (and, if you want them to "
        "stay in sync, MicroSkill.bkt_p_* in curriculum/models.py) to match "
        "the 'pooled' values above."
    )


# Run the script
if __name__ == "__main__":
    main()
