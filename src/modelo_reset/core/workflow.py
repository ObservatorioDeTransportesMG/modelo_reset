import os
from typing import Any, Optional

import geopandas as gpd
import networkx as nx

from ..utils import columns, constants
from . import analysis, data_exporter, data_loader, network_design, visualization
from .ibge_downloader import baixar_dados_censo_renda, baixar_malha_municipal


class ModeloReset:
	"""
	Orquestra o fluxo de trabalho completo para análise geoespacial, desde o carregamento de dados até a visualização de resultados.
	"""

	def __init__(self, crs_projetado: str = constants.CRS_PROJETADO):
		"""Inicializa o workflow, definindo os sistemas de coordenadas e o contêiner de camadas.

		Args:
			crs_projetado (str, optional): O CRS projetado a ser usado para cálculos de área e distância. Padrão é "EPSG:31983".
		"""
		self.camadas: dict[str, Any] = {}
		self.camadas[columns.CAMADA_BAIRRO] = None
		self.crs_padrao: str = "EPSG:4326"
		self.crs_projetado: str = crs_projetado
		self.grafo: Optional[nx.MultiDiGraph] = None

	def carregar_dados_base(self, path_bairros: Optional[str] = None, epsg_bairros: Optional[str] = None):
		"""Carrega as camadas de dados geográficos base (bairros e residências).

		Args:
			path_bairros (str): Caminho para o shapefile dos bairros.
			path_residencias (str): Caminho para o CSV das residências.
			epsg_bairros (str): Código EPSG original do shapefile de bairros, caso não esteja definido no arquivo.
		"""
		if path_bairros:
			if not epsg_bairros:
				raise ValueError("Para realizar o carregamento dos dados base é preciso passar o paramêtro 'epgs_bairros'.")
			self.camadas[columns.CAMADA_BAIRRO] = data_loader.ler_shapefile(path_bairros, self.crs_padrao, epsg_bairros)
			self.camadas[columns.CAMADA_BAIRRO] = self.camadas[columns.CAMADA_BAIRRO].rename(
				columns={columns.NOME_BAIRRO_SHAPEFILE: columns.NOME_BAIRRO}
			)

	def carregar_dados_ibge(self, ano_censo: int, uf: str = "MG"):
		"""Carrega os dados do IBGE (setores censitários e dados de renda).

		Args:
			ano_malha (int): O ano da malha territorial do IBGE (ex: 2024).
			ano_censo (int): O ano do censo do IBGE (ex: 2022).
			uf (str): A sigla do estado em maiúsculas (ex: "SP", "MG").
		"""
		path_setores = baixar_malha_municipal(
			diretorio_saida=os.path.join((os.path.expanduser("~")), "modelo_reset_data", "malha"), uf=uf, ano=ano_censo
		)
		path_renda = baixar_dados_censo_renda(diretorio_saida=os.path.join((os.path.expanduser("~")), "modelo_reset_data"), ano=ano_censo)

		if path_setores is None or path_renda is None:
			raise Exception("Erro ao baixar dados do IBGE.")

		gdf_setores = data_loader.ler_shapefile(path_setores, self.crs_padrao)
		self.camadas[columns.CAMADA_SETORES] = gdf_setores.copy()
		self.camadas[columns.CAMADA_RENDA] = data_loader.ler_renda_csv(path_renda, separador=";")
		gdf_bairros_atual = self.camadas.get(columns.CAMADA_BAIRRO)

		if gdf_bairros_atual is None or gdf_bairros_atual.empty:
			self.camadas[columns.CAMADA_BAIRRO] = gdf_setores.copy()

	def carregar_rede_viaria(self, path_vias: str, epsg_vias: str = constants.CRS_GEOGRAFICO):
		"""Carrega a camada de dados da rede viária (ruas).

		Args:
			path_vias (str): Caminho para o shapefile das vias.
			epsg_vias (int): Código EPSG original, se não estiver no .prj.
		"""
		self.camadas[columns.CAMADA_VIAS] = data_loader.ler_shapefile(path_vias, self.crs_padrao, epsg_vias)

	def _processar_renda_ibge(self, municipio: str):
		"""Filtra, vincula e agrega dados de renda e população por bairro.

		Args:
			municipio (str): Nome do município para filtrar os setores censitários.
			uf (str): Sigla do estado (UF) para filtrar os setores.
		"""
		setores_filtrados = analysis.filtrar_setores_por_municipio(self.camadas[columns.CAMADA_SETORES], municipio)
		if self.camadas.get(columns.CAMADA_BAIRRO, None) is None:
			self.camadas[columns.CAMADA_BAIRRO] = setores_filtrados.copy()
		self.camadas[columns.CAMADA_BAIRRO][columns.POLO] = "Nenhum"
		setores_com_renda = analysis.vincular_setores_com_renda(setores_filtrados, self.camadas[columns.CAMADA_RENDA])
		bairros_com_renda = analysis.agregar_renda_por_bairro(self.camadas[columns.CAMADA_BAIRRO], setores_com_renda, self.crs_projetado)
		self.camadas[columns.CAMADA_BAIRRO] = bairros_com_renda
		self.camadas[columns.CAMADA_SETORES] = setores_com_renda

	def _processar_densidade(self):
		"""Calcula a densidade populacional para a camada de bairros."""
		self.camadas[columns.CAMADA_BAIRRO] = analysis.calcular_densidade_populacional(self.camadas[columns.CAMADA_BAIRRO], self.crs_projetado)

	def processar_dados(self, municipio: str):
		"""Função responsável por processar todos os dados necessários."""
		self._processar_renda_ibge(municipio)
		self._processar_densidade()

	def carregar_e_processar_od(self, path_od: str):
		"""Carrega dados de Origem-Destino e calcula os fluxos por bairro.

		Args:
			path_od (str): Caminho para o arquivo CSV de Origem-Destino.
		"""
		df_od = data_loader.ler_od_csv(path_od)

		geom_origem = gpd.points_from_xy(df_od["longitude_origem"], df_od["latitude_origem"])
		origem_gdf = gpd.GeoDataFrame(df_od, geometry=geom_origem, crs=self.crs_padrao)

		geom_destino = gpd.points_from_xy(df_od["longitude_destino"], df_od["latitude_destino"])
		destino_gdf = gpd.GeoDataFrame(df_od, geometry=geom_destino, crs=self.crs_padrao)

		self.camadas[columns.CAMADA_BAIRRO] = analysis.calcular_fluxos_od(self.camadas[columns.CAMADA_BAIRRO], origem_gdf, destino_gdf)

	def identificar_polos_planejados(self, *polos_planejados: str):
		"""Define polos planejados e identifica polos emergentes e consolidados.

		Args:
			*polos_planejados (str): Nomes dos bairros a serem classificados como "Planejado".
		"""
		self.set_polos_planejados(*polos_planejados)
		self.camadas[columns.CAMADA_BAIRRO] = analysis.identificar_polos(self.camadas[columns.CAMADA_BAIRRO])

	def identificar_polos(self):
		"""Define polos planejados e identifica polos emergentes e consolidados.

		Args:
			*polos_planejados (str): Nomes dos bairros a serem classificados como "Planejado".
		"""
		self.camadas[columns.CAMADA_BAIRRO] = analysis.identificar_polos(self.camadas[columns.CAMADA_BAIRRO])

	def carregar_pontos_articulacao(self, path_pontos: str):
		"""Carrega a camada de pontos de articulação a partir de um arquivo KML.

		Args:
			path_pontos (str): Caminho para o arquivo KML dos pontos de articulação.
		"""
		self.camadas[columns.CAMADA_PONTOS_ARTICULACO] = data_loader.ler_kml(path_pontos, self.crs_padrao)

	def _projetar_camadas_para_analise(self):
		"""
		Garante que todas as camadas de análise estejam projetadas no CRS métrico.
		"""
		# target_crs = f"EPSG:{self.crs_projetado}"

		camadas_para_projetar = ["bairros", "vias", "pontos_articulacao"]

		for nome_camada in camadas_para_projetar:
			if nome_camada in self.camadas:
				if self.camadas[nome_camada].crs != self.crs_projetado:
					self.camadas[nome_camada] = self.camadas[nome_camada].to_crs(self.crs_projetado)
				else:
					self.camadas[nome_camada] = self.camadas[nome_camada]
			else:
				continue

	def set_polos_planejados(self, *args: str):
		"""Define manualmente quais bairros são classificados como "Planejado".

		Args:
			*args (str): Uma sequência de nomes de bairros a serem definidos como "Planejado".
		"""
		bairros = self.camadas.get(columns.CAMADA_BAIRRO, gpd.GeoDataFrame())
		if bairros.empty:
			return

		bairros[columns.POLO] = "Nenhum"
		for polo in args:
			bairros.loc[bairros[columns.NOME_BAIRRO].isin([polo]), columns.POLO] = "Planejado"

	def _montar_grafo(self):
		camadas_necessarias = ["bairros", "vias", "pontos_articulacao"]
		if not all(k in self.camadas for k in camadas_necessarias):
			raise ValueError("Camadas 'bairros', 'vias' e 'pontos_articulacao' são necessárias. Carregue-as primeiro.")

		self._projetar_camadas_para_analise()

		bairros_proj = self.camadas[columns.CAMADA_BAIRRO]
		vias_proj = self.camadas[columns.CAMADA_VIAS]
		pontos_art_proj = self.camadas[columns.CAMADA_PONTOS_ARTICULACO]

		vias_filtradas = network_design.filtrar_vias_por_bairros(vias_proj, bairros_proj)
		self.camadas[columns.CAMADA_VIAS_FILTRADA] = vias_filtradas

		self.grafo = network_design.criar_grafo_ponderado(vias_filtradas, pontos_art_proj, bairros_proj)

	def gerar_rotas_otimizadas(self, bairro_central: Optional[str] = None):
		"""
		Orquestra todo o processo de análise de rede.

		1. Projeta as camadas.
		2. Filtra as vias.
		3. Gera o grafo ponderado.
		4. Calcula os caminhos de ida e volta.
		"""
		# 1. Garantir que as camadas estão prontas e projetadas

		self._montar_grafo()
		bairros_proj = self.camadas[columns.CAMADA_BAIRRO]

		if not self.grafo:
			raise Exception("Falha ao criar o grafo.")

		# 4. Calcular caminhos
		self.camadas[columns.CAMADA_CAMINHO_VOLTA] = network_design.encontrar_caminho_minimo(
			bairros_proj, self.grafo, bairro_central=bairro_central, sentido="VOLTA"
		)

		self.camadas[columns.CAMADA_CAMINHO_IDA] = network_design.encontrar_caminho_minimo(
			bairros_proj, self.grafo, bairro_central=bairro_central, sentido="IDA"
		)

		self.camadas[columns.CAMADA_ROTAS_CONCATENADAS] = gpd.pd.concat([
			self.camadas[columns.CAMADA_CAMINHO_VOLTA],
			self.camadas[columns.CAMADA_CAMINHO_IDA],
		])

	def mostrar_centroids(self):
		"""Plota os bairros e os centroides dos setores censitários associados."""
		setores = self.camadas[columns.CAMADA_SETORES].copy()
		crs_original = setores.crs

		setores_projetado = setores.to_crs(epsg=self.crs_projetado)

		centroides_projetados = setores_projetado.geometry.centroid

		setores["geometry"] = centroides_projetados.to_crs(crs_original)
		setores_associados = gpd.sjoin(setores, self.camadas[columns.CAMADA_BAIRRO], how="left", predicate="within")
		setores_associados = setores_associados[setores_associados["index_right"].notnull()]

		visualization.plotar_centroid_e_bairros(self.camadas[columns.CAMADA_BAIRRO], setores_associados, self.crs_projetado)

	def plotar_densidade(self):
		"""Gera e exibe um mapa coroplético da densidade populacional dos bairros."""
		visualization.plotar_mapa_coropletico(
			self.camadas[columns.CAMADA_BAIRRO], self.crs_projetado, columns.DENSIDADE, "Densidade Populacional (hab/km²)", "OrRd"
		)

	def plotar_renda_media(self):
		"""Gera e exibe um mapa coroplético da renda média dos bairros."""
		visualization.plotar_mapa_coropletico(
			self.camadas[columns.CAMADA_BAIRRO], self.crs_projetado, columns.RENDA, "Renda Média por Bairro", "YlGn"
		)

	def mostrar_rotas_otimizadas(self):
		"""
		Exibe o mapa final com as rotas de ida e volta otimizadas.
		"""
		camadas_necessarias = ["vias_filtradas", "bairros", "caminhos_ida", "caminhos_volta"]
		if not all(k in self.camadas for k in camadas_necessarias):
			return

		visualization.plotar_caminhos(
			self.camadas[columns.CAMADA_VIAS_FILTRADA],
			self.camadas[columns.CAMADA_BAIRRO],
			self.camadas[columns.CAMADA_CAMINHO_IDA],
			self.camadas[columns.CAMADA_CAMINHO_VOLTA],
		)

	def mostrar_polos(self):
		"""Gera e exibe um mapa dos polos de desenvolvimento."""
		visualization.plotar_polos(self.camadas[columns.CAMADA_BAIRRO], self.crs_projetado)

	def mostrar_modelo_completo(self):
		"""Gera e exibe o mapa final com polos e pontos de articulação."""
		visualization.plotar_modelo_completo(
			self.camadas[columns.CAMADA_BAIRRO], self.camadas.get(columns.CAMADA_PONTOS_ARTICULACO, gpd.GeoDataFrame()), self.crs_projetado
		)

	def exportar_resultados(self, pasta_saida: str = "resultados"):
		"""
		Exporta as camadas processadas para arquivos físicos.
		"""
		if "rotas_concatenadas" in self.camadas:
			data_exporter.exportar_geodataframe(
				self.camadas[columns.CAMADA_ROTAS_CONCATENADAS], caminho_saida=f"{pasta_saida}/rotas_finais.geojson", formato="geojson"
			)

		if "bairros" in self.camadas:
			data_exporter.exportar_geodataframe(
				self.camadas[columns.CAMADA_BAIRRO],
				caminho_saida=f"{pasta_saida}/bairros_analisados.shp",
				formato="shapefile",
				crs_saida=self.crs_projetado,
			)

	@property
	def bairros(self) -> list[str]:
		"""Retorna a lista de nomes dos bairros carregados."""
		gdf_bairros = self.camadas.get(columns.CAMADA_BAIRRO)

		if gdf_bairros is None or columns.NOME_BAIRRO not in gdf_bairros.columns:
			return []

		gdf_filtrado = gdf_bairros[gdf_bairros[columns.NOME_BAIRRO].notnull()]
		gdf_filtrado[columns.NOME_BAIRRO] = gdf_bairros[columns.NOME_BAIRRO].astype(str)
		return sorted(gdf_filtrado[columns.NOME_BAIRRO].unique())
