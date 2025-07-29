import geopandas as gpd
import pandas as pd

from utils.constants import COLUNAS


def filtrar_setores_por_municipio(setores_gdf: gpd.GeoDataFrame, municipio: str, uf: str) -> gpd.GeoDataFrame:
	"""Filtra um GeoDataFrame de setores censitários por município e UF.

	Args:
		setores_gdf (gpd.GeoDataFrame): O GeoDataFrame de entrada contendo os setores censitários. Deve conter as colunas "NM_MUN" e "NM_UF".
		municipio (str): O nome do município a ser filtrado.
		uf (str): A sigla do estado (UF) a ser filtrado.

	Returns:
		gpd.GeoDataFrame: Um novo GeoDataFrame contendo apenas os setores do município e UF especificados.
	"""
	print(f"Filtrando setores para {municipio.upper()} - {uf.upper()}...")
	filtro = (setores_gdf["NM_MUN"].str.upper() == municipio.upper()) & (setores_gdf["NM_UF"].str.upper() == uf.upper())
	setores_filtrados = setores_gdf[filtro].copy()
	print(f"Encontrados {len(setores_filtrados)} setores.")
	return setores_filtrados


def vincular_setores_com_renda(
	setores_filtrados_gdf: gpd.GeoDataFrame, renda_df: pd.DataFrame, coluna_setor_shp: str = "CD_SETOR", coluna_setor_csv: str = "CD_SETOR"
) -> gpd.GeoDataFrame:
	"""Vincula dados de renda a um GeoDataFrame de setores censitários.

	Args:
		setores_filtrados_gdf (gpd.GeoDataFrame): GeoDataFrame com os setores censitários (geralmente já filtrados por município).
		renda_df (pd.DataFrame): DataFrame contendo os dados de renda.
		coluna_setor_shp (str, optional): Nome da coluna com o código do setor no GeoDataFrame. Padrão é "CD_SETOR".
		coluna_setor_csv (str, optional): Nome da coluna com o código do setor no DataFrame de renda. Padrão é "CD_SETOR".

	Returns:
		gpd.GeoDataFrame: Um GeoDataFrame com as informações de renda adicionadas aos setores correspondentes.
	"""
	setores_filtrados_gdf[coluna_setor_shp] = setores_filtrados_gdf[coluna_setor_shp].astype(str)
	renda_df[coluna_setor_csv] = renda_df[coluna_setor_csv].astype(str)

	setores_com_renda = setores_filtrados_gdf.merge(renda_df, left_on=coluna_setor_shp, right_on=coluna_setor_csv, how="left")
	print("Vinculação de setores com renda finalizada.")
	return setores_com_renda


def associar_ibge_bairros(bairros_gdf: gpd.GeoDataFrame, setores_com_renda_gdf: gpd.GeoDataFrame, crs_projetado: str) -> gpd.GeoDataFrame:
	"""Associa dados de setores censitários (IBGE) aos polígonos de bairros.

	Args:
		bairros_gdf (gpd.GeoDataFrame): GeoDataFrame contendo os polígonos dos bairros.
		setores_com_renda_gdf (gpd.GeoDataFrame): GeoDataFrame de setores censitários, já enriquecido com dados de renda.
		crs_projetado (str): O código EPSG de um Sistema de Referência de Coordenadas (CRS) projetado (ex: 'EPSG:31983').

	Returns:
		gpd.GeoDataFrame: Um GeoDataFrame onde cada linha representa um setor censitário com as informações do bairro ao qual foi associado.
	"""
	bairros_proj = bairros_gdf.to_crs(crs_projetado)
	setores_proj = setores_com_renda_gdf.to_crs(crs_projetado)

	# Limpeza e conversão de colunas

	setores_limpos = setores_proj.copy()
	for col_original, col_novo in COLUNAS.items():
		if col_original in setores_limpos.columns:
			setores_limpos[col_original] = setores_limpos[col_original].astype(str)
			setores_limpos[col_original] = setores_limpos[col_original].str.replace(".", "", regex=False)
			setores_limpos[col_novo] = pd.to_numeric(setores_limpos[col_original].str.replace(",", ".", regex=False), errors="coerce").fillna(0)
		else:
			print(f"Aviso: Coluna '{col_original}' não encontrada no DataFrame de setores.")
			setores_limpos[col_novo] = 0

	setores_centroids = setores_limpos.copy()
	setores_centroids["geometry"] = setores_centroids.geometry.centroid

	join_espacial = gpd.sjoin(setores_centroids, bairros_proj, how="left", predicate="within")
	return join_espacial[join_espacial["index_right"].notna()]


def agregar_renda_por_bairro(bairros_gdf: gpd.GeoDataFrame, setores_com_renda_gdf: gpd.GeoDataFrame, crs_projetado: str) -> gpd.GeoDataFrame:
	"""Agrega dados de renda e população dos setores para a camada de bairros.

	Args:
		bairros_gdf (gpd.GeoDataFrame): O GeoDataFrame original dos bairros.
		setores_com_renda_gdf (gpd.GeoDataFrame): GeoDataFrame de setores com dados de renda.
		crs_projetado (str): O código EPSG do CRS projetado a ser usado.

	Returns:
		gpd.GeoDataFrame: O GeoDataFrame de bairros com as novas colunas `renda_total_bairro`, `populacao_total_bairro` e `renda_media_bairro`.
	"""
	bairros_proj = bairros_gdf.to_crs(crs_projetado)
	join_espacial = associar_ibge_bairros(bairros_gdf, setores_com_renda_gdf, crs_projetado)

	dados_agregados = join_espacial.groupby("index_right").agg(
		renda_total_bairro=("renda_mensal_média", "sum"), populacao_total_bairro=("num_de_moradores", "sum")
	)

	bairros_com_renda = bairros_proj.join(dados_agregados).fillna(0)
	bairros_com_renda["renda_media_bairro"] = bairros_com_renda.apply(
		lambda row: row["renda_total_bairro"] / row["populacao_total_bairro"] if row["populacao_total_bairro"] > 0 else 0, axis=1
	)

	print("Agregação de renda por bairro finalizada.")
	print(bairros_com_renda.head())
	if bairros_gdf.crs is None:
		raise
	return bairros_com_renda.to_crs(bairros_gdf.crs)


def calcular_fluxos_od(bairros_gdf: gpd.GeoDataFrame, origem_gdf: gpd.GeoDataFrame, destino_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
	"""Calcula o número total de pontos de origem e destino por bairro.

	Args:
		bairros_gdf (gpd.GeoDataFrame): GeoDataFrame com os polígonos dos bairros.
		origem_gdf (gpd.GeoDataFrame): GeoDataFrame de pontos representando as origens.
		destino_gdf (gpd.GeoDataFrame): GeoDataFrame de pontos representando os destinos.

	Returns:
		gpd.GeoDataFrame: O GeoDataFrame de bairros com as novas colunas `n_origens`, `n_destinos` e `fluxo_total`.
	"""
	bairros_result = bairros_gdf.copy()
	if bairros_result.crs is None:
		raise
	if bairros_result.crs != origem_gdf.crs:
		origem_gdf = origem_gdf.to_crs(bairros_result.crs)
	if bairros_result.crs != destino_gdf.crs:
		destino_gdf = destino_gdf.to_crs(bairros_result.crs)

	# Assumindo que o índice do bairro é usado para agrupar
	pontos_origem = gpd.sjoin(origem_gdf, bairros_result, how="left", predicate="within")
	pontos_destino = gpd.sjoin(destino_gdf, bairros_result, how="left", predicate="within")

	qtd_origem = pontos_origem.groupby("index_right").size()
	qtd_destino = pontos_destino.groupby("index_right").size()

	bairros_result["n_origens"] = bairros_result.index.map(qtd_origem).fillna(0).astype(int)
	bairros_result["n_destinos"] = bairros_result.index.map(qtd_destino).fillna(0).astype(int)
	bairros_result["fluxo_total"] = bairros_result["n_origens"] + bairros_result["n_destinos"]

	print("Cálculo de fluxos O/D finalizado.")
	return bairros_result


def calcular_densidade_populacional(bairros_gdf: gpd.GeoDataFrame, crs_projetado: str) -> gpd.GeoDataFrame:
	"""Calcula a densidade populacional por bairro (habitantes por km²).

	Args:
		bairros_gdf (gpd.GeoDataFrame): GeoDataFrame de bairros, devendo conter a coluna `populacao_total_bairro`.
		crs_projetado (str): O código EPSG do CRS projetado (ex: 'EPSG:31983') para o cálculo preciso da área.

	Returns:
		gpd.GeoDataFrame: O GeoDataFrame de bairros com as novas colunas `area_km2` e `densidade_km2`.
	"""
	bairros_proj = bairros_gdf.to_crs(crs_projetado)
	# residencias_proj = residencias_gdf.to_crs(crs_projetado)
	# setores_proj = setores_com_renda_gdf.to_crs(crs_projetado)

	bairros_proj["area_km2"] = bairros_proj.geometry.area / 1_000_000

	# agregado = setores_proj.groupby("index_right").agg(populacao_total=("num_de_moradores", "sum"))

	# bairros_proj = bairros_proj.join(agregado).fillna(0)
	bairros_proj["populacao_total_bairro"] = bairros_proj["populacao_total_bairro"].astype(int)
	bairros_proj["densidade_km2"] = bairros_proj["populacao_total_bairro"] / bairros_proj["area_km2"]

	print("Cálculo de densidade finalizado.")
	if bairros_gdf.crs is None:
		raise
	return bairros_proj.to_crs(bairros_gdf.crs)


def identificar_polos(bairros_gdf: gpd.GeoDataFrame, densidade_limiar=0.8, renda_limiar=0.4, fluxo_limiar=0.8) -> gpd.GeoDataFrame:
	"""Classifica bairros em "Polos de Desenvolvimento" com base em limiares.

	Args:
		bairros_gdf (gpd.GeoDataFrame): O GeoDataFrame de bairros, que deve conter as colunas 'densidade_km2', 'renda_media_bairro' e 'fluxo_total'.
		densidade_limiar (float, optional): Quantil para "alta densidade". Padrão 0.8.
		renda_limiar (float, optional): Quantil para "baixa renda". Padrão 0.4.
		fluxo_limiar (float, optional): Quantil para "alto fluxo". Padrão 0.8.

	Returns:
		gpd.GeoDataFrame: O GeoDataFrame de bairros com a nova coluna `tipo_polo` indicando a classificação de cada um.
	"""
	bairros_result = bairros_gdf.copy()
	# bairros_result["tipo_polo"] = "Nenhum"  # Inicializa

	dens_alta = bairros_result["densidade_km2"].quantile(densidade_limiar)
	renda_baixa = bairros_result["renda_media_bairro"].quantile(renda_limiar)
	fluxo_alto = bairros_result["fluxo_total"].quantile(fluxo_limiar)

	# Polo Consolidado
	bairros_result.loc[
		(bairros_result["densidade_km2"] >= dens_alta)
		& (bairros_result["renda_media_bairro"] <= renda_baixa)
		& (bairros_result["fluxo_total"] >= fluxo_alto),
		"tipo_polo",
	] = "Consolidado"

	# Polo Emergente
	bairros_result.loc[
		(bairros_result["densidade_km2"] >= dens_alta)
		& (bairros_result["renda_media_bairro"] <= renda_baixa)
		& (bairros_result["fluxo_total"] < fluxo_alto),
		"tipo_polo",
	] = "Emergente"

	print("Identificação de Polos finalizada.")
	return bairros_result
