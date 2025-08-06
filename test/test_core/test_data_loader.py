# test_leitores.py

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

# Importe as funções do seu módulo
# Assumindo que o arquivo se chama 'leitores.py'
from core.data_loader import ler_kml, ler_od_csv, ler_renda_csv, ler_residencias_csv, ler_shapefile

# --- Constantes de Teste ---
CRS_GEO = "EPSG:4326"  # WGS 84
CRS_PROJETADO = "EPSG:31983"  # SIRGAS 2000 / UTM zone 23S

# --- Testes para ler_shapefile ---


def test_ler_shapefile_com_crs_definido(tmp_path):
	"""
	Testa a leitura de um shapefile que já possui um CRS definido.

	Usa a fixture 'tmp_path' do pytest para criar um diretório temporário.
	"""
	# 1. Cria um GeoDataFrame de teste
	gdf_original = gpd.GeoDataFrame({"id": [1], "data": ["teste"]}, geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs=CRS_GEO)
	# 2. Salva como um shapefile temporário
	caminho_shp = tmp_path / "teste.shp"
	gdf_original.to_file(caminho_shp, driver="ESRI Shapefile")

	# 3. Executa a função
	resultado_gdf = ler_shapefile(str(caminho_shp), target_crs=CRS_PROJETADO)

	# 4. Verifica os resultados
	assert isinstance(resultado_gdf, gpd.GeoDataFrame)
	assert resultado_gdf.crs.to_string() == CRS_PROJETADO
	assert len(resultado_gdf) == 1


def test_ler_shapefile_sem_crs_definido(mocker, tmp_path):
	"""
	Testa a leitura de um shapefile sem CRS, verificando se o CRS padrão é atribuído.

	Usa 'mocker' para simular a leitura do arquivo e retornar um GDF sem CRS.
	"""
	# 1. Cria um GeoDataFrame de teste sem CRS
	gdf_sem_crs = gpd.GeoDataFrame(
		{"id": [1]},
		geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
		crs=None,  # CRS é None
	)
	caminho_shp = tmp_path / "teste_sem_crs.shp"
	gdf_sem_crs.to_file(caminho_shp)  # Salva sem CRS info

	# 2. Simula (mock) a função gpd.read_file para retornar nosso GDF sem CRS
	#    e também espiona a função print para ver se o aviso é impresso.
	mock_read_file = mocker.patch("core.data_loader.gpd.read_file", return_value=gdf_sem_crs)
	mock_print = mocker.patch("builtins.print")

	# 3. Executa a função
	resultado_gdf = ler_shapefile(str(caminho_shp), target_crs=CRS_PROJETADO, original_epsg=4326)

	# 4. Verifica os resultados
	mock_read_file.assert_called_once_with(str(caminho_shp), ignore_geometry=False)
	mock_print.assert_called_once_with("Aviso: CRS não definido para " + str(caminho_shp) + ". Assumindo EPSG:4326.")
	assert resultado_gdf.crs.to_string() == CRS_PROJETADO


# --- Testes para leitores de CSV ---


def test_ler_residencias_csv(tmp_path):
	"""Testa a leitura de um CSV com coordenadas e sua conversão para GeoDataFrame."""
	# 1. Cria um arquivo CSV temporário
	caminho_csv = tmp_path / "residencias.csv"
	conteudo_csv = "id,latitude,longitude\n1,-23.55, -46.63\n2,-22.90,-43.17"
	caminho_csv.write_text(conteudo_csv)

	# 2. Executa a função
	resultado_gdf = ler_residencias_csv(str(caminho_csv))

	# 3. Verifica os resultados
	assert isinstance(resultado_gdf, gpd.GeoDataFrame)
	assert len(resultado_gdf) == 2
	assert resultado_gdf.crs.to_string() == CRS_GEO
	assert resultado_gdf.geometry.iloc[0].x == -46.63


def test_ler_residencias_csv_coluna_faltando(tmp_path):
	"""Testa se a função falha corretamente se uma coluna de coordenada estiver faltando."""
	caminho_csv = tmp_path / "residencias_malformado.csv"
	conteudo_csv = "id,lat\n1,-23.55"  # Falta a coluna 'longitude'
	caminho_csv.write_text(conteudo_csv)

	# Verifica se um KeyError é levantado, como esperado
	with pytest.raises(KeyError):
		ler_residencias_csv(str(caminho_csv))


def test_ler_od_csv(tmp_path):
	"""Testa a leitura simples de um CSV para um DataFrame."""
	caminho_csv = tmp_path / "od.csv"
	conteudo_csv = "origem,destino,fluxo\nA,B,100\nB,C,200"
	caminho_csv.write_text(conteudo_csv)

	resultado_df = ler_od_csv(str(caminho_csv))

	assert isinstance(resultado_df, pd.DataFrame)
	assert len(resultado_df) == 2
	assert "fluxo" in resultado_df.columns


def test_ler_renda_csv(tmp_path):
	"""Testa a leitura de um CSV com separador e encoding customizados."""
	caminho_csv = tmp_path / "renda.csv"
	# Conteúdo com ponto-e-vírgula e caractere especial (ç)
	conteudo_csv = "setor;renda;população\n1;5000;150\n2;3000;200"
	# Salva usando encoding 'latin-1'
	caminho_csv.write_text(conteudo_csv, encoding="latin-1")

	# Executa a função passando os parâmetros corretos
	resultado_df = ler_renda_csv(str(caminho_csv), separador=";", encoding="latin-1")

	assert isinstance(resultado_df, pd.DataFrame)
	assert len(resultado_df) == 2
	assert "população" in resultado_df.columns
	assert resultado_df["renda"].iloc[0] == 5000


# --- Testes para ler_kml ---


def test_ler_kml_sucesso(mocker):
	"""
	Testa a leitura bem-sucedida de um KML com múltiplas camadas usando mocks.
	"""
	# 1. Prepara os mocks
	# Mock para list_layers: simula um KML com duas camadas
	mock_list_layers = mocker.patch("core.data_loader.list_layers", return_value=[("Camada de Pontos", "Point"), ("Camada de Poligonos", "Polygon")])

	# Mock para gpd.read_file: retorna um GDF diferente para cada camada
	gdf_pontos = gpd.GeoDataFrame({"nome": ["Ponto 1"]}, geometry=[Point(1, 1)], crs=CRS_GEO)
	gdf_poligonos = gpd.GeoDataFrame({"nome": ["Area 1"]}, geometry=[Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])], crs=CRS_GEO)

	def read_file_side_effect(*args, **kwargs):
		if kwargs.get("layer") == "Camada de Pontos":
			return gdf_pontos
		if kwargs.get("layer") == "Camada de Poligonos":
			return gdf_poligonos
		return gpd.GeoDataFrame()

	mock_read_file = mocker.patch("core.data_loader.gpd.read_file", side_effect=read_file_side_effect)

	# 2. Executa a função
	resultado_gdf = ler_kml("caminho/falso/para/arquivo.kml", target_crs=CRS_PROJETADO)

	# 3. Verifica os resultados
	assert mock_list_layers.call_count == 1
	assert mock_read_file.call_count == 2
	assert len(resultado_gdf) == 2
	assert "camada" in resultado_gdf.columns
	assert resultado_gdf.crs.to_string() == CRS_PROJETADO
	assert "Camada de Pontos" in resultado_gdf["camada"].values


def test_ler_kml_sem_camadas(mocker):
	"""
	Testa o comportamento da função quando o KML não tem camadas.
	"""
	# Mock para list_layers retornando uma lista vazia
	mocker.patch("core.data_loader.list_layers", return_value=[])
	mock_print = mocker.patch("builtins.print")

	resultado_gdf = ler_kml("caminho/falso/para/vazio.kml", target_crs=CRS_PROJETADO)

	# A função deve capturar a exceção e retornar um GDF vazio
	assert isinstance(resultado_gdf, gpd.GeoDataFrame)
	assert resultado_gdf.empty
	# Verifica se a mensagem de erro foi impressa
	mock_print.assert_called_once()
	assert "Nenhuma camada encontrada no arquivo KML" in mock_print.call_args[0][0]


def test_ler_kml_erro_na_leitura(mocker):
	"""
	Testa o tratamento de erro se gpd.read_file falhar.
	"""
	mocker.patch("core.data_loader.list_layers", return_value=[("Camada 1", "Point")])
	# Força gpd.read_file a levantar uma exceção
	mocker.patch("core.data_loader.gpd.read_file", side_effect=Exception("Erro de leitura genérico"))
	mock_print = mocker.patch("builtins.print")

	resultado_gdf = ler_kml("caminho/falso/para/corrompido.kml", target_crs=CRS_PROJETADO)

	assert resultado_gdf.empty
	mock_print.assert_called_once()
	assert "Erro ao processar KML: Erro de leitura genérico" in mock_print.call_args[0][0]
