import os
from typing import Optional

import geopandas as gpd


def garantir_diretorio(caminho_arquivo: str):
	"""Cria o diretório pai se ele não existir."""
	diretorio = os.path.dirname(caminho_arquivo)
	if diretorio and not os.path.exists(diretorio):
		os.makedirs(diretorio)
		print(f"Diretório criado: {diretorio}")


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
		print(f"Aviso: GeoDataFrame vazio. Nada foi salvo em {caminho_saida}.")
		return

	garantir_diretorio(caminho_saida)

	# Trabalha numa cópia para não alterar o dado original na memória
	gdf_export = gdf.copy()

	# Conversão de CRS (KML e GeoJSON preferem WGS84/EPSG:4326)
	if crs_saida:
		gdf_export = gdf_export.to_crs(crs_saida)
	elif formato in ["kml", "geojson"] and gdf_export.crs != "EPSG:4326":
		print("Aviso: Convertendo automaticamente para EPSG:4326 para compatibilidade web/KML.")
		gdf_export = gdf_export.to_crs("EPSG:4326")

	drivers = {"shapefile": "ESRI Shapefile", "geojson": "GeoJSON", "gpkg": "GPKG"}

	try:
		gdf_export.to_file(caminho_saida, driver=drivers[formato])
		print(f"Sucesso: Arquivo salvo em {caminho_saida}")

	except Exception as e:
		print(f"Erro ao exportar para {caminho_saida}: {e}")
