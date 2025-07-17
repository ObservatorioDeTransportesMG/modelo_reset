# from modelo_reset import ModeloReset
from core.workflow import ModeloResetWorkflow as ModeloReset

PATH_BAIRROS = "limites_bairros_moc/limites_bairros_moc.shp"
PATH_RESIDENCIAS = "planilhas/residencias_tratado.csv"
PATH_OD = "planilhas/origem_destino.csv"
PATH_PONTOS_ARTICULACAO = "Ogay.kml"
# PATH_VIAS = "dados/shapefiles/malha_viaria.shp"

EPSG_PROJETADO = 31983

COLUNA_POPULACAO = "HAB/EDIF 2022"
COLUNA_RENDA = "RENDA_MEDIA"

DADOS_RENDA = "planilhas/Agregados_por_setores_renda_responsavel_BR.csv"
SETORES_CENSITARIOS = "BR_setores_CD2022/BR_setores_CD2022.shp"


def executar_analise_reset():
	"""
	Função principal para executar todas as etapas do Modelo RESET.
	"""
	print(">>> Iniciando a análise com o Método RESET <<<")

	modelo = ModeloReset()

	# Carrega os polígonos dos bairros e os pontos das residências com dados socioeconômicos.
	modelo.carregar_dados_base(path_bairros=PATH_BAIRROS, path_residencias=PATH_RESIDENCIAS, epsg_bairros=EPSG_PROJETADO)
	modelo.carregar_dados_ibge(path_setores=SETORES_CENSITARIOS, path_renda=DADOS_RENDA)

	# Carrega os pontos de viagens para calcular os fluxos.

	# Calcula densidade, renda e fluxos por bairro.
	# modelo.vincular_dados_IBGE("Montes Claros", "Minas Gerais")
	modelo.processar_renda_ibge(municipio="Montes Claros", uf="Minas Gerais")
	modelo.processar_densidade(COLUNA_POPULACAO)
	modelo.carregar_e_processar_od(path_od=PATH_OD)

	# modelo.calcular_densidade_e_renda(coluna_renda=COLUNA_RENDA, coluna_pop=COLUNA_POPULACAO)
	# if not modelo.origem.empty:
	# modelo.calcular_origem_destino()

	# O resultado será um mapa com os polos classificados.
	# modelo.set_polos_planejados("Distrito Industrial")
	modelo.identificar_polos_desenvolvimento("Distrito Industrial")
	# modelo.selecionar_polos_desenvolvimento()  # Usa os limiares padrão (quantis)

	modelo.carregar_pontos_articulacao(PATH_PONTOS_ARTICULACAO)

	modelo.mostrar_modelo_completo()

	print(">>> Análise RESET finalizada. <<<")


# Ponto de entrada do script
if __name__ == "__main__":
	executar_analise_reset()
