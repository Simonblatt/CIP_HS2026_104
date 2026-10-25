# Visualization for RQ2
# Does the percentage of hiking trails for each difficulty level relate to the mean elevation of a canton?

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

df = pd.read_csv("../rq2_result_difficulty_elevation.csv")

plt.scatter(x = 'Z_AVG', y='mittel (Bergwanderweg)', data=df)

# Annotating each dot
texts = [
    plt.text(x, y, label, fontsize=8)
    for x, y, label in zip(df['Z_AVG'], df['mittel (Bergwanderweg)'], df['canton'])
]
# In case labels overlap
adjust_text(
    texts,
    expand=(1.5, 1.8),
    force_text=(0.5, 0.8),
    force_static=(0.5, 0.8),
)

plt.xlabel("Average elevation canton")
plt.ylabel("% Bergwanderwege")

plt.show()