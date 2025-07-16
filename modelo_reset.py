import os
from typing import Optional

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from pyogrio import list_layers


class ModeloReset:
	def __init__(self, crs_projetado: str = "EPSG:31983"):
		self.camadas = {}

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

	def _carregar_setores_censitario(self, path_setores: str):
		"""
		Carrega o shapefile dos setores censitários e o padroniza para o CRS do projeto.
		"""
		print(f"Carregando shapefile de setores censitários de: {path_setores}")
		shapefile = gpd.read_file(path_setores)

		shapefile = shapefile.to_crs(self.crs_padrao)

		self.camadas["setores_censitarios"] = shapefile
		print("Shapefile de setores censitários carregado.")

	def _carregar_dados_renda(self, path_renda: str, separador_csv: str = ",", encoding_csv: str = "latin-1"):
		"""
		Carrega o shapefile dos setores censitários e o padroniza para o CRS do projeto.
		"""
		print(f"Carregando dados de renda de: {path_renda}")
		df_renda = pd.read_csv(path_renda, sep=separador_csv, encoding=encoding_csv)
		self.camadas["dados_de_renda"] = df_renda.copy()
		print("Dados de renda carregada com sucesso")

	def carregar_dados_IBGE(self, path_setores: str, path_renda: str):
		"""Função responsável por carregar os dados do IBGE."""
		self._carregar_setores_censitario(path_setores)
		self._carregar_dados_renda(path_renda)

	def _filtrar_setores_censitarios(self, municipio: str, uf: str) -> gpd.GeoDataFrame:
		"""
		Filtra os setores censitários para um município e UF específicos.

		Args:
			municipio (str): O nome do município (ex: "Montes Claros").
			uf (str): A sigla da UF (ex: "MG").

		Returns:
			gpd.GeoDataFrame: GeoDataFrame contendo apenas os setores do município especificado.
		"""
		if "setores_censitarios" not in self.camadas or self.camadas["setores_censitarios"].empty:
			print("Erro: A camada 'setores_censitarios' não foi carregada. Chame _carregar_setores_censitario() primeiro.")
			return gpd.GeoDataFrame()

		print(f"Filtrando setores para o município de {municipio.upper()} - {uf.upper()}...")

		setores_df = self.camadas["setores_censitarios"]

		filtro = (setores_df["NM_MUN"].str.upper() == municipio.upper()) & (setores_df["NM_UF"].str.upper() == uf.upper())

		setores_filtrados = setores_df[filtro].copy()

		if setores_filtrados.empty:
			print(f"Aviso: Nenhum setor censitário encontrado para {municipio} - {uf}.")
		else:
			print(f"{len(setores_filtrados)} setores censitários encontrados para {municipio} - {uf}.")

		return setores_filtrados

	def _vincular_setores_com_renda(self, municipio: str, uf: str, coluna_setor_shp: str = "CD_SETOR", coluna_setor_csv: str = "CD_SETOR"):
		"""
		Carrega, filtra e vincula os dados de setores censitários com uma planilha de renda.

		Args:
			municipio (str): Nome do município para filtrar.
			uf (str): Sigla da UF para filtrar.
			coluna_setor_shp (str): Nome da coluna com o código do setor no shapefile.
			coluna_setor_csv (str): Nome da coluna com o código do setor no CSV.
		"""
		# Passo 1: Carregar os dados geográficos dos setores
		df_renda = self.camadas["dados_de_renda"]

		setores_municipio = self._filtrar_setores_censitarios(municipio=municipio, uf=uf)

		if setores_municipio.empty:
			return

		try:
			setores_municipio[coluna_setor_shp] = setores_municipio[coluna_setor_shp].astype(str)
			df_renda[coluna_setor_csv] = df_renda[coluna_setor_csv].astype(str)
		except KeyError as e:
			print(f"Erro: A coluna {e} não foi encontrada. Verifique os parâmetros 'coluna_setor_shp' e 'coluna_setor_csv'.")
			print(f"Colunas disponíveis no Shapefile: {setores_municipio.columns.tolist()}")
			print(f"Colunas disponíveis no CSV: {df_renda.columns.tolist()}")
			return

		print("Vinculando dados geográficos com dados de renda...")
		setores_com_renda = setores_municipio.merge(df_renda, left_on=coluna_setor_shp, right_on=coluna_setor_csv, how="left")

		self.camadas["setores_com_renda"] = setores_com_renda

		print(f"Vinculação finalizada. A camada 'setores_com_renda' foi criada com {len(setores_com_renda)} registros.")

	def _vincular_renda_com_bairro(self):
		"""
		Associa os dados de renda dos setores censitários a cada bairro, agrupando e calculando a renda total e média por bairro.
		"""
		print("Iniciando a vinculação de dados de renda aos bairros...")

		setores = self.camadas.get("setores_com_renda")
		bairros = self.camadas.get("gdf_bairros")

		if setores is None or bairros is None or setores.empty or bairros.empty:
			print("Erro: As camadas 'setores_com_renda' ou 'gdf_bairros' não foram carregadas ou estão vazias.")
			return

		colunas_para_agregar = {"V06005": "renda_total_setor", "V06002": "populacao_setor"}

		setores_limpos = setores.copy()
		for col_original, col_novo in colunas_para_agregar.items():
			if col_original in setores_limpos.columns:
				setores_limpos[col_original] = setores_limpos[col_original].astype(str)
				setores_limpos[col_novo] = pd.to_numeric(setores_limpos[col_original].str.replace(",", ".", regex=False), errors="coerce").fillna(0)
			else:
				print(f"Aviso: Coluna '{col_original}' não encontrada no DataFrame de setores.")
				setores_limpos[col_novo] = 0

		bairros_proj = bairros.to_crs(self.crs_projetado)
		setores_limpos_proj = setores_limpos.to_crs(self.crs_projetado)

		setores_centroids = setores_limpos_proj.copy()
		setores_centroids["geometry"] = setores_centroids.geometry.centroid

		setores_nos_bairros = gpd.sjoin(setores_centroids, bairros_proj, how="left", predicate="within")

		print("Agrupando dados por bairro e somando valores...")
		if "index_right" not in setores_nos_bairros.columns:
			print("Erro: A junção espacial não conseguiu associar setores a bairros.")
			return

		dados_agregados = setores_nos_bairros.groupby("index_right").agg(
			renda_total_bairro=("renda_total_setor", "sum"), populacao_total_bairro=("populacao_setor", "sum")
		)

		bairros_com_renda = bairros_proj.join(dados_agregados)

		bairros_com_renda["renda_total_bairro"] = bairros_com_renda["renda_total_bairro"].fillna(0)
		bairros_com_renda["populacao_total_bairro"] = bairros_com_renda["populacao_total_bairro"].fillna(0)

		bairros_com_renda["renda_media_bairro"] = bairros_com_renda.apply(
			lambda row: row["renda_total_bairro"] / row["populacao_total_bairro"] if row["populacao_total_bairro"] > 0 else 0, axis=1
		)

		self.camadas["gdf_bairros"] = bairros_com_renda.to_crs(self.crs_padrao)

		print("Vinculação de renda por bairro finalizada com sucesso!")
		colunas_resultado = ["name", "populacao_total_bairro", "renda_total_bairro", "renda_media_bairro"]
		if "name" not in self.camadas["gdf_bairros"].columns:
			colunas_resultado[0] = self.camadas["gdf_bairros"].index.name

		print(self.camadas["gdf_bairros"][colunas_resultado].head())

	def vincular_dados_IBGE(self, municipio: str, uf: str):
		"""Vincular dados do IBGE."""
		self._vincular_setores_com_renda(municipio, uf)
		self._vincular_renda_com_bairro()

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
		renda_baixa = bairros["renda_media_bairro"].quantile(renda_baixa_limiar)
		fluxo_alto = bairros["fluxo_total"].quantile(fluxo_alto_limiar)

		# Polo Consolidado: Alta densidade, Baixa Renda, Alto fluxo de viagens
		bairros.loc[
			(bairros["densidade_km2"] >= dens_alta) & (bairros["renda_media_bairro"] <= renda_baixa) & (bairros["fluxo_total"] >= fluxo_alto),
			"tipo_polo",
		] = "Consolidado"

		# Polo Emergente: Alta densidade, Baixa Renda, mas SEM alto fluxo
		bairros.loc[
			(bairros["densidade_km2"] >= dens_alta) & (bairros["renda_media_bairro"] <= renda_baixa) & (bairros["fluxo_total"] < fluxo_alto),
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

	def carregar_pontos_articulacao(self, path_pontos: str, epsg: Optional[int] = None):
		"""Carrega e armazena os Pontos de Articulação."""
		print("Carregando Pontos de Articulação...")
		# self.pontos_articulacao = self._ler_shapefile(path_pontos, epsg)
		if path_pontos.endswith(".kml"):
			self.camadas["pontos_articulacao"] = self._processar_kml(path_pontos)
			# self.pontos_articulacao.to_crs(epsg)
		print(f"Carregados {len(self.camadas['pontos_articulacao'])} Pontos de Articulação.")

	def _processar_kml(self, path_pontos: str):
		gdfs = []

		layers = list_layers(path_pontos)

		for layer_name in layers:
			gdf = gpd.read_file(path_pontos, driver="KML", layer=layer_name[0])

			gdf["camada"] = layer_name[0]

			gdfs.append(gdf)

		# Concatena todos os GeoDataFrames
		return gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))

	def mostrar_pontos_de_articulacao(self):
		"""Plota os Pontos de Articulação sobre o mapa de bairros, como na Figura 30."""
		pontos_articulacao = self.camadas["pontos_articulacao"]
		bairros = self.camadas["gdf_bairros"]
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

	def mostrar_modelo_completo(self):
		"""Plota os Pontos de Articulação sobre o mapa de bairros, como na Figura 30."""
		pontos_articulacao = self.camadas["pontos_articulacao"]
		bairros = self.camadas["gdf_bairros"]
		if pontos_articulacao is None or bairros is None:
			raise

		if pontos_articulacao.empty:
			print("Carregue os Pontos de Articulação primeiro.")
			return

		fig, ax = plt.subplots(1, 1, figsize=(12, 12))

		# Plota os bairros como base
		# bairros.plot(ax=ax, color="lightgray", edgecolor="white")
		color_map = {"Consolidado": "green", "Emergente": "orange", "Planejado": "blue", "Nenhum": "lightgrey"}

		bairros.plot(color=bairros["tipo_polo"].map(color_map), ax=ax, edgecolor="white", linewidth=0.5, legend=True)

		# Adiciona legendas personalizadas
		from matplotlib.patches import Patch

		legend_elements = [Patch(facecolor=color, edgecolor="w", label=label) for label, color in color_map.items()]
		ax.legend(handles=legend_elements, title="Tipo de Polo", loc="lower right")

		# Plota os pontos de articulação
		pontos_articulacao.plot(ax=ax, marker="o", color="red", markersize=50, label="Pontos de Articulação")

		ax.set_title("Mapa Completo", fontsize=16)
		# ax.legend()
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
