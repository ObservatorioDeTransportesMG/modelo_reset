import os
import zipfile
from pathlib import Path
from typing import Optional

import requests


def _baixar_e_descompactar_zip(url: str, diretorio_saida: str, uf: Optional[str] = None) -> Optional[str]:
	"""Função auxiliar para baixar e descompactar um arquivo .zip.

	Args:
		url (str): A URL do arquivo .zip para baixar.
		diretorio_saida (str): O diretório onde o arquivo será salvo e descompactado.
		uf (Optional[str]): A UF referente ao arquivo.

	Returns:
		Optional[str]: O caminho para o diretório onde os arquivos foram extraídos ou None em caso de falha.
	"""
	try:
		if uf:
			diretorio_saida = os.path.join(diretorio_saida, uf)

		Path(diretorio_saida).mkdir(parents=True, exist_ok=True)

		nome_arquivo_zip = os.path.join(diretorio_saida, Path(url).name)

		print(f"Baixando de: {url}")

		with requests.get(url, stream=True) as r:
			r.raise_for_status()
			with open(nome_arquivo_zip, "wb") as f:
				for chunk in r.iter_content(chunk_size=8192):
					f.write(chunk)

		print(f"Arquivo salvo em: {nome_arquivo_zip}")

		print(f"Descompactando {nome_arquivo_zip}...")
		with zipfile.ZipFile(nome_arquivo_zip, "r") as zip_ref:
			zip_ref.extractall(diretorio_saida)

		os.remove(nome_arquivo_zip)
		print("Descompactação concluída e arquivo .zip removido.")

		return diretorio_saida

	except requests.exceptions.RequestException as e:
		print(f"Erro de conexão ao tentar baixar de {url}: {e}")
		return None
	except zipfile.BadZipFile:
		print(f"Erro: O arquivo baixado de {url} não é um .zip válido.")
		return None
	except Exception as e:
		print(f"Ocorreu um erro inesperado: {e}")
		return None


def baixar_malha_municipal(diretorio_saida: str, uf: str = "MG", ano: int = 2024) -> Optional[str]:
	"""Baixa a malha municipal (shapefile) de um estado (UF) e ano específicos do IBGE.

	Args:
		diretorio_saida (str): O diretório onde os arquivos serão salvos.
		uf (str): A sigla do estado em maiúsculas (ex: "SP", "MG").
		ano (int): O ano da malha territorial (ex: 2020).

	Returns:
		Optional[str]: O caminho para o arquivo .shp principal se o download e a descompactação forem bem-sucedidos, caso contrário None.
	"""
	# Exemplo de URL base para malhas municipais.
	# ATENÇÃO: Esta URL pode mudar. Verifique no site do IBGE se o link ainda é válido.
	url = f"https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_{ano}/UFs/{uf}/{uf}_Municipios_{ano}.zip"

	diretorio_extraido = _baixar_e_descompactar_zip(url, diretorio_saida, uf)

	if diretorio_extraido:
		for arquivo in Path(diretorio_extraido).rglob("*.shp"):
			return str(arquivo)

	print(f"Não foi possível encontrar o arquivo .shp para {uf} - {ano}.")
	return None


def baixar_dados_censo_renda(diretorio_saida: str, ano: int = 2022) -> Optional[str]:
	"""Baixa os dados de renda do Censo Demográfico do IBGE.

	Args:
		ano (int): O ano do Censo (ex: 2010).
		diretorio_saida (str): O diretório onde os arquivos serão salvos.

	Returns:
		Optional[str]: O caminho para o arquivo CSV de renda se o download for bem-sucedido, caso contrário None.
	"""
	url = f"https://ftp.ibge.gov.br/Censos/Censo_Demografico_{ano}/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/Agregados_por_setores_renda_responsavel_BR_csv.zip"

	diretorio_extraido = _baixar_e_descompactar_zip(url, diretorio_saida)

	if diretorio_extraido:
		for arquivo in Path(diretorio_extraido).rglob("*.csv"):
			if "renda" in arquivo.name.lower() or "domicilio" in arquivo.name.lower():
				return str(arquivo)

		primeiro_csv = next(Path(diretorio_extraido).rglob("*.csv"), None)
		if primeiro_csv:
			return str(primeiro_csv)

	print(f"Não foi possível encontrar o arquivo CSV de renda para o Censo {ano}.")
	return None


if __name__ == "__main__":
	baixar_dados_censo_renda("arquivos/teste/")
	baixar_malha_municipal("arquivos/malha_teste/")
