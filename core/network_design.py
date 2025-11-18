from typing import Literal, Optional

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
from shapely.geometry import LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon
from shapely.ops import nearest_points

from core.data_loader import ler_kml

PROJECTED_CRS = "EPSG:31983"
GEOGRAPHIC_CRS = "EPSG:4326"


def filtrar_vias_por_bairros(gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
	"""
	Filtra o GeoDataFrame de vias para incluir apenas aquelas que intersectam a área dos bairros.
	"""
	vias_filtradas = gpd.sjoin(gdf_vias, gdf_bairros, how="inner", predicate="intersects")
	vias_filtradas = vias_filtradas.drop_duplicates(subset="ID")
	return vias_filtradas


def calcular_peso_atrativo(ponto_articulacao: Point, ponto_aresta: Point, peso_original: float):
	"""
	Calcula um peso atrativo. Arestas mais próximas do ponto de articulação terão seu peso reduzido, atraindo o caminho mais curto.
	"""
	distancia = ponto_articulacao.distance(ponto_aresta)

	distancia_max_influencia = 1000
	fator_atracao = max(0, 1 - (distancia / distancia_max_influencia))

	peso_com_desconto = peso_original * (1 - (fator_atracao * 0.5))

	return peso_com_desconto


def criacao_arestas(grafo: nx.MultiDiGraph, linha: LineString, todos_os_pontos_articulacao: MultiPoint, via_id_principal: int, direcao: int):
	"""
	Função responsável por criar as arestas.
	"""
	coordenadas = list(linha.coords)

	for i in range(len(coordenadas) - 1):
		ponto_inicio_segmento = coordenadas[i]
		ponto_fim_segmento = coordenadas[i + 1]

		segmento = LineString([ponto_inicio_segmento, ponto_fim_segmento])
		peso_original_segmento = segmento.length

		if peso_original_segmento == 0:
			continue

		ponto_medio_segmento = segmento.interpolate(0.5, normalized=True)
		_, ponto_articulacao_mais_proximo = nearest_points(ponto_medio_segmento, todos_os_pontos_articulacao)

		peso_final_segmento = calcular_peso_atrativo(ponto_articulacao_mais_proximo, ponto_medio_segmento, peso_original_segmento)

		atributos = {"weight": peso_final_segmento, "original_weight": peso_original_segmento, "via_id": via_id_principal}

		if direcao == 0:
			grafo.add_edge(ponto_inicio_segmento, ponto_fim_segmento, **atributos)
			grafo.add_edge(ponto_fim_segmento, ponto_inicio_segmento, **atributos)
		elif direcao == 1:
			grafo.add_edge(ponto_inicio_segmento, ponto_fim_segmento, **atributos)
		elif direcao == -1:
			grafo.add_edge(ponto_fim_segmento, ponto_inicio_segmento, **atributos)


def criar_grafo_ponderado(gdf_vias: gpd.GeoDataFrame, gdf_pontos_articulacao: gpd.GeoDataFrame) -> nx.MultiDiGraph:
	"""
	Cria o grafo a partir de um GeoDataFrame de vias JÁ PROJETADO.

	Esta versão "explode" cada LineString em seus segmentos constituintes,
	criando uma aresta para CADA segmento.

	A ponderação de atratividade é aplicada individualmente a cada segmento.
	"""
	grafo = nx.MultiDiGraph()

	if gdf_pontos_articulacao.empty:
		raise ValueError("O GeoDataFrame de pontos de articulação está vazio.")

	todos_os_pontos_articulacao = MultiPoint(gdf_pontos_articulacao.geometry.union_all())  # type: ignore

	for via in gdf_vias.itertuples():
		geometrias = []
		if isinstance(via.geometry, LineString):
			geometrias = [via.geometry]
		elif isinstance(via.geometry, MultiLineString):
			geometrias = list(via.geometry.geoms)

		if not geometrias or not all(g.is_valid and not g.is_empty for g in geometrias):
			continue

		direcao = via.DIR
		via_id_principal = via.ID

		if not isinstance(direcao, int) or not isinstance(via_id_principal, int):
			raise ValueError("Erro na direção ou no id da via")

		for linha in geometrias:
			criacao_arestas(grafo, linha, todos_os_pontos_articulacao, via_id_principal, direcao)

	print(f"Grafo direcionado criado com {grafo.number_of_nodes()} nós e {grafo.number_of_edges()} arestas.")
	return grafo


def encontrar_no_mais_proximo(ponto: Point, nos_grafo_multipoint: MultiPoint):
	"""
	Encontra o Nó mais próximo de forma otimizada, recebendo um MultiPoint pré-calculado.
	"""
	ponto_mais_proximo = nearest_points(ponto, nos_grafo_multipoint)[1]
	return (ponto_mais_proximo.x, ponto_mais_proximo.y)


def filtrar_sublinhas(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
	"""
	Remove eficientemente as geometrias de LineString que são "sublinhas", ou seja, que estão completamente contidas dentro de outras LineStrings no mesmo GeoDataFrame.

	Usa uma junção espacial (sjoin) para performance.
	"""
	if gdf.empty:
		print("Geodataframe das linhas vazio.")
		return gdf

	gdf_com_buffer = gdf.copy()
	gdf_com_buffer.geometry = gdf.geometry.buffer(1e-2)

	gdf_sjoined = gpd.sjoin(gdf, gdf_com_buffer, how="left", predicate="within")

	linhas_contidas = gdf_sjoined[gdf_sjoined.index != gdf_sjoined["index_right"]]

	indices_das_sublinhas = linhas_contidas.index.unique()

	gdf_filtrado = gdf.drop(index=indices_das_sublinhas)

	print(f"Linhas originais: {len(gdf)} | Sublinhas removidas: {len(indices_das_sublinhas)} | Linhas finais: {len(gdf_filtrado)}")

	return gdf_filtrado


def encontrar_caminho_minimo(
	gdf_bairros: gpd.GeoDataFrame, grafo: nx.MultiDiGraph, bairro_central: Optional[str] = None, sentido: Literal["IDA", "VOLTA"] = "IDA"
) -> gpd.GeoDataFrame:
	"""
	Encontra o caminho mínimo entre os centroides dos bairros e um bairro central.

	Assume que TODOS os dados de entrada estão em um CRS projetado.
	"""
	if grafo.number_of_nodes() == 0:
		print("Aviso: O grafo está vazio. Nenhum caminho pode ser calculado.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	nos_multipoint = MultiPoint([Point(no) for no in grafo.nodes()])

	ponto_bairro_central = gdf_bairros.centroid

	if bairro_central:
		bairro_destino = gdf_bairros[gdf_bairros["name"] == bairro_central]
		if bairro_destino.empty:
			raise ValueError(f"Bairro central '{bairro_central}' não encontrado.")
		ponto_bairro_central = bairro_destino.geometry.centroid.item()
	else:
		print("Nenhum bairro central especificado. Usando o centroide de toda a área de estudo.")
		area_total = gdf_bairros.geometry.union_all()
		ponto_bairro_central = area_total.centroid

	if not isinstance(ponto_bairro_central, Point):
		raise ValueError("Ponto central não encontrado")

	no_central = encontrar_no_mais_proximo(ponto_bairro_central, nos_multipoint)

	lista_caminhos = []
	for index, bairro in enumerate(gdf_bairros.itertuples()):
		if bairro_central and bairro.name == bairro_central:
			continue

		if not isinstance(bairro.geometry, (Polygon, MultiPolygon)):
			continue

		ponto_bairro = bairro.geometry.centroid
		no_bairro = encontrar_no_mais_proximo(ponto_bairro, nos_multipoint)

		source, target = (no_bairro, no_central) if sentido == "IDA" else (no_central, no_bairro)

		linha_id = f"{index}{sentido[0]}"

		try:
			caminho_mais_curto = nx.dijkstra_path(grafo, source=source, target=target, weight="weight")
			if len(caminho_mais_curto) < 2:
				continue
			lista_caminhos.append({"geometry": LineString(caminho_mais_curto), "id": linha_id})
		except nx.NetworkXNoPath:
			print(f"Não foi possível encontrar um caminho para o bairro no sentido de {sentido} e index {index}")
			continue

	if not lista_caminhos:
		print("Aviso: Nenhum caminho foi gerado no total.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	gdf_rotas_brutas = gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)

	print(f"Filtrando sublinhas para o sentido: {sentido}")
	gdf_rotas_filtradas = filtrar_sublinhas(gdf_rotas_brutas)

	return gdf_rotas_filtradas


def plotar_caminhos(
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

	if gdf_caminhos.crs is None or not isinstance(gdf_caminhos, gpd.GeoDataFrame):
		raise ValueError("Erro com o CRS do geoDataframes dos caminhos")

	lista_ids = gdf_caminhos["id"].unique()

	import matplotlib

	cores = matplotlib.colormaps.get_cmap("hsv")

	mapa_cores = {linha_id: cores(i) for i, linha_id in enumerate(lista_ids)}

	for _, caminho in gdf_caminhos.iterrows():
		linha_id = caminho["id"]
		cor = mapa_cores[linha_id]

		gpd.GeoSeries(caminho.geometry, crs=gdf_caminhos.crs).plot(
			ax=ax, color=cor, linewidth=2.5, zorder=3, label=f"ID: {linha_id} ({caminho['bairro_origem']})"
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
		pass
	else:
		print("\nAnálise concluída, mas nenhum caminho foi encontrado para plotar.")
