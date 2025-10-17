from typing import Literal

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiPoint, Point
from shapely.ops import nearest_points

# --- Definições Globais de CRS ---
PROJECTED_CRS = "EPSG:31983"  # SIRGAS 2000 / UTM Zone 23S (para cálculos em metros)
GEOGRAPHIC_CRS = "EPSG:4326"  # WGS 84 (para dados em lat/lon)

# --- Funções de Análise (Refatoradas) ---


def calcular_peso_atrativo(ponto_articulacao: Point, ponto_aresta: Point, peso_original: float):
	"""
	Calcula um peso atrativo. Arestas mais próximas do ponto de articulação terão seu peso REDUZIDO, atraindo o caminho mais curto.
	"""
	distancia = ponto_articulacao.distance(ponto_aresta)  # Distância em metros

	# Fator de atração: 1 para pontos muito próximos, diminuindo para 0 para pontos distantes.
	# Ajuste 'distancia_max_influencia' para definir o raio de atração do ponto.
	distancia_max_influencia = 3000  # 3 km de raio de influência
	fator_atracao = max(0, 1 - (distancia / distancia_max_influencia))

	# Reduz o peso original com base na proximidade.
	# O fator 0.7 significa que o desconto máximo no custo da aresta é de 70%.
	desconto = fator_atracao * 0.7
	peso_com_desconto = peso_original * (1 - desconto)

	return peso_com_desconto


def criar_grafo_ponderado(gdf_vias: gpd.GeoDataFrame, ponto_articulacao: Point, sentido: Literal["IDA", "VOLTA"] = "IDA"):
	"""
	Cria o grafo a partir de um GeoDataFrame de vias JÁ PROJETADO.
	"""
	G = nx.MultiDiGraph()
	sentido_via = 1 if sentido == "IDA" else -1

	gdf_vias_filtradas = gdf_vias[(gdf_vias["Dir"] == sentido_via) | (gdf_vias["Dir"] == 0)]

	# Usar itertuples() é muito mais rápido que iterrows()
	for via in gdf_vias_filtradas.itertuples():
		if not via.geometry.is_valid or via.geometry.is_empty:
			continue

		ponto_inicio = via.geometry.coords[0]
		ponto_fim = via.geometry.coords[-1]
		peso_original = via.geometry.length  # Usar o comprimento da geometria projetada

		# Pondera o peso com base na proximidade do ponto médio da aresta
		ponto_medio_aresta = via.geometry.interpolate(0.5, normalized=True)
		peso_final = calcular_peso_atrativo(ponto_articulacao, ponto_medio_aresta, peso_original)

		atributos = {"weight": peso_final, "original_weight": peso_original}
		direcao = via.Dir

		if direcao == 0:
			G.add_edge(ponto_inicio, ponto_fim, **atributos)
			G.add_edge(ponto_fim, ponto_inicio, **atributos)
		elif direcao == 1:
			G.add_edge(ponto_inicio, ponto_fim, **atributos)
		elif direcao == -1:
			G.add_edge(ponto_fim, ponto_inicio, **atributos)

	print(f"Grafo direcionado criado com {G.number_of_nodes()} nós e {G.number_of_edges()} arestas.")
	return G


def encontrar_no_mais_proximo(ponto: Point, grafo: nx.Graph):
	"""Encontra o nó do grafo mais próximo de um ponto shapely."""
	if not grafo.nodes:
		raise ValueError("O grafo está vazio. Verifique os dados de entrada.")
	nos_grafo = list(grafo.nodes())
	pontos_nos = MultiPoint([Point(no) for no in nos_grafo])
	ponto_mais_proximo = nearest_points(ponto, pontos_nos)[1]
	return (ponto_mais_proximo.x, ponto_mais_proximo.y)


def encontrar_caminhos(
	gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, bairro_central: str = "Centro", sentido: Literal["IDA", "VOLTA"] = "IDA"
):
	bairro_destino = gdf_bairros[gdf_bairros["name"] == bairro_central]
	if bairro_destino.empty:
		raise ValueError(f"Bairro central '{bairro_central}' não encontrado.")

	ponto_bairro_central = bairro_destino.geometry.centroid.item()

	G = criar_grafo_ponderado(gdf_vias, ponto_bairro_central, sentido)

	# CORREÇÃO: Encontra o nó do GRAFO mais próximo do ponto central
	no_destino_grafo = encontrar_no_mais_proximo(ponto_bairro_central, G)

	lista_caminhos = []
	for row in gdf_bairros.itertuples():
		if row.name == bairro_central:
			continue

		ponto_origem = row.geometry.centroid
		no_origem_grafo = encontrar_no_mais_proximo(ponto_origem, G)

		try:
			source, target = (no_origem_grafo, no_destino_grafo) if sentido == "IDA" else (no_destino_grafo, no_origem_grafo)
			caminho = nx.dijkstra_path(G, source=source, target=target, weight="weight")
			lista_caminhos.append({"geometry": LineString(caminho), "name": row.name})
		except nx.NetworkXNoPath:
			print(f"AVISO: Nenhum caminho encontrado para o bairro '{row.name}'.")
			continue

	if not lista_caminhos:
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	return gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)


def plotar_rede(gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, gdf_caminhos: gpd.GeoDataFrame):
	fig, ax = plt.subplots(figsize=(12, 12))
	gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1, label="Malha Viária")
	gdf_bairros.plot(ax=ax, facecolor="none", edgecolor="red", zorder=2, label="Bairros")
	if not gdf_caminhos.empty:
		gdf_caminhos.plot(ax=ax, color="blue", linewidth=2.5, zorder=3, label="Caminho Otimizado")

	gdf_bairros.centroid.plot(ax=ax, color="black", marker="*", markersize=100, zorder=4, label="Centroides")

	ax.set_title("Análise de Rota com Ponderação por Proximidade")
	ax.set_xlabel("Leste (metros)")
	ax.set_ylabel("Norte (metros)")
	plt.legend()
	plt.grid(True)
	plt.show()


# --- Bloco Principal de Execução ---
if __name__ == "__main__":
	try:
		df_viario_pd = pd.read_csv("arquivos/grafo/SistemaViario.csv", encoding="ISO-8859-1")
		df_nodes_pd = pd.read_csv("arquivos/grafo/Node.csv")
		gdf_bairros_orig = gpd.read_file("arquivos/limites_bairros_moc/limites_bairros_moc.shp")
	except Exception as e:
		print(f"Erro ao ler os arquivos: {e}")
		exit()

	# --- ETAPA 1: Preparação e Projeção de Dados ---

	# Criar GeoDataFrame dos nós, definindo o CRS original como geográfico
	gdf_pontos = gpd.GeoDataFrame(
		df_nodes_pd, geometry=gpd.points_from_xy(df_nodes_pd["Longitude"] / 1e6, df_nodes_pd["Latitude"] / 1e6), crs=GEOGRAPHIC_CRS
	)

	df_merged = df_viario_pd.merge(df_nodes_pd.add_suffix("_from"), left_on="From ID", right_on="ID_from").merge(
		df_nodes_pd.add_suffix("_to"), left_on="To ID", right_on="ID_to"
	)

	gdf_vias = gpd.GeoDataFrame(
		df_merged,
		geometry=[
			LineString([(r.Longitude_from / 1e6, r.Latitude_from / 1e6), (r.Longitude_to / 1e6, r.Latitude_to / 1e6)]) for r in df_merged.itertuples()
		],
		crs=GEOGRAPHIC_CRS,
	)

	# PROJETAR TUDO para um CRS métrico antes de qualquer cálculo
	print(f"Projetando todos os dados para o CRS {PROJECTED_CRS}...")
	gdf_bairros_proj = gdf_bairros_orig.to_crs(PROJECTED_CRS)
	gdf_bairros_proj = gdf_bairros_proj[(gdf_bairros_proj["name"] == "Morrinhos") | (gdf_bairros_proj["name"] == "Centro")]
	gdf_vias_proj = gdf_vias.to_crs(PROJECTED_CRS)

	# gdf_vias_proj = gdf_vias_proj[(gdf_vias_proj["Dir"] == 1) | (gdf_vias_proj["Dir"] == 0)]

	caminhos = encontrar_caminhos(gdf_vias_proj, gdf_bairros_proj)

	# --- ETAPA 2: Análise ---

	# Filtrar bairros e vias para a análise
	bairros_analise = ["São José", "Centro"]
	gdf_bairros_analise = gdf_bairros_proj[gdf_bairros_proj["name"].isin(bairros_analise)]

	# Filtra vias que estão dentro da área de interesse para otimizar o grafo
	# vias_analise = gpd.sjoin(gdf_vias_proj, gdf_bairros_analise, how="inner", predicate="intersects")
	# vias_analise = vias_analise.drop_duplicates(subset=vias_analise.columns.difference(["index_right", "name"]))

	fig, ax = plt.subplots(figsize=(12, 12))

	# Criando o dicionário de cores para os valores 1, 0, -1
	cor_map = {1: "blue", 0: "green", -1: "red"}

	# Adicionando a coluna 'color' ao DataFrame com as cores baseadas na coluna 'Dir'
	gdf_vias_proj["color"] = gdf_vias_proj["Dir"].map(cor_map)

	# Plotando com as cores da coluna 'color'
	gdf_vias_proj.plot(ax=ax, color=gdf_vias_proj["color"], linewidth=0.5, zorder=1, label="Malha Viária")
	caminhos.plot(ax=ax)

	# gdf_bairros_analise.plot(ax=ax, facecolor="none", edgecolor="red", zorder=2, label="Bairros")
	# if not gdf_caminhos.empty:
	# 	gdf_caminhos.plot(ax=ax, color="blue", linewidth=2.5, zorder=3, label="Caminho Otimizado")

	gdf_bairros_analise.centroid.plot(ax=ax, color="black", marker="*", markersize=100, zorder=4, label="Centroides")

	ax.set_title("Análise de Rota com Ponderação por Proximidade")
	ax.set_xlabel("Leste (metros)")
	ax.set_ylabel("Norte (metros)")
	plt.legend()
	plt.grid(False)
	plt.show()

	# Executar a função principal de busca de caminhos
	# gdf_caminhos = encontrar_caminhos(vias_analise, gdf_bairros_analise, bairro_central="Centro", sentido="VOLTA")

	# --- ETAPA 3: Visualização ---
	# if not gdf_caminhos.empty:
	# print("\nCaminho(s) encontrado(s). Plotando o resultado...")
	# plotar_rede(vias_analise, gdf_bairros_analise, gdf_caminhos)
	# else:
	# print("\nNenhum caminho foi encontrado. Verifique a conectividade do grafo e os filtros.")
