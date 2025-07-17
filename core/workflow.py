from typing import Any, Dict, Optional

import geopandas as gpd

# Importa as funções dos módulos que criamos
from . import analysis, data_loader, visualization


class ModeloResetWorkflow:
	def __init__(self, crs_projetado: str = "EPSG:31983"):
		self.camadas: Dict[str, Any] = {}
		self.crs_padrao: str = "EPSG:4326"  # Geográfico padrão
		self.crs_projetado: str = crs_projetado

	def carregar_dados_base(self, path_bairros: str, path_residencias: str, epsg_bairros: int):
		"""Método responsável por carregar os dados de shapefile e residências."""
		print("Carregando dados de base...")
		self.camadas["bairros"] = data_loader.ler_shapefile(path_bairros, self.crs_padrao, epsg_bairros)
		self.camadas["residencias"] = data_loader.ler_residencias_csv(path_residencias, self.crs_padrao)
		print("Dados de base carregados.")

	def carregar_dados_ibge(self, path_setores: str, path_renda: str):
		"""Método responsável por carregar os dados do IBGE."""
		print("Carregando dados do IBGE...")
		# Shapefile já é lido com o CRS padrão
		self.camadas["setores_censitarios"] = data_loader.ler_shapefile(path_setores, self.crs_padrao)
		self.camadas["dados_de_renda"] = data_loader.ler_renda_csv(path_renda)
		print("Dados do IBGE carregados.")

	def processar_renda_ibge(self, municipio: str, uf: str):
		"""Método responsável por processar os dados de renda do IBGE."""
		print("Processando e vinculando dados de renda...")
		setores_filtrados = analysis.filtrar_setores_por_municipio(self.camadas["setores_censitarios"], municipio, uf)
		setores_com_renda = analysis.vincular_setores_com_renda(setores_filtrados, self.camadas["dados_de_renda"])
		bairros_com_renda = analysis.agregar_renda_por_bairro(self.camadas["bairros"], setores_com_renda, self.crs_projetado)
		self.camadas["bairros"] = bairros_com_renda
		print("Processamento de renda finalizado.")

	def processar_densidade(self, coluna_pop="POPULACAO"):
		"""Método responsável por processar a densidade."""
		print("Calculando densidade populacional...")
		self.camadas["bairros"] = analysis.calcular_densidade_populacional(
			self.camadas["bairros"], self.camadas["residencias"], self.crs_projetado, coluna_pop
		)
		print("Cálculo de densidade finalizado.")

	def carregar_e_processar_od(self, path_od: str):
		"""Método responsável por carregar e processar dados de origem-destino."""
		print("Carregando e processando dados de O/D...")
		df_od = data_loader.ler_od_csv(path_od)

		# Cria GeoDataFrames para origem e destino
		geom_origem = gpd.points_from_xy(df_od["longitude_origem"], df_od["latitude_origem"])
		origem_gdf = gpd.GeoDataFrame(df_od, geometry=geom_origem, crs=self.crs_padrao)

		geom_destino = gpd.points_from_xy(df_od["longitude_destino"], df_od["latitude_destino"])
		destino_gdf = gpd.GeoDataFrame(df_od, geometry=geom_destino, crs=self.crs_padrao)

		self.camadas["bairros"] = analysis.calcular_fluxos_od(self.camadas["bairros"], origem_gdf, destino_gdf)
		print("Processamento de O/D finalizado.")

	def identificar_polos_desenvolvimento(self, *polos_planejados):
		"""Método responsável por identificar os polos de desenvolvimento."""
		print("Identificando polos...")
		self.set_polos_planejados(*polos_planejados)
		self.camadas["bairros"] = analysis.identificar_polos(self.camadas["bairros"])

	def carregar_pontos_articulacao(self, path_pontos: str):
		"""Métodos responsável por carregar os pontos de articulação."""
		print("Carregando pontos de articulação...")
		self.camadas["pontos_articulacao"] = data_loader.ler_kml(path_pontos, self.crs_padrao)
		print(f"Carregados {len(self.camadas['pontos_articulacao'])} pontos.")

	def set_polos_planejados(self, *args: str):
		"""Função responsável por setar os polos planejados."""
		bairros = self.camadas.get("bairros", gpd.GeoDataFrame())
		if bairros.empty:
			return

		bairros["tipo_polo"] = "Nenhum"
		for polo in args:
			bairros.loc[bairros["name"].isin([polo]), "tipo_polo"] = "Planejado"

		# self.camadas["bairros"] = bairros

	def plotar_densidade(self):
		"""Método responsável por plotar a densidade."""
		visualization.plotar_mapa_coropletico(self.camadas["bairros"], "densidade_km2", "Densidade Populacional (hab/km²)", "OrRd")

	def plotar_renda_media(self):
		"""Método responsável por plotar a renda média."""
		visualization.plotar_mapa_coropletico(self.camadas["bairros"], "renda_media_bairro", "Renda Média por Bairro", "YlGn")

	def mostrar_polos(self):
		"""Método responsável por mostrar os polos."""
		visualization.plotar_polos(self.camadas["bairros"])

	def mostrar_modelo_completo(self):
		"""Método responsável por mostrar o modelo completo."""
		visualization.plotar_modelo_completo(self.camadas["bairros"], self.camadas.get("pontos_articulacao", gpd.GeoDataFrame()))
