# Visualization for RQ2
# Does the percentage of hiking trails for each difficulty level relate to the mean elevation of a canton?

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text
from pathlib import Path
import numpy as np

df = pd.read_csv("../results_cantons.csv")

cols = {
    "Easy": "rq2_condition_leicht",
    "Medium": "rq2_condition_mittel",
    "Difficult": "rq2_condition_schwer",
}

fig, ax = plt.subplots(figsize=(9, 6))

for label, col in cols.items():
    share = df[col] / df["rq3_wanderland_routes"] * 100

    sc = ax.scatter(df["mean_elevation_m"], share, label=label)
    color = sc.get_facecolor()[0]

    # Trend line (same color, no label, so no extra legend entry)
    mask = share.notna()
    m, b = np.polyfit(df.loc[mask, "mean_elevation_m"], share[mask], 1)
    xs = np.linspace(df["mean_elevation_m"].min(), df["mean_elevation_m"].max(), 100)
    ax.plot(xs, m * xs + b, color=color, alpha=0.6)

ax.set_xlabel("Average elevation canton (m)")
ax.set_ylabel("Share of routes (%)")
ax.legend(title="Condition level")

Path("plots").mkdir(exist_ok=True)
fig.savefig("plots/rq2_condition.png", dpi=300, bbox_inches="tight")
plt.show()