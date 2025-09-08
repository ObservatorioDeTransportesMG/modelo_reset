import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
from shapely import LineString, MultiPoint, Point
from shapely.ops import nearest_points

# 1. Carregar os Shapefiles
try:
	# Carregando o shapefile de vias
	gdf_vias = gpd.read_file("arquivos/Shapes para Mapas/Sistema viario.shp")
	gdf_bairros = gpd.read_file("arquivos/limites_bairros_moc/limites_bairros_moc.shp")

	# Carregando o shapefile de pontos
	# gdf_pontos = gpd.read_file("arquivos/pontos_teste.shp")
	gdf_pontos = gpd.read_file("arquivos/Shapes para Mapas/Node.shp")

except Exception as e:
	print(f"Erro ao ler os arquivos shapefile: {e}")
	exit()

# gdf_vias = gdf_vias[gdf_vias["TYPE"] == "residential"]

gdf_bairros = gdf_bairros.to_crs(gdf_vias.crs)

gdf_vias_2 = gpd.sjoin(gdf_vias, gdf_bairros, how="inner", predicate="intersects")
gdf_vias = gdf_vias_2.drop_duplicates(subset="ID")

fig, ax = plt.subplots(figsize=(12, 12))

# Plotar a rede de vias
# gdf_bairros.plot(ax=ax, color="gray")
# gdf_vias.plot(ax=ax, color="red", linewidth=0.5, zorder=1)

# plt.show()

print("COLUNAS VIAS: ", gdf_vias.columns)
print("COLUNAS PONTOS: ", gdf_pontos.columns)

# exit()

# Certificar-se de que ambos os GeoDataFrames estão no mesmo sistema de coordenadas (CRS)
if gdf_vias.crs != gdf_pontos.crs:
	print("Aviso: Os sistemas de coordenadas são diferentes. Reprojetando os pontos.")
	gdf_pontos = gdf_pontos.to_crs(gdf_vias.crs)

# 2. Construir a Rede (Grafo)
# Criar um grafo MultiDiGraph para permitir múltiplas arestas entre os mesmos nós e arestas direcionadas


G = nx.MultiDiGraph()

gdf_vias = gdf_vias[(gdf_vias["DIR"] == -1) | (gdf_vias["DIR"] == 0)]

for _, via in gdf_vias.iterrows():
	# Coordenadas de início e fim da geometria da via
	ponto_inicio = via.geometry.coords[0]
	ponto_fim = via.geometry.coords[-1]

	# Atributos da aresta (peso, ID da via, etc.)
	atributos = {
		"weight": via.geometry.length,  # Custo principal para Dijkstra (comprimento)
		"via_id": via["ID"],  # Guardar o ID original da via é uma boa prática
	}

	direcao = via["DIR"]

	# Lógica para adicionar arestas com base na coluna 'DIR'
	if direcao == 0:
		# Mão dupla: adicionar arestas em ambos os sentidos
		G.add_edge(ponto_inicio, ponto_fim, **atributos)
		G.add_edge(ponto_fim, ponto_inicio, **atributos)
	elif direcao == 1:
		# Mão única no sentido da digitalização (From-To)
		G.add_edge(ponto_inicio, ponto_fim, **atributos)
	elif direcao == -1:
		# Mão única no sentido oposto à digitalização (To-From)
		G.add_edge(ponto_fim, ponto_inicio, **atributos)
	# else:
	# Opcional: tratar vias sem direção definida (por exemplo, assumir mão dupla)
	# G.add_edge(ponto_inicio, ponto_fim, **atributos)
	# G.add_edge(ponto_fim, ponto_inicio, **atributos)

print(f"Grafo direcionado criado com {G.number_of_nodes()} nós e {G.number_of_edges()} arestas.")


# 3. Integrar os Pontos à Rede
# plt.show()
# Encontrar os nós da rede mais próximos aos seus pontos de interesse


# Função para encontrar o nó mais próximo no grafo para um dado ponto
def encontrar_no_mais_proximo(ponto, grafo):
	nos = list(grafo.nodes())
	pontos_nos = [Point(no) for no in nos]
	ponto_mais_proximo = nearest_points(ponto, MultiPoint(pontos_nos))[1]
	return (ponto_mais_proximo.x, ponto_mais_proximo.y)


# Supondo que você queira encontrar o caminho entre o primeiro e o segundo ponto do seu shapefile
ponto_origem = gdf_pontos.geometry.iloc[0]
ponto_destino = gdf_pontos.geometry.iloc[-1]

# Encontrar os nós do grafo mais próximos dos pontos de origem e destino
no_origem = encontrar_no_mais_proximo(ponto_origem, G)
no_destino = encontrar_no_mais_proximo(ponto_destino, G)

print(f"Nó de origem na rede: {no_origem}")
print(f"Nó de destino na rede: {no_destino}")

# 4. Executar o Algoritmo de Dijkstra
try:
	# Calcular o caminho mais curto usando o algoritmo de Dijkstra
	# O atributo 'weight' é usado para o cálculo (neste caso, o comprimento da via)
	caminho_mais_curto = nx.dijkstra_path(G, source=no_origem, target=no_destino, weight="weight")
	print("Caminho mais curto encontrado:")
	# print(caminho_mais_curto) # Descomente para ver a lista de coordenadas do caminho

	# Calcular o comprimento do caminho
	comprimento_caminho = nx.dijkstra_path_length(G, source=no_origem, target=no_destino, weight="weight")
	print(f"Comprimento do caminho: {comprimento_caminho:.2f} unidades")

except nx.NetworkXNoPath:
	print("Não foi possível encontrar um caminho entre a origem e o destino.")
	caminho_mais_curto = None

# 5. Visualizar o Resultado
# fig, ax = plt.subplots(figsize=(12, 12))

# Plotar a rede de vias
gdf_vias.plot(ax=ax, color="gray", linewidth=0.5, zorder=1)

# Plotar os pontos originais
gdf_pontos.plot(ax=ax, color="red", markersize=2, zorder=2)

# Se um caminho foi encontrado, plotá-lo
if caminho_mais_curto:
	# Criar um GeoDataFrame para o caminho
	caminho_linha = LineString(caminho_mais_curto)
	gdf_caminho = gpd.GeoDataFrame([{"geometry": caminho_linha}], crs=gdf_vias.crs)

	# Plotar o caminho
	gdf_caminho.plot(ax=ax, color="blue", linewidth=2, zorder=3)

# Plotar os nós de origem e destino na rede
ax.scatter(*zip(no_origem, no_destino), color="green", s=100, zorder=4, label="Nós na Rede")

ax.set_title("Análise de Rota com Algoritmo de Dijkstra")
ax.legend()
plt.show()
