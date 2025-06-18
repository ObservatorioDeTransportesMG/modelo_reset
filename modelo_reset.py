# from typing import Optional

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd


class ModeloReset:
	def __init__(self, crs_projetado: str = "EPSG:31983"):
		self.camadas = {}
		# self.gdf_bairros = gpd.GeoDataFrame()
		# self.origem_destino = gpd.GeoDataFrame()
		# self.destino = gpd.GeoDataFrame()
		# self.origem = gpd.GeoDataFrame()
		# self.residencias = gpd.GeoDataFrame()
		# self.bairros = gpd.GeoDataFrame()
		# self.pontos_articulacao = gpd.GeoDataFrame()
		# self.svetc = gpd.GeoDataFrame()

		self.crs_padrao: str = "EPSG:4326"
		self.crs_projetado = crs_projetado

	def _ler_shapefile(self, path: str, epsg: int = 4326):
		shapefile = gpd.read_file(path, ignore_geometry=False)
		if shapefile.crs is None:
			shapefile = shapefile.set_crs(epsg=epsg, inplace=True)
		shapefile = shapefile.to_crs(self.crs_padrao)
		return shapefile

	def _ler_residencias(self, path: str):
		df = pd.read_csv(path)
		geometria = gpd.points_from_xy(df["longitude"], df["latitude"])
		residencias = gpd.GeoDataFrame(df, geometry=geometria)
		residencias = residencias.set_crs(self.crs_padrao)
		return residencias

	def carregar_dados_base(self, path_bairros: str, path_residencias: str, epsg: int):
		"""Carrega os dados geográficos essenciais."""
		print("Carregando dados de bairros e residências...")
		self.camadas["gdf_bairros"] = self._ler_shapefile(path_bairros, epsg)
		self.camadas["residencias"] = self._ler_residencias(path_residencias)
		print("Dados carregados com sucesso.")

	def carregar_dados_od(self, path_od: str):
		"""Carrega os dados geográficos essenciais."""
		print("Carregando dados de bairros e residências...")
		df = self._ler_dados_origem_destino(path_od)
		self._tratar_dados_origem_destino(df)
		print("Dados carregados com sucesso.")

	def _ler_dados_origem_destino(self, path: str):
		origem_destino = pd.read_csv(path)
		return origem_destino

	def _tratar_dados_origem_destino(self, df: pd.DataFrame):
		geometria_origem = gpd.points_from_xy(df["longitude_origem"], df["latitude_origem"])
		self.camadas["destino"] = gpd.GeoDataFrame(df, geometry=geometria_origem, crs=self.crs_padrao).to_crs(self.crs_projetado)

		geometria_destino = gpd.points_from_xy(df["longitude_destino"], df["latitude_destino"])
		self.camadas["origem"] = gpd.GeoDataFrame(df, geometry=geometria_destino, crs=self.crs_padrao).to_crs(self.crs_projetado)

	def calcular_origem_destino(self):
		"""Função responsável por calcular a origem e destino."""
		origem_projetado = self.camadas.get("origem", None)
		destino_projetado = self.camadas.get("destino", None)
		bairros = self.camadas.get("gdf_bairros", None)

		if origem_projetado is None or destino_projetado is None or bairros is None:
			raise

		if origem_projetado.crs is not bairros.crs:
			origem_projetado = origem_projetado.to_crs(bairros.crs)
		if destino_projetado.crs is not bairros.crs:
			destino_projetado = destino_projetado.to_crs(bairros.crs)

		pontos_origem = gpd.sjoin(origem_projetado, bairros, how="left", predicate="within")
		pontos_destino = gpd.sjoin(destino_projetado, bairros, how="left", predicate="within")

		quantidade_pontos_origem = pontos_origem.groupby("index_right").size()
		quantidade_pontos_destino = pontos_destino.groupby("index_right").size()

		bairros["n_origens"] = bairros.index.map(quantidade_pontos_origem).fillna(0).astype(int)
		bairros["n_destinos"] = bairros.index.map(quantidade_pontos_destino).fillna(0).astype(int)
		bairros["fluxo_total"] = bairros["n_origens"] + bairros["n_destinos"]

		print("Cálculo de fluxos de O/D finalizado.")

	def calcular_densidade_e_renda(self, coluna_renda="RENDIMENTO", coluna_pop="POPULACAO"):
		"""
		Calcula a densidade populacional e a renda média por bairro.

		Esta função combina a lógica das funções `calcular_densidade_por_bairro` e
		`calcular_distribuicao_de_renda_por_bairro` do seu código original.
		"""
		bairros: gpd.GeoDataFrame = self.camadas.get("gdf_bairros", gpd.GeoDataFrame())
		residencias: gpd.GeoDataFrame = self.camadas.get("residencias", gpd.GeoDataFrame())

		if bairros.empty or residencias.empty:
			print("Erro: GeoDataFrames de bairros e/ou residências não foram carregados.")
			return

		print("Calculando densidade e renda por bairro...")
		bairros_proj = bairros.to_crs(self.crs_projetado)
		residencias_proj = residencias.to_crs(self.crs_projetado)

		bairros_proj["area_km2"] = bairros_proj.geometry.area / 1_000_000

		# Junção espacial para agregar dados das residências para os bairros
		pontos_no_bairro = gpd.sjoin(residencias_proj, bairros_proj, how="left", predicate="within")

		# Agrega os dados
		# agregado = pontos_no_bairro.groupby("index_right").agg(
		# 	populacao_total=(coluna_pop, "sum"), renda_total=(coluna_renda, "sum"), n_residencias=("geometry", "count")
		# )
		agregado = pontos_no_bairro.groupby("index_right").agg(populacao_total=(coluna_pop, "sum"), n_residencias=("geometry", "count"))

		# Junta os dados agregados de volta ao GeoDataFrame de bairros
		bairros_proj = bairros_proj.join(agregado)
		bairros_proj["populacao_total"] = bairros_proj["populacao_total"].fillna(0).astype(int)
		# bairros_proj["renda_total"] = bairros_proj["renda_total"].fillna(0)
		bairros_proj["n_residencias"] = bairros_proj["n_residencias"].fillna(0).astype(int)

		# Calcula a densidade e a renda média
		bairros_proj["densidade_km2"] = bairros_proj["populacao_total"] / bairros_proj["area_km2"]
		# Evita divisão por zero para a renda média
		# bairros_proj["renda_media"] = bairros_proj.apply(
		# 	lambda row: row["renda_total"] / row["populacao_total"] if row["populacao_total"] > 0 else 0, axis=1
		# )

		self.camadas["gdf_bairros"] = bairros_proj.to_crs(self.crs_padrao)
		print("Cálculo de densidade e renda finalizado.")

	def plotar_densidade(self, coluna="densidade_km2", cmap="OrRd"):
		"""
		Plota o mapa de densidade por bairro com base na coluna especificada.

		Parâmetros:
			gdf_bairros: GeoDataFrame com a geometria dos bairros e a coluna de densidade.
			coluna: Nome da coluna com os valores de densidade a serem usados na coloração.
			cmap: Mapa de cores (ex: 'OrRd', 'YlGnBu', 'viridis').
		"""
		fig, ax = plt.subplots(1, 1, figsize=(10, 8))
		self.camadas["gdf_bairros"].plot(column=coluna, ax=ax, legend=True, cmap=cmap, edgecolor="black", linewidth=0.5)
		ax.set_title("Densidade residentes por km²", fontsize=14)
		ax.axis("off")
		plt.tight_layout()
		plt.show()

	def set_polos_planejados(self, *args: str):
		"""Função responsável por setar os polos planejados."""
		bairros = self.camadas.get("gdf_bairros", gpd.GeoDataFrame())
		if bairros.empty:
			return

		bairros["tipo_polo"] = "Nenhum"
		for polo in args:
			bairros.loc[bairros["name"].isin([polo]), "tipo_polo"] = "Planejado"

		self.camadas["gdf_bairros"] = bairros

	def selecionar_polos_desenvolvimento(self, densidade_alta_limiar=0.8, renda_baixa_limiar=0.4, fluxo_alto_limiar=0.8):
		"""
		Classifica os bairros em Polos de Desenvolvimento com base em critérios.

		Os limiares (thresholds) são quantis (ex: 0.8 para os 20% mais altos).
		"""
		bairros: gpd.GeoDataFrame = self.camadas.get("gdf_bairros", gpd.GeoDataFrame())

		if bairros.empty:
			return

		if "densidade_km2" not in bairros.columns:
			print("Execute `calcular_densidade_e_renda()` primeiro.")
			return
		if "fluxo_total" not in bairros.columns:
			print("Execute `calcular_fluxos_od()` primeiro.")
			return

		print("Selecionando Polos de Desenvolvimento...")

		# Define os limiares com base nos quantis dos dados
		dens_alta = bairros["densidade_km2"].quantile(densidade_alta_limiar)
		# renda_baixa = bairros["renda_media"].quantile(renda_baixa_limiar)
		fluxo_alto = bairros["fluxo_total"].quantile(fluxo_alto_limiar)

		# Polo Consolidado: Alta densidade, Baixa Renda, Alto fluxo de viagens
		bairros.loc[
			(bairros["densidade_km2"] >= dens_alta)
			# & (bairros["renda_media"] <= renda_baixa)
			& (bairros["fluxo_total"] >= fluxo_alto),
			"tipo_polo",
		] = "Consolidado"

		# Polo Emergente: Alta densidade, Baixa Renda, mas SEM alto fluxo
		bairros.loc[
			(bairros["densidade_km2"] >= dens_alta)
			# & (bairros["renda_media"] <= renda_baixa)
			& (bairros["fluxo_total"] < fluxo_alto),
			"tipo_polo",
		] = "Emergente"

		# NOTA: Polos Planejados geralmente vêm de uma fonte externa (ex: Plano Diretor)
		# Ex: bairros.loc[bairros['NOME'].isin(['Distrito Industrial']), 'tipo_polo'] = "Planejado"
		# O Distrito Industrial foi identificado como polo planejado no estudo

		print("Seleção de Polos finalizada.")
		self.plotar_polos()

	def plotar_polos(self):
		"""Plota o mapa dos Polos de Desenvolvimento, similar à Figura 29 da dissertação."""
		bairros = self.camadas["gdf_bairros"]
		if "tipo_polo" not in bairros.columns:
			print("Execute `selecionar_polos_desenvolvimento()` primeiro.")
			return

		fig, ax = plt.subplots(1, 1, figsize=(12, 12))

		# Mapeia os tipos de polo para cores
		color_map = {"Consolidado": "green", "Emergente": "orange", "Planejado": "blue", "Nenhum": "lightgrey"}

		bairros.plot(color=bairros["tipo_polo"].map(color_map), ax=ax, edgecolor="white", linewidth=0.5, legend=True)

		# Adiciona legendas personalizadas
		from matplotlib.patches import Patch

		legend_elements = [Patch(facecolor=color, edgecolor="w", label=label) for label, color in color_map.items()]
		ax.legend(handles=legend_elements, title="Tipo de Polo", loc="lower right")

		ax.set_title("Polos de Desenvolvimento (Método RESET)", fontsize=16)
		ax.set_axis_off()
		plt.tight_layout()
		plt.show()

	def carregar_pontos_articulacao(self, path_pontos: str, epsg: int):
		"""Carrega e armazena os Pontos de Articulação."""
		print("Carregando Pontos de Articulação...")
		self.pontos_articulacao = self._ler_shapefile(path_pontos, epsg)
		print(f"Carregados {len(self.pontos_articulacao)} Pontos de Articulação.")

	def mostrar_pontos_de_articulacao(self):
		"""Plota os Pontos de Articulação sobre o mapa de bairros, como na Figura 30."""
		pontos_articulacao = self.camadas["pontos_articulacao"]
		bairros = self.camadas["gdf_camadas"]
		if pontos_articulacao is None or bairros is None:
			raise

		if pontos_articulacao.empty:
			print("Carregue os Pontos de Articulação primeiro.")
			return

		fig, ax = plt.subplots(1, 1, figsize=(12, 12))

		# Plota os bairros como base
		bairros.plot(ax=ax, color="lightgray", edgecolor="white")

		# Plota os pontos de articulação
		pontos_articulacao.plot(ax=ax, marker="o", color="red", markersize=50, label="Pontos de Articulação")

		ax.set_title("Pontos de Articulação", fontsize=16)
		ax.legend()
		ax.set_axis_off()
		plt.tight_layout()
		plt.show()

	# def estabelecer_svetc(self, path_vias: str, epsg: int, nomes_avenidas_principais: list):
	# 	"""
	# 	Estabelece o Sistema Viário Estrutural de Transporte Coletivo (SVETC) selecionando as principais avenidas.
	# 	"""
	# 	print("Estabelecendo o SVETC...")
	# 	vias = self._ler_shapefile(path_vias, epsg)

	# 	# Filtra as vias que são consideradas principais
	# 	self.svetc = vias[vias["NOME_DA_COLUNA_VIA"].isin(nomes_avenidas_principais)]

	# 	print(f"SVETC estabelecido com {len(self.svetc)} segmentos de via.")

	# def mostrar_svetc(self):
	# 	"""Plota o SVETC sobre o mapa, como na Figura 32."""
	# 	if self.svetc.empty:
	# 		print("Estabeleça o SVETC primeiro.")
	# 		return

	# 	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	# 	self.gdf_bairros.plot(ax=ax, color="lightgray", edgecolor="white")
	# 	self.svetc.plot(ax=ax, color="black", linewidth=2, label="SVETC")

	# 	ax.set_title("Sistema Viário Estrutural de Transporte Coletivo (SVETC)", fontsize=16)
	# 	ax.legend()
	# 	ax.set_axis_off()
	# 	plt.tight_layout()
	# 	plt.show()

	# # Continuação da classe ModeloReset

	# def conceber_linhas(self, path_linhas_planejadas: str, epsg: int):
	# 	"""
	# 	Carrega um shapefile de linhas já desenhadas para visualização.

	# 	A concepção real é um processo complexo de planejamento.
	# 	"""
	# 	print("Carregando rede de linhas planejada...")
	# 	self.linhas_planejadas = self._ler_shapefile(path_linhas_planejadas, epsg)
	# 	print("Rede planejada carregada.")

	# def mostrar_rede_planejada(self):
	# 	"""Plota a rede final planejada, como na Figura 40."""
	# 	if self.linhas_planejadas.empty:
	# 		print("Carregue as linhas planejadas primeiro.")
	# 		return

	# 	fig, ax = plt.subplots(1, 1, figsize=(12, 12))

	# 	self.gdf_bairros.plot(ax=ax, color="#EFEFEF", edgecolor="white")

	# 	# Plota as linhas com cores baseadas em uma coluna 'TIPO_LINHA'
	# 	# (ex: 'Radial', 'Transversal', 'Local')
	# 	self.linhas_planejadas.plot(column="TIPO_LINHA", ax=ax, legend=True, linewidth=1.5)

	# 	ax.set_title("Rede de Transporte Planejada (Método RESET)", fontsize=16)
	# 	ax.set_axis_off()
	# 	plt.tight_layout()
	# 	plt.show()

	@property
	def origem(self):
		"""Retorna dataframe de origem."""
		return self.camadas.get("origem", gpd.GeoDataFrame())

	@property
	def bairros(self):
		"""Retorna dataframe de origem."""
		return self.camadas.get("gdf_bairros", gpd.GeoDataFrame())
