from modelo_reset import ModeloReset

PATH_BAIRROS = "limites_bairros_moc/limites_bairros_moc.shp"
PATH_RESIDENCIAS = "planilhas/residencias_tratado.csv"
PATH_OD = "planilhas/origem_destino.csv"  # Shapefile de pontos O/D
# PATH_PONTOS_ARTICULACAO = "dados/shapefiles/pontos_articulacao.shp"
# PATH_VIAS = "dados/shapefiles/malha_viaria.shp"

EPSG_ORIGINAL = 31983

COLUNA_POPULACAO = "HAB/EDIF 2022"
COLUNA_RENDA = "RENDA_MEDIA"

def executar_analise_reset():
	"""
	Função principal para executar todas as etapas do Modelo RESET.
	"""
	print(">>> Iniciando a análise com o Método RESET <<<")

	modelo = ModeloReset()

	# Carrega os polígonos dos bairros e os pontos das residências com dados socioeconômicos.
	modelo.carregar_dados_base(path_bairros=PATH_BAIRROS, path_residencias=PATH_RESIDENCIAS, epsg=EPSG_ORIGINAL)

	# Carrega os pontos de viagens para calcular os fluxos.
	try:
		modelo.carregar_dados_od(path_od=PATH_OD)
	except Exception as e:
		print(f"Não foi possível carregar os dados de O/D: {e}. O cálculo de fluxo será ignorado.")

	# Calcula densidade, renda e fluxos por bairro.
	modelo.calcular_densidade_e_renda(coluna_renda=COLUNA_RENDA, coluna_pop=COLUNA_POPULACAO)
	if not modelo.origem.empty:
		modelo.calcular_origem_destino()

	# O resultado será um mapa com os polos classificados.
	modelo.selecionar_polos_desenvolvimento()  # Usa os limiares padrão (quantis)

	# Carrega e plota os locais de interesse que ancorarão a rede.
	# try:
	# 	modelo.carregar_pontos_articulacao(path_pontos=PATH_PONTOS_ARTICULACAO, epsg=EPSG_ORIGINAL)
	# 	modelo.mostrar_pontos_de_articulacao()
	# except Exception as e:
	# 	print(f"\nNão foi possível carregar os Pontos de Articulação: {e}")
	# 	print("Certifique-se que o arquivo existe no caminho especificado.")

	# Seleciona e plota as principais vias que formarão o esqueleto da rede.
	# try:
	# 	modelo.estabelecer_svetc(
	# 		path_vias=PATH_VIAS, epsg=EPSG_ORIGINAL, nomes_avenidas_principais=AVENIDAS_PRINCIPAIS, coluna_nome_via=COLUNA_NOME_VIA
	# 	)
	# 	modelo.mostrar_svetc()
	# except Exception as e:
	# 	print(f"\nNão foi possível estabelecer o SVETC: {e}")
	# 	print("Certifique-se que o arquivo de vias e os nomes das colunas/avenidas estão corretos.")

	print("\n>>> Análise RESET finalizada. <<<")


# Ponto de entrada do script
if __name__ == "__main__":
	executar_analise_reset()
