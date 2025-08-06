from unittest.mock import MagicMock

import geopandas as gpd
import pandas as pd
import pytest

from core.workflow import ModeloReset


@pytest.fixture
def mock_modulos(mocker):
	"""Fixture que mocka os módulos inteiros de dependência."""
	mock_data_loader = mocker.patch("core.workflow.data_loader")
	mock_analysis = mocker.patch("core.workflow.analysis")
	mock_visualization = mocker.patch("core.workflow.visualization")
	return mock_data_loader, mock_analysis, mock_visualization


@pytest.fixture
def gdf_fake():
	"""Retorna um GeoDataFrame genérico para usar como retorno dos mocks."""
	return gpd.GeoDataFrame({"geometry": []})


class TestModeloReset:
	def test_init(self):
		"""Testa a inicialização da classe."""
		modelo = ModeloReset(crs_projetado=31983)
		assert isinstance(modelo.camadas, dict)
		assert len(modelo.camadas) == 0
		assert modelo.crs_padrao == "EPSG:4326"
		assert modelo.crs_projetado == 31983

	def test_carregar_dados_base(self, mock_modulos, gdf_fake):
		"""Verifica se o carregamento de dados base chama o data_loader corretamente."""
		mock_data_loader, _, _ = mock_modulos
		mock_data_loader.ler_shapefile.return_value = gdf_fake

		modelo = ModeloReset()
		modelo.carregar_dados_base(path_bairros="/path/bairros.shp", epsg_bairros=4674)

		mock_data_loader.ler_shapefile.assert_called_once_with("/path/bairros.shp", "EPSG:4326", 4674)
		assert "bairros" in modelo.camadas
		assert modelo.camadas["bairros"] is gdf_fake

	def test_carregar_dados_ibge(self, mock_modulos, gdf_fake):
		"""Verifica se o carregamento de dados do IBGE chama o data_loader."""
		mock_data_loader, _, _ = mock_modulos
		df_fake = pd.DataFrame()
		mock_data_loader.ler_shapefile.return_value = gdf_fake
		mock_data_loader.ler_renda_csv.return_value = df_fake

		modelo = ModeloReset()
		modelo.carregar_dados_ibge(path_setores="/path/setores.shp", path_renda="/path/renda.csv")

		mock_data_loader.ler_shapefile.assert_called_once_with("/path/setores.shp", "EPSG:4326")
		mock_data_loader.ler_renda_csv.assert_called_once_with("/path/renda.csv")
		assert modelo.camadas["setores_censitarios"] is gdf_fake
		assert modelo.camadas["dados_de_renda"] is df_fake

	def test_processar_renda_ibge(self, mock_modulos, gdf_fake):
		"""
		Testa a orquestração do processamento de renda, verificando a cadeia de chamadas.
		"""
		_, mock_analysis, _ = mock_modulos

		# Simula o retorno de cada etapa da análise
		gdf_filtrado = gpd.GeoDataFrame({"filtro": [1]})
		gdf_com_renda = gpd.GeoDataFrame({"renda": [2]})
		gdf_final_bairros = gpd.GeoDataFrame({"agregado": [3]})

		mock_analysis.filtrar_setores_por_municipio.return_value = gdf_filtrado
		mock_analysis.vincular_setores_com_renda.return_value = gdf_com_renda
		mock_analysis.agregar_renda_por_bairro.return_value = gdf_final_bairros

		# Prepara o estado inicial do modelo
		modelo = ModeloReset()
		modelo.camadas["setores_censitarios"] = gdf_fake
		modelo.camadas["dados_de_renda"] = pd.DataFrame()
		modelo.camadas["bairros"] = gdf_fake

		# Executa o método
		modelo.processar_renda_ibge(municipio="Teste", uf="TS")

		# Verifica a cadeia de chamadas
		mock_analysis.filtrar_setores_por_municipio.assert_called_once_with(gdf_fake, "Teste", "TS")
		mock_analysis.vincular_setores_com_renda.assert_called_once_with(gdf_filtrado, modelo.camadas["dados_de_renda"])
		mock_analysis.agregar_renda_por_bairro.assert_called_once_with(gdf_fake, gdf_com_renda, modelo.crs_projetado)

		# Verifica se o estado foi atualizado corretamente
		assert modelo.camadas["bairros"] is gdf_final_bairros
		assert modelo.camadas["setores"] is gdf_com_renda

	def test_identificar_polos_desenvolvimento(self, mock_modulos, gdf_fake):
		"""Testa se a identificação de polos chama a análise e o set_polos."""
		_, mock_analysis, _ = mock_modulos
		mock_analysis.identificar_polos.return_value = gdf_fake

		modelo = ModeloReset()
		# Mock para o método interno da própria classe
		modelo.set_polos_planejados = MagicMock()
		modelo.camadas["bairros"] = gdf_fake

		modelo.identificar_polos_desenvolvimento("Bairro Planejado 1", "Bairro Planejado 2")

		modelo.set_polos_planejados.assert_called_once_with("Bairro Planejado 1", "Bairro Planejado 2")
		mock_analysis.identificar_polos.assert_called_once_with(gdf_fake)
		assert modelo.camadas["bairros"] is gdf_fake

	def test_set_polos_planejados(self):
		"""Testa a lógica interna de definir polos planejados."""
		modelo = ModeloReset()
		bairros_df = gpd.GeoDataFrame({"name": ["Bairro A", "Bairro B", "Bairro C"], "geometry": [None, None, None]})
		modelo.camadas["bairros"] = bairros_df

		modelo.set_polos_planejados("Bairro B")

		tipos_esperados = ["Nenhum", "Planejado", "Nenhum"]
		assert list(modelo.camadas["bairros"]["tipo_polo"]) == tipos_esperados

	def test_plotar_densidade(self, mock_modulos, gdf_fake):
		"""Verifica se o método de plotagem de densidade chama a visualização."""
		_, _, mock_visualization = mock_modulos

		modelo = ModeloReset()
		modelo.camadas["bairros"] = gdf_fake

		modelo.plotar_densidade()

		mock_visualization.plotar_mapa_coropletico.assert_called_once_with(gdf_fake, "densidade_km2", "Densidade Populacional (hab/km²)", "OrRd")

	def test_mostrar_polos(self, mock_modulos, gdf_fake):
		"""Verifica se o método de mostrar polos chama a visualização."""
		_, _, mock_visualization = mock_modulos

		modelo = ModeloReset()
		modelo.camadas["bairros"] = gdf_fake

		modelo.mostrar_polos()

		mock_visualization.plotar_polos.assert_called_once_with(gdf_fake)
