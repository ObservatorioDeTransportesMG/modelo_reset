import os
from typing import Any

import geopandas as gpd
import networkx as nx

from . import analysis, data_loader, network_design, visualization
from .ibge_downloader import baixar_dados_censo_renda, baixar_malha_municipal


class ModeloReset:
	"""
	Orquestra o fluxo de trabalho completo para análise geoespacial, desde o carregamento de dados até a visualização de resultados.
	"""

	def __init__(self, crs_projetado: int = 31983):
		"""Inicializa o workflow, definindo os sistemas de coordenadas e o contêiner de camadas.

		Args:
			crs_projetado (str, optional): O CRS projetado a ser usado para cálculos de área e distância. Padrão é "EPSG:31983".
		"""
		self.camadas: dict[str, Any] = {}
		self.crs_padrao: str = "EPSG:4326"
		self.crs_projetado: int = crs_projetado
		self.grafo: nx.MultiDiGraph | None = None
		print(f"ModeloReset inicializado. CRS Padrão: {self.crs_padrao}, CRS Projetado: EPSG:{self.crs_projetado}")

	def carregar_dados_base(self, path_bairros: str, epsg_bairros: int):
		"""Carrega as camadas de dados geográficos base (bairros e residências).

		Args:
			path_bairros (str): Caminho para o shapefile dos bairros.
			path_residencias (str): Caminho para o CSV das residências.
			epsg_bairros (int): Código EPSG original do shapefile de bairros, caso não esteja definido no arquivo.
		"""
		print("Carregando dados de base...")
		self.camadas["bairros"] = data_loader.ler_shapefile(path_bairros, self.crs_padrao, epsg_bairros)
		print("Dados de base carregados.")

	def carregar_dados_ibge(self, ano_censo: int, uf: str = "MG"):
		"""Carrega os dados do IBGE (setores censitários e dados de renda).

		Args:
			ano_malha (int): O ano da malha territorial do IBGE (ex: 2024).
			ano_censo (int): O ano do censo do IBGE (ex: 2022).
			uf (str): A sigla do estado em maiúsculas (ex: "SP", "MG").
		"""
		print("Carregando dados do IBGE...")
		path_setores = baixar_malha_municipal(diretorio_saida=os.path.join("data", "malha"), uf=uf, ano=ano_censo)
		path_renda = baixar_dados_censo_renda(diretorio_saida="data", ano=ano_censo)

		if path_setores is None or path_renda is None:
			raise Exception("Erro ao baixar dados do IBGE.")

		self.camadas["setores_censitarios"] = data_loader.ler_shapefile(path_setores, self.crs_padrao)
		self.camadas["dados_de_renda"] = data_loader.ler_renda_csv(path_renda, separador=";")
		print("Dados do IBGE carregados.")

	def carregar_rede_viaria(self, path_vias: str, epsg_vias: int = 0):  # <<< NOVO MÉTODO
		"""Carrega a camada de dados da rede viária (ruas).

		Args:
			path_vias (str): Caminho para o shapefile das vias.
			epsg_vias (int): Código EPSG original, se não estiver no .prj.
		"""
		print("Carregando rede viária...")
		self.camadas["vias"] = data_loader.ler_shapefile(path_vias, self.crs_padrao, epsg_vias)
		print("Rede viária carregada.")

	def _processar_renda_ibge(self, municipio: str):
		"""Filtra, vincula e agrega dados de renda e população por bairro.

		Args:
			municipio (str): Nome do município para filtrar os setores censitários.
			uf (str): Sigla do estado (UF) para filtrar os setores.
		"""
		print("Processando e vinculando dados de renda...")
		setores_filtrados = analysis.filtrar_setores_por_municipio(self.camadas["setores_censitarios"], municipio)
		setores_com_renda = analysis.vincular_setores_com_renda(setores_filtrados, self.camadas["dados_de_renda"])
		bairros_com_renda = analysis.agregar_renda_por_bairro(self.camadas["bairros"], setores_com_renda, self.crs_projetado)
		self.camadas["bairros"] = bairros_com_renda
		self.camadas["setores"] = setores_com_renda
		print("Processamento de renda finalizado.")

	def _processar_densidade(self):
		"""Calcula a densidade populacional para a camada de bairros."""
		print("Calculando densidade populacional...")
		self.camadas["bairros"] = analysis.calcular_densidade_populacional(self.camadas["bairros"], self.crs_projetado)

	def processar_dados(self, municipio: str):
		"""Função responsável por processar todos os dados necessários."""
		self._processar_renda_ibge(municipio)
		self._processar_densidade()

	def carregar_e_processar_od(self, path_od: str):
		"""Carrega dados de Origem-Destino e calcula os fluxos por bairro.

		Args:
			path_od (str): Caminho para o arquivo CSV de Origem-Destino.
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
			*polos_planejados (str): Nomes dos bairros a serem classificados como "Planejado".
		"""
		print("Identificando polos...")
		self.set_polos_planejados(*polos_planejados)
		self.camadas["bairros"] = analysis.identificar_polos(self.camadas["bairros"])

	def carregar_pontos_articulacao(self, path_pontos: str):
		"""Carrega a camada de pontos de articulação a partir de um arquivo KML.

		Args:
			path_pontos (str): Caminho para o arquivo KML dos pontos de articulação.
		"""
		print("Carregando pontos de articulação...")
		self.camadas["pontos_articulacao"] = data_loader.ler_kml(path_pontos, self.crs_padrao)
		print(f"Carregados {len(self.camadas['pontos_articulacao'])} pontos.")

	def _projetar_camadas_para_analise(self):
		"""
		Garante que todas as camadas de análise estejam projetadas no CRS métrico.
		"""
		print(f"Projetando camadas para o CRS métrico: EPSG:{self.crs_projetado}")
		target_crs = f"EPSG:{self.crs_projetado}"

		camadas_para_projetar = {"bairros": "bairros", "vias": "vias", "pontos_articulacao": "pontos_articulacao"}

		for nome_camada, nome_origem in camadas_para_projetar.items():
			if nome_origem in self.camadas:
				if self.camadas[nome_origem].crs != target_crs:
					self.camadas[nome_camada] = self.camadas[nome_origem].to_crs(target_crs)
				else:
					self.camadas[nome_camada] = self.camadas[nome_origem]
			else:
				print(f"Aviso: Camada de origem '{nome_origem}' não carregada. Pulando projeção.")

	def set_polos_planejados(self, *args: str):
		"""Define manualmente quais bairros são classificados como "Planejado".

		Args:
			*args (str): Uma sequência de nomes de bairros a serem definidos como "Planejado".
		"""
		bairros = self.camadas.get("bairros", gpd.GeoDataFrame())
		if bairros.empty:
			return

		bairros["tipo_polo"] = "Nenhum"
		for polo in args:
			bairros.loc[bairros["name"].isin([polo]), "tipo_polo"] = "Planejado"

	def gerar_rotas_otimizadas(self, bairro_central: str = "Centro"):
		"""
		Orquestra todo o processo de análise de rede.

		1. Projeta as camadas.
		2. Filtra as vias.
		3. Gera o grafo ponderado.
		4. Calcula os caminhos de ida e volta.
		"""
		print("Iniciando geração de rotas otimizadas...")

		# 1. Garantir que as camadas estão prontas e projetadas
		camadas_necessarias = ["bairros", "vias", "pontos_articulacao"]
		if not all(k in self.camadas for k in camadas_necessarias):
			raise ValueError("Camadas 'bairros', 'vias' e 'pontos_articulacao' são necessárias. Carregue-as primeiro.")

		self._projetar_camadas_para_analise()

		bairros_proj = self.camadas["bairros"]
		vias_proj = self.camadas["vias"]
		pontos_art_proj = self.camadas["pontos_articulacao"]

		# 2. Filtrar vias da área de estudo
		print("Filtrando rede viária para a área de estudo...")
		vias_filtradas = network_design.filtrar_vias_por_bairros(vias_proj, bairros_proj)
		self.camadas["vias_filtradas"] = vias_filtradas

		# 3. Gerar o grafo
		print("Gerando o grafo ponderado da rede...")
		self.grafo = network_design.criar_grafo_ponderado(vias_filtradas, pontos_art_proj)

		if not self.grafo:
			raise Exception("Falha ao criar o grafo.")

		# 4. Calcular caminhos
		print("Calculando caminhos de VOLTA...")
		self.camadas["caminhos_volta"] = network_design.encontrar_caminho_minimo(
			bairros_proj, self.grafo, bairro_central=bairro_central, sentido="VOLTA"
		)

		print("Calculando caminhos de IDA...")
		self.camadas["caminhos_ida"] = network_design.encontrar_caminho_minimo(bairros_proj, self.grafo, bairro_central=bairro_central, sentido="IDA")

		print("Geração de rotas concluída.")

	def mostrar_centroids(self):
		"""Plota os bairros e os centroides dos setores censitários associados."""
		setores = self.camadas["setores"].copy()
		crs_original = setores.crs

		setores_projetado = setores.to_crs(epsg=self.crs_projetado)

		centroides_projetados = setores_projetado.geometry.centroid

		setores["geometry"] = centroides_projetados.to_crs(crs_original)
		setores_associados = gpd.sjoin(setores, self.camadas["bairros"], how="left", predicate="within")
		setores_associados = setores_associados[setores_associados["index_right"].notnull()]

		visualization.plotar_centroid_e_bairros(self.camadas["bairros"], setores_associados, self.crs_projetado)

	def plotar_densidade(self):
		"""Gera e exibe um mapa coroplético da densidade populacional dos bairros."""
		visualization.plotar_mapa_coropletico(
			self.camadas["bairros"], self.crs_projetado, "densidade_km2", "Densidade Populacional (hab/km²)", "OrRd"
		)

	def plotar_renda_media(self):
		"""Gera e exibe um mapa coroplético da renda média dos bairros."""
		visualization.plotar_mapa_coropletico(self.camadas["bairros"], self.crs_projetado, "renda_total_bairro", "Renda Média por Bairro", "YlGn")

	def mostrar_rotas_otimizadas(self):  # <<< NOVO MÉTODO
		"""
		Exibe o mapa final com as rotas de ida e volta otimizadas.
		"""
		print("Gerando visualização das rotas...")
		camadas_necessarias = ["vias_filtradas", "bairros", "caminhos_ida", "caminhos_volta"]
		if not all(k in self.camadas for k in camadas_necessarias):
			print("Camadas de rotas não encontradas. Execute `gerar_rotas_otimizadas()` primeiro.")
			return

		visualization.plotar_caminhos(
			self.camadas["vias_filtradas"], self.camadas["bairros"], self.camadas["caminhos_ida"], self.camadas["caminhos_volta"]
		)

	def mostrar_polos(self):
		"""Gera e exibe um mapa dos polos de desenvolvimento."""
		visualization.plotar_polos(self.camadas["bairros"], self.crs_projetado)

	def mostrar_modelo_completo(self):
		"""Gera e exibe o mapa final com polos e pontos de articulação."""
		visualization.plotar_modelo_completo(self.camadas["bairros"], self.camadas.get("pontos_articulacao", gpd.GeoDataFrame()), self.crs_projetado)
