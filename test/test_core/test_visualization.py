# test/test_core/test_visualization.py

from unittest.mock import ANY, MagicMock

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

# Importe as funções do seu módulo
from core.visualization import plotar_centroid_e_bairros, plotar_mapa_coropletico, plotar_modelo_completo, plotar_polos

# --- Fixtures: Dados de Teste ---


@pytest.fixture
def mock_gdf_para_plot():
	"""Cria um GeoDataFrame simples para testes de plotagem."""
	data = {"nome": ["A", "B"], "valores": [10.5, 25.2], "tipo_polo": ["Consolidado", "Emergente"]}
	geometry = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), Polygon([(1, 1), (2, 1), (2, 2), (1, 2)])]
	gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")
	# Adiciona um mock ao método plot para podermos espiar suas chamadas
	gdf.plot = MagicMock()
	return gdf


@pytest.fixture
def mock_pontos_gdf():
	"""Cria um GeoDataFrame de pontos para teste."""
	gdf = gpd.GeoDataFrame({"tipo": ["Ponto de Interesse"]}, geometry=[Point(0.5, 0.5)], crs="EPSG:4326")
	gdf.plot = MagicMock()
	return gdf


# --- Testes para cada Função de Plotagem ---


def test_plotar_mapa_coropletico(mocker, mock_gdf_para_plot):
	"""
	Testa se a função de mapa coroplético chama as funções do matplotlib corretamente.
	"""
	# 1. Mock do módulo pyplot para evitar que a janela do gráfico apareça
	mock_plt = mocker.patch("core.visualization.plt")

	# Extrai o mock do 'ax' retornado por subplots
	mock_fig, mock_ax = MagicMock(), MagicMock()
	mock_plt.subplots.return_value = (mock_fig, mock_ax)

	# 2. Executa a função a ser testada
	plotar_mapa_coropletico(mock_gdf_para_plot, coluna="valores", titulo="Meu Mapa Teste", cmap="plasma")

	# 3. Verifica se as funções de plotagem foram chamadas com os argumentos corretos
	mock_plt.subplots.assert_called_once_with(1, 1, figsize=(12, 10))

	# Verifica a chamada ao método .plot do GeoDataFrame
	mock_gdf_para_plot.plot.assert_called_once_with(column="valores", ax=mock_ax, legend=True, cmap="plasma", edgecolor="black", linewidth=0.4)

	# Verifica as chamadas aos métodos do eixo (ax) e do pyplot (plt)
	mock_ax.set_title.assert_called_once_with("Meu Mapa Teste", fontsize=16)
	mock_ax.set_axis_off.assert_called_once()
	mock_plt.tight_layout.assert_called_once()
	mock_plt.show.assert_called_once()  # Garante que o fluxo chegou ao fim


def test_plotar_polos(mocker, mock_gdf_para_plot):
	"""
	Testa a função de plotagem de polos, verificando o mapeamento de cores e a legenda.
	"""
	mock_plt = mocker.patch("core.visualization.plt")

	mock_fig, mock_ax = MagicMock(), MagicMock()
	mock_plt.subplots.return_value = (mock_fig, mock_ax)

	plotar_polos(mock_gdf_para_plot)

	# Verifica se o plot foi chamado. A verificação do argumento 'color' é mais complexa,
	# então aqui focamos que a chamada ocorreu.
	mock_gdf_para_plot.plot.assert_called_once()
	# Podemos inspecionar o argumento 'color' se necessário
	call_args, call_kwargs = mock_gdf_para_plot.plot.call_args
	assert "color" in call_kwargs
	assert all(call_kwargs["color"] == pd.Series(["green", "orange"]))  # Verifica se o map funcionou

	# Verifica se a legenda foi criada corretamente
	# Usamos ANY (do módulo unittest.mock) porque o conteúdo de 'handles' é complexo de recriar
	mock_ax.legend.assert_called_once_with(handles=ANY, title="Tipo de Polo", loc="lower right")

	mock_ax.set_title.assert_called_once_with("Polos de Desenvolvimento", fontsize=16)
	mock_plt.show.assert_called_once()


def test_plotar_polos_sem_coluna_necessaria(mocker):
	"""
	Testa o comportamento de 'plotar_polos' quando a coluna 'tipo_polo' não existe.
	"""
	# Cria um GDF sem a coluna 'tipo_polo'
	gdf_sem_polo = gpd.GeoDataFrame({"nome": ["A"]}, geometry=[Polygon([(0, 0), (1, 1), (1, 0)])])

	mock_plt = mocker.patch("core.visualization.plt")
	mock_print = mocker.patch("builtins.print")

	plotar_polos(gdf_sem_polo)

	# Verifica se a mensagem de aviso foi impressa
	mock_print.assert_called_once_with("Coluna 'tipo_polo' não encontrada. Execute a análise de polos primeiro.")

	# Garante que NENHUMA função de plotagem foi chamada
	mock_plt.subplots.assert_not_called()
	mock_plt.show.assert_not_called()


def test_plotar_centroid_e_bairros(mocker, mock_gdf_para_plot, mock_pontos_gdf):
	"""
	Testa a plotagem de duas camadas (polígonos e pontos).
	"""
	mock_plt = mocker.patch("core.visualization.plt")

	mock_fig, mock_ax = MagicMock(), MagicMock()
	mock_plt.subplots.return_value = (mock_fig, mock_ax)

	# A função original usa os GDFs reais, então vamos usar nossos mocks de plot
	plotar_centroid_e_bairros(mock_gdf_para_plot, mock_pontos_gdf)

	# Verifica a plotagem da camada de bairros
	mock_gdf_para_plot.plot.assert_called_once_with(ax=mock_ax, facecolor="lightgray", edgecolor="white", linewidth=0.5)

	# Verifica a plotagem da camada de centroides
	mock_pontos_gdf.plot.assert_called_once_with(ax=mock_ax, marker="o", color="red", markersize=20)

	mock_ax.legend.assert_called_once_with(handles=ANY, title="Legenda", loc="lower right")
	mock_ax.set_title.assert_called_once_with("Bairros e Setores Censitários", fontsize=16)
	mock_plt.show.assert_called_once()


def test_plotar_modelo_completo(mocker, mock_gdf_para_plot, mock_pontos_gdf):
	"""
	Testa a plotagem do modelo completo com polos e pontos.
	"""
	mock_plt = mocker.patch("core.visualization.plt")

	mock_fig, mock_ax = MagicMock(), MagicMock()
	mock_plt.subplots.return_value = (mock_fig, mock_ax)

	plotar_modelo_completo(mock_gdf_para_plot, mock_pontos_gdf)

	# Verifica a plotagem dos bairros (polos)
	mock_gdf_para_plot.plot.assert_called_once()
	assert "color" in mock_gdf_para_plot.plot.call_args.kwargs

	# Verifica a plotagem dos pontos de interesse
	mock_pontos_gdf.plot.assert_called_once_with(ax=mock_ax, marker="o", color="red", markersize=50, label="Pontos de Articulação")

	mock_ax.legend.assert_called_once_with(handles=ANY, title="Tipo de Polo", loc="lower right")
	mock_ax.set_title.assert_called_once_with("Modelo Completo: Polos e Pontos de Articulação", fontsize=16)
	mock_plt.show.assert_called_once()
