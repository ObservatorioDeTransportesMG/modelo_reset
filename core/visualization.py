import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def plotar_mapa_coropletico(gdf: gpd.GeoDataFrame, coluna: str, titulo: str, cmap: str = "viridis"):
	"""Plota um mapa coroplético (de cores) a partir de uma coluna do GeoDataFrame.

	Args:
		gdf (gpd.GeoDataFrame): O GeoDataFrame a ser plotado.
		coluna (str): O nome da coluna cujos valores serão usados para a coloração.
		titulo (str): O título a ser exibido no topo do mapa.
		cmap (str, optional): O mapa de cores (colormap) a ser utilizado. Padrão é "viridis".
	"""
	fig, ax = plt.subplots(1, 1, figsize=(12, 10))
	gdf.plot(column=coluna, ax=ax, legend=True, cmap=cmap, edgecolor="black", linewidth=0.4)
	ax.set_title(titulo, fontsize=16)
	ax.set_axis_off()
	plt.tight_layout()
	plt.show()


def plotar_polos(gdf_bairros: gpd.GeoDataFrame):
	"""Plota um mapa dos bairros coloridos de acordo com seu "Tipo de Polo".

	Args:
		gdf_bairros (gpd.GeoDataFrame): O GeoDataFrame de bairros, que deve conter a coluna "tipo_polo".
	"""
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


def plotar_centroid_e_bairros(gdf_bairros: gpd.GeoDataFrame, gdf_ibge: gpd.GeoDataFrame):
	"""Plota os polígonos dos bairros e os centroides dos setores censitários.

	Args:
		gdf_bairros (gpd.GeoDataFrame): GeoDataFrame contendo os polígonos dos bairros.
		gdf_ibge (gpd.GeoDataFrame): GeoDataFrame contendo a geometria dos centroides dos setores censitários.
	"""
	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	gdf_bairros.plot(ax=ax, facecolor="lightgray", edgecolor="white", linewidth=0.5)

	if not gdf_ibge.empty:
		gdf_ibge.plot(ax=ax, marker="o", color="red", markersize=20)

	legend_elements = [
		Patch(facecolor="lightgray", edgecolor="black", label="Bairros"),
		Line2D([0], [0], marker="o", color="w", label="Centroids Setores Censitários", markerfacecolor="red", markersize=10),
	]

	ax.legend(handles=legend_elements, title="Legenda", loc="lower right")

	ax.set_title("Bairros e Setores Censitários", fontsize=16)
	ax.set_axis_off()
	plt.tight_layout()
	plt.show()


def plotar_modelo_completo(gdf_bairros: gpd.GeoDataFrame, gdf_pontos: gpd.GeoDataFrame):
	"""Plota o mapa de polos de desenvolvimento junto com pontos de interesse.

	Args:
		gdf_bairros (gpd.GeoDataFrame): GeoDataFrame dos bairros, com a coluna "tipo_polo".
		gdf_pontos (gpd.GeoDataFrame): GeoDataFrame contendo os pontos de interesse (ex: pontos de articulação) a serem sobrepostos no mapa.
	"""
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
