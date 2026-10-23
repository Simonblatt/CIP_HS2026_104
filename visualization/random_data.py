# crating a random data set to test visualizations

import numpy as np
import pandas as pd

df = pd.read_excel("../Geographische_Kennzahlen.xlsx")
print(df.head())

df = df.drop(columns=['E_CNTR', 'N_CNTR', 'E_MIN', 'E_MAX', 'N_MIN', 'N_MAX'])
print(df.head())

rng = np.random.default_rng(seed=42)    # seed makes it reproducible
df["routes_h_tot"] = rng.integers(0, 10, size=len(df))
df["routes_h_1200"] = rng.integers(0, 7, size=len(df))
df["dens_h_1200"] = rng.random(len(df))
df["amount_leicht"] = rng.integers(0, 10, size=len(df))
df["amount_mittel"] = rng.integers(0, 10, size=len(df))
df["amount_schwer"] = rng.integers(0, 10, size=len(df))
df["dens_velo"] = rng.random(len(df))
df["dens_mb"] = rng.random(len(df))
df["dens_sk"] = rng.random(len(df))
df["dens_can"] = rng.random(len(df))

df.to_csv("random_data.csv", index=False)

