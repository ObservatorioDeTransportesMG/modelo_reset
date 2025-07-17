import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def plotar_mapa_coropletico(gdf: gpd.GeoDataFrame, coluna: str, titulo: str, cmap: str = "viridis"):
	"""Plota um mapa coroplético (de cores)."""
	fig, ax = plt.subplots(1, 1, figsize=(12, 10))
	gdf.plot(column=coluna, ax=ax, legend=True, cmap=cmap, edgecolor="black", linewidth=0.4)
	ax.set_title(titulo, fontsize=16)
	ax.set_axis_off()
	plt.tight_layout()
	plt.show()


def plotar_polos(gdf_bairros: gpd.GeoDataFrame):
	"""Plota o mapa de Polos de Desenvolvimento."""
	if "tipo_polo" not in gdf_bairros.columns:
		print("Coluna 'tipo_polo' não encontrada. Execute a análise de polos primeiro.")
		return

	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	color_map = {"Consolidado": "green", "Emergente": "orange", "Planejado": "blue", "Nenhum": "lightgrey"}
	gdf_bairros.plot(color=gdf_bairros["tipo_polo"].map(color_map), ax=ax, edgecolor="white", linewidth=0.5)

	legend_elements = [Patch(facecolor=color, edgecolor="w", label=label) for label, color in color_map.items()]
	ax.legend(handles=legend_elements, title="Tipo de Polo", loc="lower right")

	ax.set_title("Polos de Desenvolvimento", fontsize=16)
	ax.set_axis_off()
	plt.tight_layout()
	plt.show()


def plotar_modelo_completo(gdf_bairros: gpd.GeoDataFrame, gdf_pontos: gpd.GeoDataFrame):
	"""Plota o mapa de polos junto com os pontos de articulação."""
	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	color_map = {"Consolidado": "green", "Emergente": "orange", "Planejado": "blue", "Nenhum": "lightgrey"}
	gdf_bairros.plot(color=gdf_bairros["tipo_polo"].map(color_map), ax=ax, edgecolor="white", linewidth=0.5)

	if not gdf_pontos.empty:
		gdf_pontos.plot(ax=ax, marker="o", color="red", markersize=50, label="Pontos de Articulação")

	legend_elements = [Patch(facecolor=color, edgecolor="w", label=label) for label, color in color_map.items()]
	ax.legend(handles=legend_elements, title="Tipo de Polo", loc="lower right")

	ax.set_title("Modelo Completo: Polos e Pontos de Articulação", fontsize=16)
	ax.set_axis_off()
	plt.tight_layout()
	plt.show()
