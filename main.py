from core.workflow import ModeloReset

PATH_BAIRROS = "arquivos/limites_bairros_moc/limites_bairros_moc.shp"
PATH_VIAS = "arquivos/Shapes para Mapas/Sistema viario.shp"
PATH_OD = "arquivos/planilhas/origem_destino.csv"
PATH_PONTOS_ARTICULACAO = "arquivos/pontos_articulacao.kml"

EPSG_PROJETADO = 31983
EPSG_GEOGRAFICO = 4326


def executar_analise_reset():
	"""
	Função principal para executar todas as etapas do Modelo RESET e da Análise de Rede subsequente.
	"""
	print(">>> Iniciando a análise com o Método RESET <<<")

	modelo = ModeloReset(crs_projetado=EPSG_PROJETADO)

	print("\n--- Carregando Camadas ---")
	modelo.carregar_dados_base(path_bairros=PATH_BAIRROS, epsg_bairros=EPSG_GEOGRAFICO)
	modelo.carregar_pontos_articulacao(PATH_PONTOS_ARTICULACAO)
	modelo.carregar_rede_viaria(path_vias=PATH_VIAS, epsg_vias=EPSG_GEOGRAFICO)  # <<< ADICIONADO
	modelo.carregar_e_processar_od(path_od=PATH_OD)
	modelo.carregar_dados_ibge(2022)

	print("\n--- Processando Dados Demográficos ---")
	modelo.processar_dados(municipio="Montes Claros")
	modelo.identificar_polos_desenvolvimento("Distrito Industrial")

	print("\n--- Exibindo Análises Demográficas ---")
	# modelo.mostrar_centroids()
	# modelo.plotar_renda_media()
	# modelo.plotar_densidade()
	# modelo.mostrar_modelo_completo()

	print("\n--- Iniciando Análise de Rede (Rotas) ---")
	modelo.gerar_rotas_otimizadas(bairro_central="Centro")
	modelo.mostrar_rotas_otimizadas()

	print("\n>>> Análise RESET e de Rede finalizada. <<<")


if __name__ == "__main__":
	executar_analise_reset()
