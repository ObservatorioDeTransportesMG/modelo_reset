from typing import Literal

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import polars as pl
from shapely.geometry import LineString, MultiPoint, Point
from shapely.ops import nearest_points

from core.data_loader import ler_kml

# --- Definições Globais e de CRS ---
PROJECTED_CRS = "EPSG:31983"  # SIRGAS 2000 / UTM Zone 23S para Montes Claros
GEOGRAPHIC_CRS = "EPSG:4326"  # WGS 84 (padrão para lat/lon)

# --- Funções de Análise (Refatoradas) ---


def calcular_peso_atrativo(ponto_articulacao: Point, ponto_aresta: Point, peso_original: float):
	"""
	Calcula um peso atrativo. Arestas mais próximas do ponto de articulação terão seu peso reduzido, atraindo o caminho mais curto.
	"""
	distancia = ponto_articulacao.distance(ponto_aresta)  # Em metros, pois os dados estão projetados

	# Fator de atração: diminui linearmente de 1 (na articulação) a 0 (a 5km de distância)
	# Arestas a mais de 5km não recebem benefício. Ajuste 'distancia_max_influencia' conforme necessário.
	distancia_max_influencia = 5000  # 5 km
	fator_atracao = max(0, 1 - (distancia / distancia_max_influencia))

	# Reduz o peso original com base na proximidade.
	# O fator 0.5 significa que o desconto máximo é de 50%. Ajuste conforme o desejado.
	peso_com_desconto = peso_original * (1 - (fator_atracao * 0.5))

	return peso_com_desconto


def criar_grafo_ponderado(gdf_vias: gpd.GeoDataFrame, ponto_articulacao: Point, sentido: Literal["IDA", "VOLTA"] = "IDA"):
	"""
	Cria o grafo a partir de um GeoDataFrame de vias JÁ PROJETADO e ajusta o peso das arestas com base na proximidade de um ponto de articulação.
	"""
	G = nx.MultiDiGraph()
	# sentido_via = 1 if sentido == "IDA" else -1

	# gdf_vias_filtradas = gdf_vias[(gdf_vias["Dir"] == sentido_via) | (gdf_vias["Dir"] == 0)]

	for via in gdf_vias.itertuples():
		if not via.geometry.is_valid or via.geometry.is_empty:
			continue

		ponto_inicio = via.geometry.coords[0]
		ponto_fim = via.geometry.coords[-1]
		peso_original = via.Length  # Assumindo que a coluna de comprimento se chama "Length"

		# Pondera o peso da aresta com base na proximidade de seu ponto médio à articulação
		ponto_medio_aresta = via.geometry.interpolate(0.5, normalized=True)
		peso_final = calcular_peso_atrativo(ponto_articulacao, ponto_medio_aresta, peso_original)

		atributos = {"weight": peso_final, "original_weight": peso_original}
		direcao = via.Dir

		if direcao == 0:  # Mão dupla
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
		raise ValueError("O grafo não possui nós para a busca.")
	nos_grafo = list(grafo.nodes())
	pontos_nos = MultiPoint([Point(no) for no in nos_grafo])
	ponto_mais_proximo = nearest_points(ponto, pontos_nos)[1]
	return (ponto_mais_proximo.x, ponto_mais_proximo.y)


def encontrar_caminhos(
	gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, bairro_central: str = "Centro", sentido: Literal["IDA", "VOLTA"] = "IDA"
):
	"""
	Encontra o menor caminho de todos os bairros até o bairro de destino. Assume que TODOS os GeoDataFrames de entrada já estão no mesmo CRS PROJETADO.
	"""
	bairro_destino = gdf_bairros[gdf_bairros["name"] == bairro_central]
	if bairro_destino.empty:
		raise ValueError(f"Bairro central '{bairro_central}' não encontrado.")

	ponto_bairro_central = bairro_destino.geometry.centroid.item()

	G = criar_grafo_ponderado(gdf_vias, ponto_bairro_central, sentido)

	# CORREÇÃO: Encontra o nó do grafo mais próximo do ponto central
	no_destino_final = encontrar_no_mais_proximo(ponto_bairro_central, G)

	lista_caminhos = []
	for row in gdf_bairros.itertuples():
		if row.name == bairro_central or row.name != "Morrinhos":
			continue

		ponto_origem = row.geometry.centroid
		no_origem_inicial = encontrar_no_mais_proximo(ponto_origem, G)

		try:
			source, target = (no_origem_inicial, no_destino_final) if sentido == "IDA" else (no_destino_final, no_origem_inicial)
			caminho_mais_curto = nx.dijkstra_path(G, source=source, target=target, weight="weight")
			lista_caminhos.append({"geometry": LineString(caminho_mais_curto), "name": row.name})
		except nx.NetworkXNoPath:
			print(f"AVISO: Nenhum caminho encontrado para '{row.name}'.")
			continue

	if not lista_caminhos:
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)  # Retorna GDF vazio com CRS

	return gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)


def plotar_rede(gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, gdf_caminho_ida: gpd.GeoDataFrame, gdf_caminho_volta: gpd.GeoDataFrame):
	fig, ax = plt.subplots(figsize=(12, 12))
	gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1)
	gdf_bairros.plot(ax=ax, facecolor="none", edgecolor="red", zorder=2)

	gdf_caminho_ida.plot(ax=ax, color="blue", linewidth=2.5, zorder=3, label="Linhas Propostas (IDA)")
	gdf_caminho_volta.plot(ax=ax, color="green", linewidth=2.5, zorder=3, label="Linhas Propostas (VOLTA)")

	# Plota os centroides para visualização
	gdf_bairros.centroid.plot(ax=ax, color="black", marker="*", markersize=80, zorder=4, label="Centroides Bairros")

	ax.set_title("Análise de Rota com Ponderação por Proximidade")
	ax.set_xlabel("Leste (m)")
	ax.set_ylabel("Norte (m)")
	plt.legend()
	plt.grid(True)
	plt.show()


# --- Bloco Principal de Execução ---
if __name__ == "__main__":
	# 1. Carregar Dados
	try:
		df_viario_pl = pl.read_csv("arquivos/grafo/SistemaViario.csv", encoding="ISO-8859-1")
		df_nodes_pl = pl.read_csv("arquivos/grafo/Node.csv")
		df_pontos_articulacao = ler_kml("arquivos/pontos_articulacao.kml", GEOGRAPHIC_CRS)
		gdf_bairros_orig = gpd.read_file("arquivos/limites_bairros_moc/limites_bairros_moc.shp")
	except Exception as e:
		print(f"Erro ao ler os arquivos: {e}")
		exit()

	gdf_pontos = gpd.GeoDataFrame(geometry=gpd.points_from_xy(df_nodes_pl["Longitude"] / 1e6, df_nodes_pl["Latitude"] / 1e6), crs=GEOGRAPHIC_CRS)
	gdf_pontos["node_id"] = df_nodes_pl["ID"]

	df_viario_pd = df_viario_pl.to_pandas()
	df_nodes_pd = df_nodes_pl.to_pandas()

	nodes_from = df_nodes_pd.add_suffix("_from")
	nodes_to = df_nodes_pd.add_suffix("_to")

	df_merged = df_viario_pd.merge(nodes_from, left_on="From ID", right_on="ID_from").merge(nodes_to, left_on="To ID", right_on="ID_to")

	gdf_vias = gpd.GeoDataFrame(
		df_merged,
		geometry=[
			LineString([(lon_from / 1e6, lat_from / 1e6), (lon_to / 1e6, lat_to / 1e6)])
			for lon_from, lat_from, lon_to, lat_to in zip(
				df_merged["Longitude_from"], df_merged["Latitude_from"], df_merged["Longitude_to"], df_merged["Latitude_to"], strict=False
			)
		],
		crs=GEOGRAPHIC_CRS,
	)

	print(f"Projetando todos os dados para {PROJECTED_CRS}...")
	gdf_bairros_proj = gdf_bairros_orig.to_crs(PROJECTED_CRS)
	gdf_vias_proj = gdf_vias.to_crs(PROJECTED_CRS)

	# 4. Filtrar Bairros e Vias para a Análise
	gdf_bairros_proj = gdf_bairros_proj[gdf_bairros_proj["name"].isin(["Morrinhos", "Centro"])]
	# Opcional: filtrar vias que estão na área de análise para otimizar o grafo
	vias_na_area = gpd.sjoin(gdf_vias_proj, gdf_bairros_proj, how="inner", predicate="intersects")
	# vias_na_area = vias_na_area.drop_duplicates(subset=["ID_from"])  # Remove duplicatas por ID

	# fig, ax = plt.subplots(figsize=(12, 12))
	# vias_na_area.plot(ax=ax, color="gray", linewidth=0.5, zorder=1)
	# gdf_bairros_analise.plot(ax=ax, facecolor="none", edgecolor="red", zorder=2)

	# # Plota os centroides para visualização
	# gdf_bairros_analise.centroid.plot(ax=ax, color="black", marker="*", markersize=80, zorder=4, label="Centroides Bairros")

	# ax.set_title("Análise de Rota com Ponderação por Proximidade")
	# ax.set_xlabel("Leste (m)")
	# ax.set_ylabel("Norte (m)")
	# plt.legend()
	# plt.grid(True)
	# plt.show()

	# 5. Executar a Análise de Caminhos
	gdf_caminhos_ida = encontrar_caminhos(vias_na_area, gdf_bairros_proj, sentido="IDA")
	gdf_caminhos_volta = encontrar_caminhos(vias_na_area, gdf_bairros_proj, sentido="VOLTA")

	# 6. Plotar o Resultado
	plotar_rede(vias_na_area, gdf_bairros_proj, gdf_caminhos_ida, gdf_caminhos_volta)
