import os
from typing import Optional

import geopandas as gpd


def garantir_diretorio(caminho_arquivo: str):
	"""Cria o diretório pai se ele não existir."""
	diretorio = os.path.dirname(caminho_arquivo)
	if diretorio and not os.path.exists(diretorio):
		os.makedirs(diretorio)


def exportar_geodataframe(gdf: gpd.GeoDataFrame, caminho_saida: str, formato: str = "shapefile", crs_saida: Optional[str] = None):
	"""
	Exporta um GeoDataFrame para arquivo.

	Args:
		gdf: O GeoDataFrame a ser salvo.
		caminho_saida: Caminho completo do arquivo (ex: 'saida/rotas.shp').
		formato: 'shapefile', 'geojson', 'gpkg', 'kml'.
		crs_saida: (Opcional) Converter para este CRS antes de salvar (ex: "EPSG:4326").
	"""
	if gdf.empty:
		return

	garantir_diretorio(caminho_saida)

	# Trabalha numa cópia para não alterar o dado original na memória
	gdf_export = gdf.copy()

	# Conversão de CRS (KML e GeoJSON preferem WGS84/EPSG:4326)
	if crs_saida:
		gdf_export = gdf_export.to_crs(crs_saida)
	elif formato in ["kml", "geojson"] and gdf_export.crs != "EPSG:4326":
		gdf_export = gdf_export.to_crs("EPSG:4326")

	drivers = {"shapefile": "ESRI Shapefile", "geojson": "GeoJSON", "gpkg": "GPKG"}

	try:
		gdf_export.to_file(caminho_saida, driver=drivers[formato])

	except Exception as e:
		raise ValueError(e)
