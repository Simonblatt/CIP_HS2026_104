# This file combines the results of all three research questions

import pandas as pd

canton_abbreviations = {
    1: "ZH", 2: "BE", 3: "LU", 4: "UR", 5: "SZ", 6: "OW", 7: "NW", 8: "GL", 9: "ZG",
    10: "FR", 11: "SO", 12: "BS", 13: "BL", 14: "SH", 15: "AR", 16: "AI", 17: "SG",
    18: "GR", 19: "AG", 20: "TG", 21: "TI", 22: "VD", 23: "VS", 24: "NE", 25: "GE", 26: "JU"
}

df_rq1 = pd.read_csv('rq1_result_density_below_1200m.csv')
df_rq2 = pd.read_csv('rq2_result_difficulty_elevation.csv')
df_rq3 = pd.read_csv('rq3_result_combined_index.csv')

data_combined = pd.merge(df_rq1, df_rq2, on='canton')
data_combined = pd.merge(data_combined, df_rq3, on='canton')

#Adding canton numbers is necessary for creating the map
canton_numbers = {abbr: num for num, abbr in canton_abbreviations.items()}

data_combined.insert(
    data_combined.columns.get_loc("canton") + 1,
    "kantonsnummer",
    data_combined["canton"].map(canton_numbers),
)

data_combined.to_csv('data_combined.csv', index=False)