import geopandas as gpd
import pandas as pd
from pyogrio import list_layers


def ler_shapefile(path: str, target_crs: str, original_epsg: int = 4326) -> gpd.GeoDataFrame:
	"""Lê um shapefile, define seu CRS se ausente e o converte para um CRS de destino.

	Args:
		path (str): O caminho para o arquivo shapefile.
		target_crs (str): O CRS de destino para o qual o GeoDataFrame será convertido.
		original_epsg (int, optional): O código EPSG a ser assumido se o arquivo não tiver um CRS definido. Padrão é 4326.

	Returns:
		gpd.GeoDataFrame: Um GeoDataFrame lido a partir do arquivo e
			convertido para o CRS de destino.
	"""
	shapefile = gpd.read_file(path, ignore_geometry=False)
	if shapefile.crs is None:
		print(f"Aviso: CRS não definido para {path}. Assumindo EPSG:{original_epsg}.")
		shapefile = shapefile.set_crs(epsg=original_epsg, inplace=True)

	# Converte para o CRS padrão geográfico para consistência
	shapefile = shapefile.to_crs(target_crs)
	return shapefile


def ler_residencias_csv(path: str, crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
	"""Lê um CSV de residências e o converte para um GeoDataFrame de pontos.

	Args:
		path (str): O caminho para o arquivo CSV. O arquivo deve conter as colunas 'longitude' e 'latitude'.
		crs (str, optional): O CRS dos pontos de geometria. Padrão é "EPSG:4326".

	Returns:
		gpd.GeoDataFrame: Um GeoDataFrame com a geometria de pontos criada a partir das coordenadas do CSV.
	"""
	df = pd.read_csv(path)
	geometria = gpd.points_from_xy(df["longitude"], df["latitude"])
	residencias_gdf = gpd.GeoDataFrame(df, geometry=geometria, crs=crs)
	return residencias_gdf


def ler_od_csv(path: str) -> pd.DataFrame:
	"""Lê um CSV de dados de origem-destino.

	Args:
		path (str): O caminho para o arquivo CSV de origem-destino.

	Returns:
		pd.DataFrame: Um DataFrame do pandas com os dados lidos.
	"""
	return pd.read_csv(path)


def ler_renda_csv(path: str, separador: str = ",", encoding: str = "latin-1") -> pd.DataFrame:
	"""Lê um CSV com dados de renda, com opções de separador e encoding.

	Args:
		path (str): O caminho para o arquivo CSV de renda.
		separador (str, optional): O delimitador de colunas no arquivo. Padrão é ",".
		encoding (str, optional): A codificação do arquivo. Padrão é "latin-1".

	Returns:
		pd.DataFrame: Um DataFrame do pandas com os dados de renda.
	"""
	return pd.read_csv(path, sep=separador, encoding=encoding)


def ler_kml(path: str, target_crs: str) -> gpd.GeoDataFrame:
	"""Lê um arquivo KML, processando e unindo todas as suas camadas.

	Args:
		path (str): O caminho para o arquivo KML.
		target_crs (str): O CRS de destino para o qual o GeoDataFrame final será convertido.

	Returns:
		gpd.GeoDataFrame: Um único GeoDataFrame contendo os dados de todas as camadas do KML, convertido para o CRS de destino. Retorna um GeoDataFrame vazio em caso de erro.
	"""
	gdfs: list[gpd.GeoDataFrame] = []
	try:
		# Habilita o driver KML que pode não estar ativado por padrão
		layers = list_layers(path)
		for layer_info in layers:
			layer_name = layer_info[0]
			gdf = gpd.read_file(path, driver="KML", layer=layer_name)
			gdf["camada"] = layer_name
			gdfs.append(gdf)

		if not gdfs:
			raise ValueError("Nenhuma camada encontrada no arquivo KML.")

		# Concatena todos os GeoDataFrames
		concatenated_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
		return concatenated_gdf.to_crs(target_crs)

	except Exception as e:
		print(f"Erro ao processar KML: {e}")
		return gpd.GeoDataFrame()
