import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib_map_utils.core.north_arrow import north_arrow
from matplotlib_map_utils.core.scale_bar import scale_bar


def crs_epsg_para_utm_zone(epsg: int) -> int:
	"""Extrai a zona UTM do código EPSG para projeções SIRGAS 2000 no hemisfério sul."""
	if 31978 <= epsg <= 31985:
		return epsg - 31960
	return 0  # Retorno padrão caso não seja um EPSG esperado


def configurar_mapa(ax: Axes, titulo: str, crs_epsg: int):
	"""Função responsável por fazer a configuração padrão dos mapas."""
	ax.set_title(titulo, fontsize=16)
	ax.set_axis_off()
	texto_atribuicao = f"Fonte: Autor\nProjeção: SIRGAS 2000 / UTM Zone {crs_epsg_para_utm_zone(crs_epsg)}S (EPSG:{crs_epsg})"

	ax.text(x=0.5, y=0.01, s=texto_atribuicao, transform=ax.transAxes, ha="center", va="bottom", fontsize="medium", color="black", style="italic")
	scale_bar(ax=ax, location="lower left", style="boxes", bar={"projection": crs_epsg})
	north_arrow(ax=ax, location="upper right", rotation={"crs": crs_epsg, "reference": "center"})
	return ax


def plotar_mapa_coropletico(gdf: gpd.GeoDataFrame, crs_projetado: int, coluna: str, titulo: str, cmap: str = "viridis"):
	"""Plota um mapa coroplético (de cores) a partir de uma coluna do GeoDataFrame.

	Args:
		gdf (gpd.GeoDataFrame): O GeoDataFrame a ser plotado.
		crs_projetado (int): Crs projetado.
		coluna (str): O nome da coluna cujos valores serão usados para a coloração.
		titulo (str): O título a ser exibido no topo do mapa.
		cmap (str, optional): O mapa de cores (colormap) a ser utilizado. Padrão é "viridis".
	"""
	fig, ax = plt.subplots(1, 1, figsize=(12, 10))
	gdf_proj = gdf.to_crs(crs_projetado)
	gdf_proj.plot(column=coluna, ax=ax, legend=True, cmap=cmap, edgecolor="black", linewidth=0.4)
	ax = configurar_mapa(ax, titulo, crs_projetado)
	plt.tight_layout()
	plt.show()


def plotar_polos(gdf_bairros: gpd.GeoDataFrame, crs_projetado: int):
	"""Plota um mapa dos bairros coloridos de acordo com seu "Tipo de Polo".

	Args:
		gdf_bairros (gpd.GeoDataFrame): O GeoDataFrame de bairros, que deve conter a coluna "tipo_polo".
		crs_projetado (int): Crs projetado.
	"""
	if "tipo_polo" not in gdf_bairros.columns:
		print("Coluna 'tipo_polo' não encontrada. Execute a análise de polos primeiro.")
		return

	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	gdf_proj = gdf_bairros.to_crs(crs_projetado)

	color_map = {"Consolidado": "green", "Emergente": "orange", "Planejado": "blue", "Nenhum": "lightgrey"}
	gdf_proj.plot(color=gdf_bairros["tipo_polo"].map(color_map), ax=ax, edgecolor="white", linewidth=0.5)

	legend_elements = [Patch(facecolor=color, edgecolor="w", label=label) for label, color in color_map.items()]

	ax = configurar_mapa(ax, "Polos de Desenvolvimento", crs_projetado)
	ax.legend(handles=legend_elements, title="Tipo de Polo", loc="lower right")

	plt.tight_layout()
	plt.show()


def plotar_centroid_e_bairros(gdf_bairros: gpd.GeoDataFrame, gdf_ibge: gpd.GeoDataFrame, crs_projetado: int):
	"""Plota os polígonos dos bairros e os centroides dos setores censitários.

	Args:
		gdf_bairros (gpd.GeoDataFrame): GeoDataFrame contendo os polígonos dos bairros.
		gdf_ibge (gpd.GeoDataFrame): GeoDataFrame contendo a geometria dos centroides dos setores censitários.
		crs_projetado (int): Crs projetado.
	"""
	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	gdf_bairros_proj = gdf_bairros.to_crs(crs_projetado)
	gdf_bairros_proj.plot(ax=ax, facecolor="lightgray", edgecolor="white", linewidth=0.5)

	if not gdf_ibge.empty:
		gdf_ibge_proj = gdf_ibge.to_crs(crs_projetado)
		gdf_ibge_proj.plot(ax=ax, marker="o", color="red", markersize=20)

	legend_elements = [
		Patch(facecolor="lightgray", edgecolor="black", label="Bairros"),
		Line2D([0], [0], marker="o", color="w", label="Centroids Setores Censitários", markerfacecolor="red", markersize=10),
	]

	ax = configurar_mapa(ax, "Bairros e Setores Censitários", crs_projetado)

	ax.legend(handles=legend_elements, title="Legenda", loc="lower right")

	plt.tight_layout()
	plt.show()


def plotar_modelo_completo(gdf_bairros: gpd.GeoDataFrame, gdf_pontos: gpd.GeoDataFrame, crs_projetado: int):
	"""Plota o mapa de polos de desenvolvimento junto com pontos de interesse.

	Args:
		gdf_bairros (gpd.GeoDataFrame): GeoDataFrame dos bairros, com a coluna "tipo_polo".
		gdf_pontos (gpd.GeoDataFrame): GeoDataFrame contendo os pontos de interesse (ex: pontos de articulação) a serem sobrepostos no mapa.
		crs_projetado (int): Crs projetado.
	"""
	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	color_map = {"Consolidado": "green", "Emergente": "orange", "Planejado": "blue", "Nenhum": "lightgrey"}
	gdf_bairros_plot = gdf_bairros.to_crs(crs_projetado)
	gdf_bairros_plot.plot(color=gdf_bairros["tipo_polo"].map(color_map), ax=ax, edgecolor="white", linewidth=0.5)

	if not gdf_pontos.empty:
		gdf_pontos_proj = gdf_pontos.to_crs(crs_projetado)
		gdf_pontos_proj.plot(ax=ax, marker="o", color="red", markersize=50, label="Pontos de Articulação")

	legend_elements = [Patch(facecolor=color, edgecolor="w", label=label) for label, color in color_map.items()]
	ax = configurar_mapa(ax, "Modelo Completo: Polos e Pontos de Articulação", crs_projetado)

	ax.legend(handles=legend_elements, title="Tipo de Polo", loc="lower right")

	plt.tight_layout()
	plt.show()
