from typing import Literal, Optional

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, MultiLineString, MultiPoint, Point
from shapely.ops import nearest_points

from .data_loader import ler_kml

PROJECTED_CRS = "EPSG:31983"
GEOGRAPHIC_CRS = "EPSG:4326"


def filtrar_vias_por_bairros(gdf_vias: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
	"""
	Filtra o GeoDataFrame de vias para incluir apenas aquelas que intersectam a área dos bairros.
	"""
	vias_filtradas = gpd.sjoin(gdf_vias, gdf_bairros, how="inner", predicate="intersects")
	vias_filtradas = vias_filtradas.drop_duplicates(subset="ID")
	return vias_filtradas


def calcular_peso_atrativo(ponto_articulacao: Point, ponto_aresta: Point, centroid_bairro: Point, peso_original: float, tipo_bairro: str = "Nenhum"):
	"""
	Calcula o peso da aresta aplicando descontos cumulativos baseados na proximidade de pontos de articulação e do centro do bairro, com preferência por tipo de bairro.
	"""
	distancia_articulacao = ponto_articulacao.distance(ponto_aresta)
	desconto_articulacao = _desconto_ponto_articulacao(distancia_articulacao)

	if tipo_bairro == "Emergente":
		raio_influencia = 2000
		max_desconto = 0.5
	elif tipo_bairro == "Consolidado":
		raio_influencia = 1500
		max_desconto = 0.3
	elif tipo_bairro == "Planejado":
		raio_influencia = 1000
		max_desconto = 0.1
	else:
		raio_influencia = 1
		max_desconto = 0.0

	distancia_polo = centroid_bairro.distance(ponto_aresta)
	desconto_polo = _desconto_polo(distancia_polo, raio_influencia, max_desconto)

	desconto_total = desconto_articulacao + desconto_polo - (desconto_articulacao * desconto_polo)

	peso_final = peso_original * (1 - desconto_total)
	return max(peso_final, 0.1)


def _desconto_ponto_articulacao(distancia: float) -> float:
	"""
	Calcula um peso atrativo. Arestas mais próximas do ponto de articulação terão seu peso reduzido, atraindo o caminho mais curto.
	"""
	fator_articulacao = max(0, 1 - (distancia / 1000))

	return fator_articulacao * 0.4


def _desconto_polo(distancia: float, raio_influencia: int, max_desconto: float) -> float:
	"""
	Calcula o peso atrativo com o centroid do bairro.
	"""
	fator_polo = max(0, 1 - (distancia / raio_influencia))
	return fator_polo * max_desconto


def criacao_arestas(
	grafo: nx.MultiDiGraph,
	linha: LineString,
	todos_os_pontos_articulacao: MultiPoint,
	centroid_bairros: MultiPoint,
	lista_tipos_bairros: list,
	via_id_principal: int,
	direcao: int,
):
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

		dists_pontos_articulacao = [p.distance(ponto_medio_segmento) for p in todos_os_pontos_articulacao.geoms]
		idx_ponto_articulacao_mais_proximo = dists_pontos_articulacao.index(min(dists_pontos_articulacao))
		dists_bairro = [p.distance(ponto_medio_segmento) for p in centroid_bairros.geoms]
		idx_bairro_mais_proximo = dists_bairro.index(min(dists_bairro))

		centroid_mais_proximo = centroid_bairros.geoms[idx_bairro_mais_proximo]
		ponto_articulacao_mais_proximo = todos_os_pontos_articulacao.geoms[idx_ponto_articulacao_mais_proximo]
		tipo_bairro_atual = lista_tipos_bairros[idx_bairro_mais_proximo]

		peso_final_segmento = calcular_peso_atrativo(
			ponto_articulacao_mais_proximo, ponto_medio_segmento, centroid_mais_proximo, peso_original_segmento, tipo_bairro=tipo_bairro_atual
		)

		atributos = {"weight": peso_final_segmento, "original_weight": peso_original_segmento, "via_id": via_id_principal}

		if direcao == 0:
			grafo.add_edge(ponto_inicio_segmento, ponto_fim_segmento, **atributos)
			grafo.add_edge(ponto_fim_segmento, ponto_inicio_segmento, **atributos)
		elif direcao == 1:
			grafo.add_edge(ponto_inicio_segmento, ponto_fim_segmento, **atributos)
		elif direcao == -1:
			grafo.add_edge(ponto_fim_segmento, ponto_inicio_segmento, **atributos)


def criar_grafo_ponderado(gdf_vias: gpd.GeoDataFrame, gdf_pontos_articulacao: gpd.GeoDataFrame, gdf_bairros: gpd.GeoDataFrame) -> nx.MultiDiGraph:
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
	bairros_relevantes = gdf_bairros[gdf_bairros["tipo_polo"].isin(["Emergente", "Consolidado"])]
	centroids_bairros = MultiPoint(bairros_relevantes.centroid.geometry.union_all())  # type: ignore
	lista_tipos_bairros = bairros_relevantes["tipo_polo"].tolist()

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
			criacao_arestas(grafo, linha, todos_os_pontos_articulacao, centroids_bairros, lista_tipos_bairros, via_id_principal, direcao)

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


def _obter_ponto_central(gdf_bairros: gpd.GeoDataFrame, nome_bairro_central: Optional[str]) -> Point:
	"""
	Determina a geometria do ponto central (hub). Se um nome for fornecido, usa o centroide desse bairro. Caso contrário, usa o centroide da área total.
	"""
	if nome_bairro_central:
		nome_limpo = nome_bairro_central.strip()
		bairro_destino = gdf_bairros[gdf_bairros["name"].str.strip() == nome_limpo]

		if bairro_destino.empty:
			raise ValueError(f"Bairro central '{nome_limpo}' não encontrado.")

		ponto = bairro_destino.geometry.centroid.item()
	else:
		print("Nenhum bairro central especificado. Usando o centroide de toda a área de estudo.")
		area_total = gdf_bairros.geometry.unary_union
		ponto = area_total.centroid

	if not isinstance(ponto, Point):
		raise ValueError("Falha ao determinar o ponto central (geometria inválida).")

	return ponto


def _calcular_rota_individual(
	grafo: nx.MultiDiGraph, no_origem: tuple[float, float], no_destino: tuple[float, float], sentido: Literal["IDA", "VOLTA"]
) -> Optional[LineString]:
	"""
	Calcula o caminho mínimo entre dois nós do grafo e retorna a LineString. Retorna None se não houver caminho ou se o caminho for trivial (ponto único).
	"""
	source, target = (no_origem, no_destino) if sentido == "IDA" else (no_destino, no_origem)

	try:
		caminho_nos = nx.dijkstra_path(grafo, source=source, target=target, weight="weight")

		if len(caminho_nos) < 2:
			return None

		return LineString(caminho_nos)

	except nx.NetworkXNoPath:
		return None


def encontrar_caminho_minimo(
	gdf_bairros: gpd.GeoDataFrame, grafo: nx.MultiDiGraph, bairro_central: Optional[str] = None, sentido: Literal["IDA", "VOLTA"] = "IDA"
) -> gpd.GeoDataFrame:
	"""
	Orquestra o cálculo de rotas entre todos os bairros e um ponto central.
	"""
	if grafo.number_of_nodes() == 0:
		print("Aviso: O grafo está vazio. Nenhum caminho pode ser calculado.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	nos_multipoint = MultiPoint([Point(no) for no in grafo.nodes()])

	ponto_central_geom = _obter_ponto_central(gdf_bairros, bairro_central)
	no_central = encontrar_no_mais_proximo(ponto_central_geom, nos_multipoint)

	lista_caminhos = []
	bairro_central_limpo = bairro_central.strip() if bairro_central else None

	for index, bairro in enumerate(gdf_bairros.itertuples()):
		if bairro_central_limpo and bairro.name.strip() == bairro_central_limpo:
			continue

		if bairro.geometry.geom_type not in ("Polygon", "MultiPolygon"):
			continue

		ponto_bairro = bairro.geometry.centroid
		no_bairro = encontrar_no_mais_proximo(ponto_bairro, nos_multipoint)

		geometria_rota = _calcular_rota_individual(grafo, no_bairro, no_central, sentido)

		if geometria_rota:
			gdf_temp = gpd.GeoDataFrame([{"geometry": geometria_rota}], crs=PROJECTED_CRS)
			intersectados = gpd.sjoin(gdf_temp, gdf_bairros, how="inner", predicate="intersects")
			nome_coluna = "CD_SETOR" if "CD_SETOR" in intersectados.columns else "name"
			nomes_bairros = intersectados[nome_coluna].unique()

			lista_caminhos.append({
				"geometry": geometria_rota,
				"id": f"{index}{sentido[0]}",
				"bairro_origem": bairro.name,
				"bairros_atendidos_n": len(nomes_bairros),
				"bairros_lista": ", ".join(nomes_bairros),
			})
		else:
			pass

	if not lista_caminhos:
		print(f"Aviso: Nenhum caminho gerado no sentido {sentido}.")
		return gpd.GeoDataFrame(crs=PROJECTED_CRS)

	gdf_rotas = gpd.GeoDataFrame(lista_caminhos, crs=PROJECTED_CRS)

	print(f"Filtrando sublinhas para o sentido: {sentido}...")
	return filtrar_sublinhas(gdf_rotas)


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
	grafo = criar_grafo_ponderado(vias_filtradas, gdf_pontos_articulacao_proj, gdf_bairros_proj)

	print("\nCalculando os caminhos mínimos...")
	caminhos_volta = encontrar_caminho_minimo(gdf_bairros_proj, grafo, sentido="VOLTA")
	caminhos_ida = encontrar_caminho_minimo(gdf_bairros_proj, grafo, sentido="IDA")

	if not caminhos_volta.empty and not caminhos_ida.empty:
		pass
	else:
		print("\nAnálise concluída, mas nenhum caminho foi encontrado para plotar.")
