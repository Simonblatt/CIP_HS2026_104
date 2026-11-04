# Visualization for RQ2
# Does the percentage of hiking trails for each difficulty level relate to the mean elevation of a canton?

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

df = pd.read_csv("../results_cantons.csv")

plt.scatter(x = 'mean_elevation_m', y='rq2_mittel (Bergwanderweg)', data=df)

# --- Annotating each dot ---
texts = [
    plt.text(x, y, label, fontsize=8)
    for x, y, label in zip(df['mean_elevation_m'], df['rq2_mittel (Bergwanderweg)'], df['canton'])
]
# --- In case labels overlap ---
adjust_text(
    texts,
    expand=(1.1, 1.3),               # mild padding around text boxes
    force_text=(0.1, 0.2),           # label <-> label repulsion
    force_static=(0.1, 0.2),         # label <-> point repulsion (for the points passed via x, y)
    force_pull=(0.01, 0.01),         # pulls labels back toward their points
)

plt.xlabel("Average elevation canton")
plt.ylabel("% mountain hiking trail")


plt.savefig("plots/rq2_technical.png", dpi=300, bbox_inches="tight")
plt.show()
