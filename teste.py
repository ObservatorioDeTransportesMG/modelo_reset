# import geopandas as gpd
# import pandas as pd
# from pyogrio import list_layers
import matplotlib.pyplot as plt  # <-- IMPORTAÇÃO NECESSÁRIA
import pandas as pd

from modelo_reset import ModeloReset

# ARQUIVO = "planilhas/Agregados_por_setores_renda_responsavel_BR.csv"
# # camadas = list_layers(ARQUIVO)
# SETORES_CENSITARIOS = "BR_setores_CD2022/BR_setores_CD2022.shp"

# df = pd.read_csv(ARQUIVO)
# print(df.columns)
# shapefile = gpd.read_file(SETORES_CENSITARIOS)

# print(shapefile.head())
# print(shapefile.columns)

meu_modelo = ModeloReset()

# Defina os caminhos para seus arquivos
path_setores_ibge = "BR_setores_CD2022/BR_setores_CD2022.shp"
path_renda_csv = "planilhas/Agregados_por_setores_renda_responsavel_BR-2.csv"

# Execute a função de vinculação
meu_modelo.vincular_setores_com_renda(
	path_shapefile_setores=path_setores_ibge,
	path_csv_renda=path_renda_csv,
	municipio="Montes Claros",
	uf="Minas Gerais",
	coluna_setor_shp="CD_SETOR",  # Verifique se este é o nome correto no seu SHP
	coluna_setor_csv="CD_SETOR",  # Verifique e altere para o nome correto no seu CSV
)

# Agora você pode acessar o GeoDataFrame resultante
if "setores_com_renda" in meu_modelo.camadas:
	gdf_final = meu_modelo.camadas["setores_com_renda"]
	print("\nVisualização do resultado final (primeiras 5 linhas):")
	print(gdf_final.head())

	# Você pode então usar este gdf_final para seus cálculos e plotagens
	# Adicione esta parte para limpar os dados
	print("\nLimpando e convertendo a coluna de renda para formato numérico...")

	# 1. Substitui a vírgula por ponto na coluna 'V06004'
	# O regex=False é importante para tratar o '.' como um caractere literal
	gdf_final["V06004_float"] = gdf_final["V06004"].str.replace(",", ".", regex=False)

	# 2. Converte a nova coluna para o tipo numérico (float)
	# errors='coerce' transformará qualquer valor que não possa ser convertido em NaN (Not a Number)
	gdf_final["V06004_float"] = pd.to_numeric(gdf_final["V06004_float"], errors="coerce")

	# Opcional: verifique se a conversão funcionou
	print("Tipos de dados após a conversão:")
	print(gdf_final[["V06004", "V06004_float"]].info())

	gdf_final.plot(column="V06004_float", legend=True, figsize=(10, 10), cmap="viridis")
	plt.title("Renda Média por Setor Censitário em Montes Claros")
	plt.xlabel("Longitude")
	plt.ylabel("Latitude")
	plt.show()  # <-- COMANDO PARA MOSTRAR O GRÁFICO NA TELA

	print("PLOTAGEM DO MAPA DE CORES FINALIZADA.")

	# Plotagem simples das geometrias
	# gdf_final.plot(figsize=(10, 10), edgecolor="blue")
	# plt.title("Setores Censitários de Montes Claros")
	# plt.show()  # <-- COMANDO PARA MOSTRAR O SEGUNDO GRÁFICO

	print("PLOTAGEM DAS GEOMETRIAS FINALIZADA.")
