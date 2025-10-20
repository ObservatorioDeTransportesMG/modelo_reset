from typing import Literal, Optional

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import polars as pl
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import nearest_points

from core.data_loader import ler_kml

PROJECTED_CRS = "EPSG:31983"
GEOGRAPHIC_CRS = "EPSG:4326"


def calcular_peso_atrativo(ponto_articulacao: Point, ponto_aresta: Point, peso_original: float):
	"""
	Calcula um peso atrativo. Arestas mais próximas do ponto de articulação terão seu peso reduzido, atraindo o caminho mais curto.
	"""
	distancia = ponto_articulacao.distance(ponto_aresta)

	distancia_max_influencia = 1000
	fator_atracao = max(0, 1 - (distancia / distancia_max_influencia))

	peso_com_desconto = peso_original * (1 - (fator_atracao * 0.5))

	return peso_com_desconto


def criar_grafo_ponderado(gdf_vias: gpd.GeoDataFrame, gdf_pontos_articulacao: gpd.GeoDataFrame, sentido: Literal["IDA", "VOLTA"] = "IDA"):
	"""
	Cria o grafo a partir de um GeoDataFrame de vias JÁ PROJETADO e ajusta o peso das arestas.

	com base na proximidade do PONTO DE ARTICULAÇÃO MAIS PRÓXIMO.
	"""
	G = nx.MultiDiGraph()

	if gdf_pontos_articulacao.empty:
		raise ValueError("O GeoDataFrame de pontos de articulação está vazio.")

	todos_os_pontos_articulacao = MultiPoint(gdf_pontos_articulacao.geometry.union_all())  # type: ignore

	for via in gdf_vias.itertuples():
		if isinstance(via.geometry, LineString):
			if not via.geometry.is_valid or via.geometry.is_empty:
				continue

			ponto_inicio = via.geometry.coords[0]
			ponto_fim = via.geometry.coords[-1]
			if isinstance(via.Length, (int, float)):  # Verifica se é um número inteiro ou float
				peso_original = float(via.Length)
			else:
				print(f"Erro: 'via.Length' não é numérico! Tipo encontrado: {type(via.Length)}")
				peso_original = 0

			ponto_medio_aresta = via.geometry.interpolate(0.5, normalized=True)

			_, ponto_articulacao_mais_proximo = nearest_points(ponto_medio_aresta, todos_os_pontos_articulacao)

			peso_final = calcular_peso_atrativo(ponto_articulacao_mais_proximo, ponto_medio_aresta, peso_original)

			atributos = {"weight": peso_final, "original_weight": peso_original}
			direcao = via.Dir

			if direcao == 0:
				G.add_edge(ponto_inicio, ponto_fim, **atributos)
				G.add_edge(ponto_fim, ponto_inicio, **atributos)
			elif direcao == 1:
				G.add_edge(ponto_inicio, ponto_fim, **atributos)
			elif direcao == -1:
				G.add_edge(ponto_fim, ponto_inicio, **atributos)

	print(f"Grafo direcionado ('{sentido}') criado com {G.number_of_nodes()} nós e {G.number_of_edges()} arestas.")
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
	gdf_vias: gpd.GeoDataFrame,
	gdf_bairros: gpd.GeoDataFrame,
	gdf_pontos_articulacao: gpd.GeoDataFrame,
	bairro_central: str = "Centro",
	sentido: Literal["IDA", "VOLTA"] = "IDA",
):
	"""
	Encontra o menor caminho de todos os bairros até o bairro de destino. Assume que TODOS os GeoDataFrames de entrada já estão no mesmo CRS PROJETADO.
	"""
	bairro_destino = gdf_bairros[gdf_bairros["name"] == bairro_central]
	if bairro_destino.empty:
		raise ValueError(f"Bairro central '{bairro_central}' não encontrado.")

	ponto_bairro_central = bairro_destino.geometry.centroid.item()

	G = criar_grafo_ponderado(gdf_vias, gdf_pontos_articulacao, sentido)

	if not isinstance(ponto_bairro_central, Point):
		return

	no_destino_final = encontrar_no_mais_proximo(ponto_bairro_central, G)

	lista_caminhos = []
	for row in gdf_bairros.itertuples():
		if row.name == bairro_central:
			continue

		if not isinstance(row.geometry, Polygon):
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
		# TODO resovler esse problema, não é possível retornar assim
		return gpd.GeoDataFrame()

	return gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)


def plotar_rede(
	gdf_vias: gpd.GeoDataFrame,
	gdf_bairros: gpd.GeoDataFrame,
	gdf_pontos_articulacao: gpd.GeoDataFrame,
	gdf_caminho_ida: Optional[gpd.GeoDataFrame] = None,
	gdf_caminho_volta: Optional[gpd.GeoDataFrame] = None,
):
	"""
	Função responsável por fazer a pltoagem.
	"""
	fig, ax = plt.subplots(figsize=(12, 12))
	gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1)
	gdf_bairros.plot(ax=ax, facecolor="none", edgecolor="none", zorder=2)

	if gdf_caminho_ida is not None:
		gdf_caminho_ida.plot(ax=ax, color="blue", linewidth=2.5, zorder=3, label="Linhas Propostas (IDA)")
	if gdf_caminho_volta is not None:
		gdf_caminho_volta.plot(ax=ax, color="green", linewidth=2.5, zorder=4, label="Linhas Propostas (VOLTA)")

	gdf_bairros.centroid.plot(ax=ax, color="black", marker="*", markersize=80, zorder=5, label="Centroides Bairros")

	gdf_buffers = gdf_pontos_articulacao.buffer(1000)
	gdf_buffers.plot(ax=ax, color="lightblue", alpha=0.5, label="Área de Abrangência (100m)")
	gdf_pontos_articulacao.plot(ax=ax, color="purple", marker="X", markersize=100, zorder=6, label="Pontos de Articulação")

	ax.set_title("Análise de Rota com Ponderação por Proximidade a Pontos de Articulação")
	ax.set_xlabel("Leste (m)")
	ax.set_ylabel("Norte (m)")
	# ax.legend(handles=[gdf_buffers, gdf_pontos_articulacao, gdf_caminho_ida, gdf_caminho_volta])
	plt.grid(True)
	plt.show()


if __name__ == "__main__":
	try:
		df_viario_pl = pl.read_csv("arquivos/grafo/SistemaViario.csv", encoding="ISO-8859-1")
		df_nodes_pl = pl.read_csv("arquivos/grafo/Node.csv")
		gdf_pontos_articulacao_orig = ler_kml("arquivos/pontos_articulacao.kml", GEOGRAPHIC_CRS)
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
	gdf_pontos_articulacao_proj = gdf_pontos_articulacao_orig.to_crs(PROJECTED_CRS)

	# gdf_bairros_proj = gdf_bairros_proj[gdf_bairros_proj["name"].isin(["Morrinhos", "Centro"])]
	# gdf_vias_proj = gpd.sjoin(gdf_vias_proj, gdf_bairros_proj, how="inner", predicate="intersects")

	gdf_caminhos_ida = encontrar_caminhos(gdf_vias_proj, gdf_bairros_proj, gdf_pontos_articulacao_proj, bairro_central="Centro", sentido="IDA")
	gdf_caminhos_volta = encontrar_caminhos(gdf_vias_proj, gdf_bairros_proj, gdf_pontos_articulacao_proj, bairro_central="Centro", sentido="VOLTA")

	plotar_rede(gdf_vias_proj, gdf_bairros_proj, gdf_pontos_articulacao_proj, gdf_caminhos_ida, gdf_caminhos_volta)
