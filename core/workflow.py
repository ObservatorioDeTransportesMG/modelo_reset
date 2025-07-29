from typing import Any

import geopandas as gpd

from . import analysis, data_loader, visualization


class ModeloResetWorkflow:
	"""
	Orquestra o fluxo de trabalho completo para análise geoespacial, desde o
	carregamento de dados até a visualização de resultados.
	"""

	def __init__(self, crs_projetado: str = "EPSG:31983"):
		"""Inicializa o workflow, definindo os sistemas de coordenadas e o contêiner de camadas.

		Args:
			crs_projetado (str, optional): O CRS projetado a ser usado para
				cálculos de área e distância. Padrão é "EPSG:31983".

		Returns:
			None
		"""
		self.camadas: dict[str, Any] = {}
		self.crs_padrao: str = "EPSG:4326"
		self.crs_projetado: str = crs_projetado

	def carregar_dados_base(self, path_bairros: str, path_residencias: str, epsg_bairros: int):
		"""Carrega as camadas de dados geográficos base (bairros e residências).

		Args:
			path_bairros (str): Caminho para o shapefile dos bairros.
			path_residencias (str): Caminho para o CSV das residências.
			epsg_bairros (int): Código EPSG original do shapefile de bairros,
				caso não esteja definido no arquivo.

		Returns:
			None
		"""
		print("Carregando dados de base...")
		self.camadas["bairros"] = data_loader.ler_shapefile(path_bairros, self.crs_padrao, epsg_bairros)
		self.camadas["residencias"] = data_loader.ler_residencias_csv(path_residencias, self.crs_padrao)
		print("Dados de base carregados.")

	def carregar_dados_ibge(self, path_setores: str, path_renda: str):
		"""Carrega os dados do IBGE (setores censitários e dados de renda).

		Args:
			path_setores (str): Caminho para o shapefile dos setores censitários.
			path_renda (str): Caminho para o CSV com os dados de renda.

		Returns:
			None
		"""
		print("Carregando dados do IBGE...")
		self.camadas["setores_censitarios"] = data_loader.ler_shapefile(path_setores, self.crs_padrao)
		self.camadas["dados_de_renda"] = data_loader.ler_renda_csv(path_renda)
		print("Dados do IBGE carregados.")

	def processar_renda_ibge(self, municipio: str, uf: str):
		"""Filtra, vincula e agrega dados de renda e população por bairro.

		Args:
			municipio (str): Nome do município para filtrar os setores censitários.
			uf (str): Sigla do estado (UF) para filtrar os setores.

		Returns:
			None
		"""
		print("Processando e vinculando dados de renda...")
		setores_filtrados = analysis.filtrar_setores_por_municipio(self.camadas["setores_censitarios"], municipio, uf)
		setores_com_renda = analysis.vincular_setores_com_renda(setores_filtrados, self.camadas["dados_de_renda"])
		bairros_com_renda = analysis.agregar_renda_por_bairro(self.camadas["bairros"], setores_com_renda, self.crs_projetado)
		self.camadas["bairros"] = bairros_com_renda
		self.camadas["setores"] = setores_com_renda
		print("Processamento de renda finalizado.")

	def processar_densidade(self):
		"""Calcula a densidade populacional para a camada de bairros.

		Args:
			None

		Returns:
			None
		"""
		print("Calculando densidade populacional...")
		self.camadas["bairros"] = analysis.calcular_densidade_populacional(self.camadas["bairros"], self.crs_projetado)
		print("Cálculo de densidade finalizado.")

	def carregar_e_processar_od(self, path_od: str):
		"""Carrega dados de Origem-Destino e calcula os fluxos por bairro.

		Args:
			path_od (str): Caminho para o arquivo CSV de Origem-Destino.

		Returns:
			None
		"""
		print("Carregando e processando dados de O/D...")
		df_od = data_loader.ler_od_csv(path_od)

		geom_origem = gpd.points_from_xy(df_od["longitude_origem"], df_od["latitude_origem"])
		origem_gdf = gpd.GeoDataFrame(df_od, geometry=geom_origem, crs=self.crs_padrao)

		geom_destino = gpd.points_from_xy(df_od["longitude_destino"], df_od["latitude_destino"])
		destino_gdf = gpd.GeoDataFrame(df_od, geometry=geom_destino, crs=self.crs_padrao)

		self.camadas["bairros"] = analysis.calcular_fluxos_od(self.camadas["bairros"], origem_gdf, destino_gdf)
		print("Processamento de O/D finalizado.")

	def identificar_polos_desenvolvimento(self, *polos_planejados: str):
		"""Define polos planejados e identifica polos emergentes e consolidados.

		Args:
			*polos_planejados (str): Nomes dos bairros a serem classificados
				como "Planejado".

		Returns:
			None
		"""
		print("Identificando polos...")
		self.set_polos_planejados(*polos_planejados)
		self.camadas["bairros"] = analysis.identificar_polos(self.camadas["bairros"])

	def carregar_pontos_articulacao(self, path_pontos: str):
		"""Carrega a camada de pontos de articulação a partir de um arquivo KML.

		Args:
			path_pontos (str): Caminho para o arquivo KML dos pontos de articulação.

		Returns:
			None
		"""
		print("Carregando pontos de articulação...")
		self.camadas["pontos_articulacao"] = data_loader.ler_kml(path_pontos, self.crs_padrao)
		print(f"Carregados {len(self.camadas['pontos_articulacao'])} pontos.")

	def set_polos_planejados(self, *args: str):
		"""Define manualmente quais bairros são classificados como "Planejado".

		Args:
			*args (str): Uma sequência de nomes de bairros a serem definidos
				como "Planejado".

		Returns:
			None
		"""
		bairros = self.camadas.get("bairros", gpd.GeoDataFrame())
		if bairros.empty:
			return

		bairros["tipo_polo"] = "Nenhum"
		for polo in args:
			bairros.loc[bairros["name"].isin([polo]), "tipo_polo"] = "Planejado"

	def mostrar_centroids(self):
		"""Plota os bairros e os centroides dos setores censitários associados.

		Args:
			None

		Returns:
			None
		"""
		setores = self.camadas["setores"].copy()
		setores["geometry"] = setores.geometry.centroid
		setores_associados = gpd.sjoin(setores, self.camadas["bairros"], how="left", predicate="within")
		setores_associados = setores_associados[setores_associados["index_right"].notnull()]

		visualization.plotar_centroid_e_bairros(self.camadas["bairros"], setores_associados)

	def plotar_densidade(self):
		"""Gera e exibe um mapa coroplético da densidade populacional dos bairros.

		Args:
			None

		Returns:
			None
		"""
		visualization.plotar_mapa_coropletico(self.camadas["bairros"], "densidade_km2", "Densidade Populacional (hab/km²)", "OrRd")

	def plotar_renda_media(self):
		"""Gera e exibe um mapa coroplético da renda média dos bairros.

		Args:
			None

		Returns:
			None
		"""
		visualization.plotar_mapa_coropletico(self.camadas["bairros"], "renda_media_bairro", "Renda Média por Bairro", "YlGn")

	def mostrar_polos(self):
		"""Gera e exibe um mapa dos polos de desenvolvimento.

		Args:
			None

		Returns:
			None
		"""
		visualization.plotar_polos(self.camadas["bairros"])

	def mostrar_modelo_completo(self):
		"""Gera e exibe o mapa final com polos e pontos de articulação.

		Args:
			None

		Returns:
			None
		"""
		visualization.plotar_modelo_completo(self.camadas["bairros"], self.camadas.get("pontos_articulacao", gpd.GeoDataFrame()))
