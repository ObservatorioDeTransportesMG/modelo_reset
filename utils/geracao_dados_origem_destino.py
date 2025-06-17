import geopandas as gpd
import numpy as np
import pandas as pd

residencias = pd.read_csv("residencias_tratado.csv")
df = pd.DataFrame()

# Shuffle independente
df["longitude_origem"] = np.random.permutation(residencias["longitude"].values)
df["latitude_origem"] = np.random.permutation(residencias["latitude"].values)
df["longitude_destino"] = np.random.permutation(residencias["longitude"].values)
df["latitude_destino"] = np.random.permutation(residencias["latitude"].values)

df.to_csv("origem_destino.csv")
