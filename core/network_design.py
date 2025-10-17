from typing import Literal

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
from shapely.geometry import LineString, MultiPoint, Point
from shapely.ops import nearest_points

# Define o CRS projetado para a região de Montes Claros (cálculos em metros)
PROJECTED_CRS = "EPSG:31983"


def criar_grafo(gdf_vias: gpd.GeoDataFrame) -> nx.MultiDiGraph:
	"""
	Cria o grafo a partir de um GeoDataFrame de vias JÁ PROJETADO.
	"""
	G = nx.MultiDiGraph()

	# itertuples() é significativamente mais rápido que iterrows()
	for via in gdf_vias.itertuples():
		# Ignora geometrias inválidas
		if not via.geometry.is_valid or via.geometry.is_empty:
			continue

		ponto_inicio = via.geometry.coords[0]
		ponto_fim = via.geometry.coords[-1]

		# O peso agora está em metros, o que é correto para o Dijkstra
		atributos = {"weight": via.geometry.length, "via_id": via.ID}
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

	# Otimização: pré-calcula os nós do grafo para a busca
	nos_multipoint = MultiPoint([Point(no) for no in grafo.nodes()])

	# CORREÇÃO: Extrai o objeto Point do GeoSeries usando .item()
	geometria_bairro_central = gdf_bairros[gdf_bairros["name"] == bairro_central].geometry.centroid.item()
	ponto_central = Point(geometria_bairro_central)
	no_central = encontrar_no_mais_proximo(Point(ponto_central), nos_multipoint)

	lista_caminhos = []
	for bairro in gdf_bairros.itertuples():
		# Pula o cálculo do caminho do bairro central para ele mesmo
		if bairro.name == bairro_central:
			continue

		ponto_bairro = bairro.geometry.centroid
		no_bairro = encontrar_no_mais_proximo(ponto_bairro, nos_multipoint)

		source, target = (no_bairro, no_central) if sentido == "IDA" else (no_central, no_bairro)

		try:
			caminho_mais_curto = nx.dijkstra_path(grafo, source=source, target=target, weight="weight")
			# CORREÇÃO: Adiciona o caminho à lista APENAS se ele for encontrado
			lista_caminhos.append({"geometry": LineString(caminho_mais_curto), "bairro_origem": bairro.name})
			print(f"Caminho encontrado para o bairro no sentido de {sentido}: {bairro.name}")
		except nx.NetworkXNoPath:
			print(f"Não foi possível encontrar um caminho para o bairro no sentido de {sentido}: {bairro.name}.")

	if not lista_caminhos:
		print("Aviso: Nenhum caminho foi gerado no total.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	return gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)


def plotar_caminhos(
	gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame, gdf_caminho_ida: gpd.GeoDataFrame, gdf_caminho_volta: gpd.GeoDataFrame
):
	fig, ax = plt.subplots(figsize=(12, 12))

	gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1, label="Sistema Viário")
	gdf_bairros.plot(ax=ax, facecolor="none", edgecolor="red", zorder=2, label="Limites dos Bairros")
	gdf_bairros.centroid.plot(ax=ax, color="black", marker="*", markersize=100, zorder=4, label="Centroides")

	gdf_caminho_ida.plot(ax=ax, color="blue", linewidth=2.5, zorder=3, label="Linhas Propostas (IDA)")
	gdf_caminho_volta.plot(ax=ax, color="green", linewidth=2.5, zorder=3, label="Linhas Propostas (VOLTA)")

	ax.set_title("Análise de Rota com Algoritmo de Dijkstra")
	ax.set_xlabel("Coordenada Leste (metros)")
	ax.set_ylabel("Coordenada Norte (metros)")
	ax.legend()
	plt.grid(True)
	plt.show()


if __name__ == "__main__":
	try:
		gdf_vias_orig = gpd.read_file("arquivos/Shapes para Mapas/Sistema viario.shp")
		gdf_bairros_orig = gpd.read_file("arquivos/limites_bairros_moc/limites_bairros_moc.shp")
	except Exception as e:
		print(f"Erro ao ler os arquivos shapefile: {e}")
		exit()

	# --- ETAPA 1: Projeção de CRS (Passo mais importante) ---
	print(f"Projetando dados para o CRS métrico: {PROJECTED_CRS}")
	gdf_vias_proj = gdf_vias_orig.to_crs(PROJECTED_CRS)
	gdf_bairros_proj = gdf_bairros_orig.to_crs(PROJECTED_CRS)
	gdf_bairros_proj = gdf_bairros_proj[(gdf_bairros_proj["name"] == "Morrinhos") | (gdf_bairros_proj["name"] == "Centro")]

	# --- ETAPA 2: Filtragem de Dados ---
	# Filtra as vias para conter apenas as que cruzam os bairros de interesse.
	# Isso torna o grafo menor e mais relevante para a análise.
	vias_filtradas = gpd.sjoin(gdf_vias_proj, gdf_bairros_proj, how="inner", predicate="intersects")
	# Remove duplicatas de vias que podem cruzar a fronteira de múltiplos bairros
	vias_filtradas = vias_filtradas.drop_duplicates(subset="ID")

	# --- ETAPA 3: Análise de Rede ---
	print("\nIniciando a criação do grafo...")
	grafo = criar_grafo(vias_filtradas)

	print("\nCalculando os caminhos mínimos...")
	caminhos_volta = encontrar_caminho_minimo(gdf_bairros_proj, grafo, sentido="VOLTA")
	caminhos_ida = encontrar_caminho_minimo(gdf_bairros_proj, grafo, sentido="IDA")

	# --- ETAPA 4: Visualização ---
	if not caminhos_volta.empty and not caminhos_ida.empty:
		plotar_caminhos(vias_filtradas, gdf_bairros_proj, caminhos_ida, caminhos_volta)
	else:
		print("\nAnálise concluída, mas nenhum caminho foi encontrado para plotar.")
