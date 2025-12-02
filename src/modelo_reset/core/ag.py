import random
from typing import Optional

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from deap import algorithms, base, creator, tools
from shapely.geometry import LineString, Point

from .network_design import *


class OtimizadorRotas:
	def __init__(self, grafo: nx.MultiDiGraph, gdf_bairros: gpd.GeoDataFrame):
		print("Iniciando Otimizador")
		self.grafo = grafo
		self.gdf_bairros = gdf_bairros
		self.bairros_dict = {idx: {"geom": row.geometry.centroid, "nome": row.NM_BAIRRO} for idx, row in gdf_bairros.iterrows()}
		self.indices_bairros = list(self.bairros_dict.keys())
		self.qtd_bairros = len(gdf_bairros)

		self.cache_rotas = {}
		self.nos_grafo_multipoint = None

		self._preparar_grafo()
		# self._pre_calcular_todas_rotas()

	def _calcular_rota_individual(
		self, grafo: nx.MultiDiGraph, no_origem: tuple[float, float], no_destino: tuple[float, float], sentido: str = "IDA"
	) -> Optional[LineString]:
		"""
		Calcula o caminho mínimo entre dois nós e retorna a geometria da linha.
		"""
		# Define quem é source e target baseado no sentido
		if sentido == "IDA":
			source, target = no_origem, no_destino
		else:
			source, target = no_destino, no_origem

		try:
			# O Dijkstra retorna uma lista de nós: [(x1,y1), (x2,y2), ...]
			caminho_nos = nx.dijkstra_path(grafo, source=source, target=target, weight="weight")

			# Se o caminho for trivial (apenas 1 ponto), não forma linha
			if len(caminho_nos) < 2:
				return None

			# Cria a geometria da linha conectando os nós
			return LineString(caminho_nos)

		except nx.NetworkXNoPath:
			# Não existe caminho entre os pontos (ilhas desconexas no grafo)
			return None
		except Exception:
			# Captura erros genéricos de topologia para não quebrar o loop genético
			# print(f"Erro ao calcular rota: {e}")
			return None

	def _preparar_grafo(self):
		"""Cria índice espacial dos nós do grafo para busca rápida."""
		from shapely.geometry import MultiPoint

		if self.grafo.number_of_nodes() > 0:
			self.nos_grafo_multipoint = MultiPoint([Point(no) for no in self.grafo.nodes()])

	def _rota_entre_bairros(self, idx_origem, idx_destino):
		"""Calcula rota e bairros atendidos entre dois centroids."""
		if (idx_origem, idx_destino) in self.cache_rotas:
			return self.cache_rotas[(idx_origem, idx_destino)]

		p1 = self.bairros_dict[idx_origem]["geom"]
		p2 = self.bairros_dict[idx_destino]["geom"]

		no_origem = encontrar_no_mais_proximo(p1, self.nos_grafo_multipoint)
		no_destino = encontrar_no_mais_proximo(p2, self.nos_grafo_multipoint)

		geom_linha = self._calcular_rota_individual(self.grafo, no_origem, no_destino, "IDA")

		if geom_linha is None:
			dados = {"dist": float("inf"), "bairros": set(), "geom": None}
		else:
			gdf_linha = gpd.GeoDataFrame([{"geometry": geom_linha}], crs=self.gdf_bairros.crs)
			intersecoes = gpd.sjoin(gdf_linha, self.gdf_bairros, how="inner", predicate="intersects")
			nomes_atendidos = set(intersecoes["NM_BAIRRO"].unique())

			dados = {"dist": geom_linha.length, "bairros": nomes_atendidos, "geom": geom_linha}

		self.cache_rotas[(idx_origem, idx_destino)] = dados
		return dados

	# def _pre_calcular_todas_rotas(self):
	# 	"""
	# 	Gera o cache. ATENÇÃO: Isso pode demorar dependendo do tamanho do grafo. Para testes rápidos, reduza o número de bairros.
	# 	"""
	# 	print("Iniciando pré-cálculo de rotas (Isso otimiza o Algoritmo Genético)...")
	# 	count = 0
	# 	# Apenas uma heurística: Calcular rotas aleatórias ou todas-contra-todas
	# 	# Se N_bairros for < 100, pode fazer todas-contra-todas.
	# 	# Caso contrário, calculamos sob demanda (lazy loading) ou amostramos.
	# 	# Aqui, vamos deixar para calcular sob demanda dentro do fitness para economizar startup,
	# 	# mas guardamos em memória (cache) assim que calculado.
	# 	pass

	# --- Configuração do Algoritmo Genético (DEAP) ---

	def setup_ga(self):
		creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0))
		creator.create("Individual", list, fitness=creator.FitnessMulti)

		toolbox = base.Toolbox()

		# 2. Gerador de Genes: Um par (origem, destino)
		def gerar_gene_rota():
			return tuple(random.sample(self.indices_bairros, 2))

		# 3. Gerador de Indivíduos: Lista de rotas (tamanho variável 20 a 40)
		def gerar_individuo():
			tamanho = random.randint(20, 40)
			return creator.Individual([gerar_gene_rota() for _ in range(tamanho)])

		toolbox.register("attr_rota", gerar_gene_rota)
		toolbox.register("individual", gerar_individuo)
		toolbox.register("population", tools.initRepeat, list, toolbox.individual)

		def evaluate(individual):
			total_distancia = 0.0
			bairros_atendidos = set()

			for origem, destino in individual:
				dados_rota = self._rota_entre_bairros(origem, destino)

				if dados_rota["dist"] == float("inf"):
					total_distancia += 100000
				else:
					total_distancia += dados_rota["dist"]
					bairros_atendidos.update(dados_rota["bairros"])

			return total_distancia, 1 - (len(bairros_atendidos) / self.qtd_bairros)

		toolbox.register("evaluate", evaluate)

		toolbox.register("mate", tools.cxTwoPoint)

		def mutacao_variavel(individual):
			r = random.random()

			if r < 0.33 and len(individual) > 20:
				idx = random.randrange(len(individual))
				del individual[idx]

			elif r < 0.66 and len(individual) < 40:
				individual.append(gerar_gene_rota())

			else:
				idx = random.randrange(len(individual))
				individual[idx] = gerar_gene_rota()

			return (individual,)

		toolbox.register("mutate", mutacao_variavel)
		toolbox.register("select", tools.selNSGA2)

		return toolbox

	def rodar_algoritmo(self, n_geracoes=50, n_populacao=100):
		toolbox = self.setup_ga()
		pop = toolbox.population(n=n_populacao)

		stats = tools.Statistics(lambda ind: ind.fitness.values)
		stats.register("avg", np.mean, axis=0)
		stats.register("min", np.min, axis=0)
		stats.register("max", np.max, axis=0)

		pop, logbook = algorithms.eaMuPlusLambda(
			pop, toolbox, mu=n_populacao, lambda_=n_populacao, cxpb=0.4, mutpb=0.5, ngen=n_geracoes, stats=stats, verbose=True
		)

		return pop, logbook

	def extrair_melhor_solucao(self, populacao, criterio="mediana"):
		"""
		Extrai uma solução da Fronteira de Pareto.

		Args:
			populacao: A população final do algoritmo genético.
			criterio: 'mediana' (equilíbrio), 'custo' (menor distância) ou 'cobertura' (maior abrangência).
		"""
		pareto_front = tools.sortNondominated(populacao, len(populacao), first_front_only=True)[0]

		if not pareto_front:
			print("Nenhuma solução encontrada.")
			return gpd.GeoDataFrame(crs=self.gdf_bairros.crs)

		if criterio == "custo":
			melhor_ind = min(pareto_front, key=lambda ind: ind.fitness.values[0])
			print("Selecionada solução de MÍNIMO CUSTO.")

		elif criterio == "cobertura":
			melhor_ind = max(pareto_front, key=lambda ind: ind.fitness.values[1])
			print("Selecionada solução de MÁXIMA COBERTURA.")

		else:
			pareto_ordenado = sorted(pareto_front, key=lambda ind: ind.fitness.values[0])

			indice_meio = len(pareto_ordenado) // 2
			melhor_ind = pareto_ordenado[indice_meio]
			print(f"Selecionada solução MEDIANA (Índice {indice_meio} de {len(pareto_ordenado)} na fronteira).")

		distancia_total = melhor_ind.fitness.values[0]
		abrangencia = melhor_ind.fitness.values[1]

		print(f"Detalhes da Solução: Distância Total: {distancia_total:.2f}m | Abrangência Cobertos: {1 - abrangencia}")

		gdf_final = []
		for i, (orig, dest) in enumerate(melhor_ind):
			dados = self._rota_entre_bairros(orig, dest)

			if dados["geom"] and isinstance(dados["geom"], LineString):
				gdf_final.append({
					"geometry": dados["geom"],
					"id": i,
					"bairros_atendidos": ", ".join(dados["bairros"]),
					"qtd_bairros": len(dados["bairros"]),
					"distancia": dados["dist"],
					"origem_idx": orig,
					"destino_idx": dest,
				})

		if not gdf_final:
			return gpd.GeoDataFrame(crs=self.gdf_bairros.crs)

		return gpd.GeoDataFrame(gdf_final, crs=self.gdf_bairros.crs)


def plotar_fronteira_pareto(populacao):
	"""
	Plota a dispersão de todas as soluções e destaca a Fronteira de Pareto.
	"""
	fitness_values = [ind.fitness.values for ind in populacao]

	distancias = [val[0] for val in fitness_values]
	coberturas = [val[1] for val in fitness_values]

	pareto_front = tools.sortNondominated(populacao, len(populacao), first_front_only=True)[0]

	pareto_fitness = [ind.fitness.values for ind in pareto_front]
	pareto_dist = [val[0] for val in pareto_fitness]
	pareto_cov = [val[1] for val in pareto_fitness]

	plt.figure(figsize=(10, 6))

	plt.scatter(distancias, coberturas, c="gray", alpha=0.5, label="Soluções Dominadas")

	plt.scatter(pareto_dist, pareto_cov, c="red", s=50, label="Fronteira de Pareto (Ótimos)")

	plt.title("Fronteira de Pareto: Distância vs Cobertura")
	plt.xlabel("Distância Total das Linhas (Minimizar)")
	plt.ylabel("1 - Percentual de Bairros Atendidos (Minimizar)")
	plt.grid(True, linestyle="--", alpha=0.7)
	plt.legend()

	plt.ylim(0, 1.05)  # Garante que mostre até 100%

	plt.show()


def plotar_evolucao(logbook):
	"""
	Plota como a média da população evoluiu ao longo das gerações.
	"""
	gen = logbook.select("gen")
	fit_avgs = logbook.select("avg")

	avg_dist = [fit[0] for fit in fit_avgs]
	avg_cov = [fit[1] for fit in fit_avgs]

	fig, ax1 = plt.subplots(figsize=(10, 5))

	color = "tab:red"
	ax1.set_xlabel("Geração")
	ax1.set_ylabel("Distância Média", color=color)
	ax1.plot(gen, avg_dist, color=color, linestyle="--")
	ax1.tick_params(axis="y", labelcolor=color)

	ax2 = ax1.twinx()  # Cria eixo Y secundário
	color = "tab:blue"
	ax2.set_ylabel("1 - Cobertura Média", color=color)
	ax2.plot(gen, avg_cov, color=color, linewidth=2)
	ax2.tick_params(axis="y", labelcolor=color)

	plt.title("Convergência do Algoritmo Genético")
	fig.tight_layout()
	plt.show()
