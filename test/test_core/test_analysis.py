# test_processamento_geo.py

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

# Importe as funções do seu módulo
# Assumindo que seu arquivo se chama 'processamento_geo.py'
from core.analysis import (
	agregar_renda_por_bairro,
	associar_ibge_bairros,
	calcular_densidade_populacional,
	calcular_fluxos_od,
	filtrar_setores_por_municipio,
	identificar_polos,
	vincular_setores_com_renda,
)

# --- CONSTANTES E CONFIGURAÇÕES DE TESTE ---

# Definição exata da constante COLUNAS que seu código usa
COLUNAS_PARA_TESTE = {
	"V06001": "num_de_responsaveis",
	"V06002": "num_de_moradores",
	"V06003": "variancia_do_num_de_morador",
	"V06004": "renda_mensal_media",
	"V06005": "variancia_de_renda",
}

CRS_GEO = "EPSG:4326"  # WGS 84
CRS_PROJETADO = 31983  # SIRGAS 2000 / UTM zone 23S (Comum no Brasil)

# --- DADOS DE TESTE (FIXTURES) ---


@pytest.fixture
def mock_setores_gdf():
	"""Cria um GeoDataFrame de setores censitários para teste."""
	data = {
		"CD_SETOR": ["111", "222", "333"],
		"NM_MUN": ["SAO PAULO", "SAO PAULO", "RIO DE JANEIRO"],
		"NM_UF": ["SP", "SP", "RJ"],
		# Usando as chaves corretas de COLUNAS
		"V06002": ["100", "150", "120"],  # num_de_moradores
		"V06004": ["1.500,50", "2.000,00", "1.800,75"],  # renda_mensal_media
		# Adicionando uma coluna que não está em COLUNAS para testar a robustez
		"DADO_EXTRA": ["A", "B", "C"],
	}
	geometry = [
		Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
		Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]),
		Polygon([(10, 10), (11, 10), (11, 11), (10, 11)]),
	]
	return gpd.GeoDataFrame(data, geometry=geometry, crs=CRS_GEO)


@pytest.fixture
def mock_renda_df():
	"""Cria um DataFrame de renda para teste."""
	data = {"CD_SETOR": ["111", "333", "444"], "outra_info_renda": [10, 20, 30]}
	return pd.DataFrame(data)


@pytest.fixture
def mock_bairros_gdf():
	"""Cria um GeoDataFrame de bairros para teste."""
	data = {"nome_bairro": ["Bairro A", "Bairro B"]}
	# Bairro A contém o centroide do setor '111' (0.5, 0.5)
	geometry = [Polygon([(-1, -1), (1.5, -1), (1.5, 1.5), (-1, 1.5)]), Polygon([(5, 5), (6, 5), (6, 6), (5, 6)])]
	return gpd.GeoDataFrame(data, geometry=geometry, crs=CRS_GEO)


@pytest.fixture
def mock_origem_destino_gdfs():
	"""Cria GeoDataFrames de pontos de origem e destino."""
	origens_data = {"geometry": [Point(0.1, 0.1), Point(0.2, 0.2)]}
	destinos_data = {"geometry": [Point(0.3, 0.3), Point(5.5, 5.5)]}
	origem_gdf = gpd.GeoDataFrame(origens_data, crs=CRS_GEO)
	destino_gdf = gpd.GeoDataFrame(destinos_data, crs=CRS_GEO)
	return origem_gdf, destino_gdf


# --- TESTES PARA CADA FUNÇÃO ---


def test_filtrar_setores_por_municipio(mock_setores_gdf):
	"""Testa se o filtro por município e UF funciona corretamente."""
	resultado = filtrar_setores_por_municipio(mock_setores_gdf, "Sao Paulo", "SP")
	assert isinstance(resultado, gpd.GeoDataFrame)
	assert len(resultado) == 2
	assert all(resultado["NM_MUN"] == "SAO PAULO")


def test_vincular_setores_com_renda(mock_setores_gdf, mock_renda_df):
	"""Testa a junção (merge) dos dados de renda com os setores."""
	setores_filtrados = mock_setores_gdf[mock_setores_gdf["NM_MUN"] == "SAO PAULO"]
	resultado = vincular_setores_com_renda(setores_filtrados, mock_renda_df)
	assert isinstance(resultado, gpd.GeoDataFrame)
	assert "outra_info_renda" in resultado.columns
	assert pd.isna(resultado[resultado["CD_SETOR"] == "222"]["outra_info_renda"].iloc[0])


def test_associar_ibge_bairros(mocker, mock_bairros_gdf, mock_setores_gdf):
	"""
	Testa a associação espacial e a limpeza/conversão de colunas.
	"""
	# Usa mocker para garantir que a função use a nossa constante de teste
	mocker.patch("utils.constants.COLUNAS", COLUNAS_PARA_TESTE)

	setores_com_renda = mock_setores_gdf.copy()
	resultado = associar_ibge_bairros(mock_bairros_gdf, setores_com_renda, CRS_PROJETADO)

	assert isinstance(resultado, gpd.GeoDataFrame)
	# Apenas o setor '111' (centroide em 0.5, 0.5) deve estar dentro do Bairro A
	assert len(resultado) == 1
	assert resultado["CD_SETOR"].iloc[0] == "111"

	# Verifica se as colunas foram renomeadas e convertidas corretamente
	assert "renda_mensal_media" in resultado.columns
	assert "num_de_moradores" in resultado.columns
	assert resultado["renda_mensal_media"].iloc[0] == 1500.50
	assert resultado["num_de_moradores"].iloc[0] == 100

	# Verifica se as colunas que não estavam em COLUNAS foram criadas com valor 0
	assert "num_de_responsaveis" in resultado.columns
	assert resultado["num_de_responsaveis"].iloc[0] == 0


def test_agregar_renda_por_bairro(mocker, mock_bairros_gdf, mock_setores_gdf):
	"""Testa a agregação (soma) de renda e população por bairro."""
	mocker.patch("utils.constants.COLUNAS", COLUNAS_PARA_TESTE)

	setores_sp = filtrar_setores_por_municipio(mock_setores_gdf, "SAO PAULO", "SP")

	# Modificar a geometria do Bairro A para conter os dois centroides de SP
	bairros_modificado = mock_bairros_gdf.copy()
	bairros_modificado.loc[0, "geometry"] = Polygon([(-1, -1), (3, -1), (3, 3), (-1, 3)])

	resultado = agregar_renda_por_bairro(bairros_modificado, setores_sp, CRS_PROJETADO)

	bairro_a = resultado[resultado["nome_bairro"] == "Bairro A"].iloc[0]
	bairro_b = resultado[resultado["nome_bairro"] == "Bairro B"].iloc[0]

	# Bairro A: soma dos setores '111' e '222'
	assert bairro_a["populacao_total_bairro"] == 100 + 150
	assert bairro_a["renda_total_bairro"] == pytest.approx(1500.50 + 2000.00)

	# Bairro B: não contém setores, deve ser zero
	assert bairro_b["populacao_total_bairro"] == 0
	assert bairro_b["renda_total_bairro"] == 0
	assert bairro_b["renda_total_bairro"] == 0


def test_calcular_fluxos_od(mock_bairros_gdf, mock_origem_destino_gdfs):
	"""Testa a contagem de pontos de origem e destino por bairro."""
	origem_gdf, destino_gdf = mock_origem_destino_gdfs
	resultado = calcular_fluxos_od(mock_bairros_gdf, origem_gdf, destino_gdf)

	bairro_a = resultado[resultado["nome_bairro"] == "Bairro A"].iloc[0]
	bairro_b = resultado[resultado["nome_bairro"] == "Bairro B"].iloc[0]

	assert bairro_a["n_origens"] == 2
	assert bairro_a["n_destinos"] == 1
	assert bairro_a["fluxo_total"] == 3
	assert bairro_b["n_origens"] == 0
	assert bairro_b["n_destinos"] == 1
	assert bairro_b["fluxo_total"] == 1


def test_calcular_densidade_populacional(mock_bairros_gdf):
	"""Testa o cálculo da densidade populacional."""
	bairros_com_pop = mock_bairros_gdf.copy()
	bairros_com_pop["populacao_total_bairro"] = [1000, 500]

	resultado = calcular_densidade_populacional(bairros_com_pop, CRS_PROJETADO)

	assert "area_km2" in resultado.columns
	assert "densidade_km2" in resultado.columns
	bairro_a = resultado[resultado["nome_bairro"] == "Bairro A"].iloc[0]
	assert bairro_a["densidade_km2"] == pytest.approx(bairro_a["populacao_total_bairro"] / bairro_a["area_km2"])
	assert resultado.crs == mock_bairros_gdf.crs


def test_identificar_polos():
	"""Testa a classificação de bairros em polos de desenvolvimento."""
	data_teste = {
		"nome": ["Consolidado", "Emergente", "Nenhum_Rico", "Nenhum_Fluxo_Baixo"],
		"densidade_km2": [1000, 1000, 100, 1000],  # Alta, Alta, Baixa, Alta
		"renda_total_bairro": [100, 100, 900, 100],  # Baixa, Baixa, Alta, Baixa
		"fluxo_total": [1000, 100, 100, 100],  # Alto, Baixo, Baixo, Baixo
	}
	bairros_teste_gdf = gpd.GeoDataFrame(data_teste, geometry=[Point(i, i) for i in range(4)])

	resultado = identificar_polos(bairros_teste_gdf, densidade_limiar=0.5, renda_limiar=0.5, fluxo_limiar=0.5)

	assert resultado.loc[0, "tipo_polo"] == "Consolidado"
	assert resultado.loc[1, "tipo_polo"] == "Emergente"
	assert resultado.loc[3, "tipo_polo"] == "Emergente"

	# Verifica que a linha 2 não foi classificada
	assert "tipo_polo" not in resultado.loc[2].keys() or pd.isna(resultado.loc[2, "tipo_polo"])
