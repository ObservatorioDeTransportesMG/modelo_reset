from core.workflow import ModeloReset

PATH_BAIRROS = "arquivos/limites_bairros_moc/limites_bairros_moc.shp"
PATH_RESIDENCIAS = "arquivos/planilhas/residencias_tratado.csv"
PATH_OD = "arquivos/planilhas/origem_destino.csv"
PATH_PONTOS_ARTICULACAO = "arquivos/pontos_articulacao.kml"

EPSG_PROJETADO = 31983

COLUNA_POPULACAO = "HAB/EDIF 2022"
COLUNA_RENDA = "RENDA_MEDIA"


def executar_analise_reset():
	"""
	Função principal para executar todas as etapas do Modelo RESET.
	"""
	print(">>> Iniciando a análise com o Método RESET <<<")

	modelo = ModeloReset()

	modelo.carregar_dados_base(path_bairros=PATH_BAIRROS, epsg_bairros=EPSG_PROJETADO)
	modelo.carregar_pontos_articulacao(PATH_PONTOS_ARTICULACAO)
	modelo.carregar_e_processar_od(path_od=PATH_OD)
	modelo.carregar_dados_ibge(2022)

	modelo.processar_dados(municipio="Montes Claros")

	modelo.identificar_polos_desenvolvimento("Distrito Industrial")

	modelo.mostrar_centroids()

	modelo.plotar_renda_media()
	modelo.plotar_densidade()

	modelo.mostrar_modelo_completo()

	print(">>> Análise RESET finalizada. <<<")


if __name__ == "__main__":
	executar_analise_reset()
