from typing import Literal

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
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


def criar_grafo_ponderado(gdf_vias: gpd.GeoDataFrame, gdf_pontos_articulacao: gpd.GeoDataFrame):
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
			if isinstance(via.LENGTH, (int, float)):
				peso_original = float(via.LENGTH)
			else:
				print(f"Erro: 'via.LENGTH' não é numérico! Tipo encontrado: {type(via.LENGTH)}")
				peso_original = 0

			ponto_medio_aresta = via.geometry.interpolate(0.5, normalized=True)

			_, ponto_articulacao_mais_proximo = nearest_points(ponto_medio_aresta, todos_os_pontos_articulacao)

			peso_final = calcular_peso_atrativo(ponto_articulacao_mais_proximo, ponto_medio_aresta, peso_original)

			atributos = {"weight": peso_final, "original_weight": peso_original}
			direcao = via.DIR

			if direcao == 0:
				G.add_edge(ponto_inicio, ponto_fim, **atributos)
				G.add_edge(ponto_fim, ponto_inicio, **atributos)
			elif direcao == 1:
				G.add_edge(ponto_inicio, ponto_fim, **atributos)
			elif direcao == -1:
				G.add_edge(ponto_fim, ponto_inicio, **atributos)

	print(f"Grafo direcionado criado com {G.number_of_nodes()} nós e {G.number_of_edges()} arestas.")
	return G


def encontrar_no_mais_proximo(ponto: Point, nos_grafo_multipoint: MultiPoint):
	"""
	Encontra o Nó mais próximo de forma otimizada, recebendo um MultiPoint pré-calculado.
	"""
	ponto_mais_proximo = nearest_points(ponto, nos_grafo_multipoint)[1]
	return (ponto_mais_proximo.x, ponto_mais_proximo.y)


def encontrar_caminho_minimo(
	gdf_bairros: gpd.GeoDataFrame, grafo: nx.MultiDiGraph, bairro_central: str = "Centro", sentido: Literal["IDA", "VOLTA"] = "IDA"
) -> gpd.GeoDataFrame:
	"""
	Encontra o caminho mínimo entre os centroides dos bairros e um bairro central.

	Assume que TODOS os dados de entrada estão em um CRS projetado.
	"""
	if grafo.number_of_nodes() == 0:
		print("Aviso: O grafo está vazio. Nenhum caminho pode ser calculado.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	nos_multipoint = MultiPoint([Point(no) for no in grafo.nodes()])
	bairro_destino = gdf_bairros[gdf_bairros["name"] == bairro_central]

	ponto_bairro_central = bairro_destino.geometry.centroid.item()

	if not isinstance(ponto_bairro_central, Point):
		raise ValueError("Ponto central não encontrado")

	no_central = encontrar_no_mais_proximo(ponto_bairro_central, nos_multipoint)

	lista_caminhos = []
	for index, bairro in enumerate(gdf_bairros.itertuples()):
		if bairro.name == bairro_central:
			continue

		if not isinstance(bairro.geometry, Polygon):
			continue

		ponto_bairro = bairro.geometry.centroid
		no_bairro = encontrar_no_mais_proximo(ponto_bairro, nos_multipoint)

		source, target = (no_bairro, no_central) if sentido == "IDA" else (no_central, no_bairro)

		linha_id = f"{index}{sentido[0]}"

		try:
			caminho_mais_curto = nx.dijkstra_path(grafo, source=source, target=target, weight="weight")
			lista_caminhos.append({"geometry": LineString(caminho_mais_curto), "bairro_origem": bairro.name, "id": linha_id})
		except nx.NetworkXNoPath:
			print(f"Não foi possível encontrar um caminho para o bairro no sentido de {sentido}: {bairro.name}.")

	if not lista_caminhos:
		print("Aviso: Nenhum caminho foi gerado no total.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	return gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)


def plotar_caminhos(
	gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, gdf_caminho_ida: gpd.GeoDataFrame, gdf_caminho_volta: gpd.GeoDataFrame
):
	"""
	Função responsável por fazer a plotagem dos caminhos.
	"""
	fig, ax = plt.subplots(figsize=(12, 12))

	gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1, label="Sistema Viário")
	gdf_bairros.plot(ax=ax, facecolor="none", edgecolor="red", zorder=2, label="Limites dos Bairros")
	gdf_bairros.centroid.plot(ax=ax, color="black", marker="*", markersize=100, zorder=4, label="Centroides")

	gdf_caminho_ida.plot(ax=ax, color="blue", linewidth=2.5, zorder=3, label="Linhas Propostas (IDA)")
	gdf_caminho_volta.plot(ax=ax, color="green", linewidth=2.5, zorder=3, label="Linhas Propostas (VOLTA)")

	ax.set_title("Análise de Rota com Algoritmo de Dijkstra")
	ax.set_xlabel("Coordenada Leste (metros)")
	ax.set_ylabel("Coordenada Norte (metros)")
	# ax.legend()
	plt.grid(True)
	plt.show()


def plotar_caminhos2(
	gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, gdf_caminho_ida: gpd.GeoDataFrame, gdf_caminho_volta: gpd.GeoDataFrame
):
	"""
	Função responsável por fazer a plotagem dos caminhos, com cada linha tendo uma cor única referenciada pelo seu ID na legenda.
	"""
	fig, ax = plt.subplots(figsize=(12, 12))

	gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1, label="Sistema Viário")
	gdf_bairros.plot(ax=ax, facecolor="none", edgecolor="none", zorder=2, label="Limites dos Bairros")
	gdf_bairros.centroid.plot(ax=ax, color="black", marker="*", markersize=100, zorder=4, label="Centroides")

	gdf_caminhos = gpd.pd.concat([gdf_caminho_ida, gdf_caminho_volta])

	lista_ids = gdf_caminhos["id"].unique()

	import matplotlib

	cores = matplotlib.colormaps.get_cmap("hsv")

	mapa_cores = {linha_id: cores(i) for i, linha_id in enumerate(lista_ids)}

	for _, caminho in gdf_caminhos.iterrows():
		linha_id = caminho["id"]
		cor = mapa_cores[linha_id]

		gpd.GeoSeries(caminho.geometry, crs=gdf_caminhos.crs).plot(
			ax=ax,
			color=cor,
			linewidth=2.5,
			zorder=3,
			label=f"ID: {linha_id} ({caminho['bairro_origem']})",  # Rótulo para a legenda
		)

	ax.set_title("Análise de Rota com Algoritmo de Dijkstra")
	ax.set_xlabel("Coordenada Leste (metros)")
	ax.set_ylabel("Coordenada Norte (metros)")

	# ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1), borderaxespad=0.0, ncols=3)

	plt.tight_layout()
	plt.grid(True)
	plt.show()


if __name__ == "__main__":
	try:
		gdf_vias_orig = gpd.read_file("arquivos/Shapes para Mapas/Sistema viario.shp")
		gdf_bairros_orig = gpd.read_file("arquivos/limites_bairros_moc/limites_bairros_moc.shp")
		gdf_pontos_articulacao_orig = ler_kml("arquivos/pontos_articulacao.kml", GEOGRAPHIC_CRS)

	except Exception as e:
		print(f"Erro ao ler os arquivos shapefile: {e}")
		exit()

	print(f"Projetando dados para o CRS métrico: {PROJECTED_CRS}")
	gdf_vias_proj = gdf_vias_orig.to_crs(PROJECTED_CRS)
	gdf_bairros_proj = gdf_bairros_orig.to_crs(PROJECTED_CRS)
	gdf_pontos_articulacao_proj = gdf_pontos_articulacao_orig.to_crs(PROJECTED_CRS)
	# gdf_bairros_proj = gdf_bairros_proj[gdf_bairros_proj["name"].isin(["Morrinhos", "Centro"])]

	vias_filtradas = gpd.sjoin(gdf_vias_proj, gdf_bairros_proj, how="inner", predicate="intersects")
	vias_filtradas = vias_filtradas.drop_duplicates(subset="ID")

	print("\nIniciando a criação do grafo...")
	grafo = criar_grafo_ponderado(vias_filtradas, gdf_pontos_articulacao_proj)

	print("\nCalculando os caminhos mínimos...")
	caminhos_volta = encontrar_caminho_minimo(gdf_bairros_proj, grafo, sentido="VOLTA")
	caminhos_ida = encontrar_caminho_minimo(gdf_bairros_proj, grafo, sentido="IDA")

	if not caminhos_volta.empty and not caminhos_ida.empty:
		plotar_caminhos2(vias_filtradas, gdf_bairros_proj, caminhos_ida, caminhos_volta)
	else:
		print("\nAnálise concluída, mas nenhum caminho foi encontrado para plotar.")
