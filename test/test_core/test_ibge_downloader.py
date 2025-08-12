# test/test_core/test_ibge_downloader.py

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

# Importe as funções do seu módulo
from core.ibge_downloader import _baixar_e_descompactar_zip, baixar_dados_censo_renda, baixar_malha_municipal

# --- Testes para a função auxiliar _baixar_e_descompactar_zip ---


def criar_zip_falso_em_memoria(nome_arquivo_interno, conteudo_arquivo):
	"""Cria um arquivo .zip em memória para simular o download."""
	memoria_zip = io.BytesIO()
	with zipfile.ZipFile(memoria_zip, "w", zipfile.ZIP_DEFLATED) as zf:
		zf.writestr(nome_arquivo_interno, conteudo_arquivo)
	memoria_zip.seek(0)
	return memoria_zip.getvalue()


def test__baixar_e_descompactar_zip_sucesso(mocker, tmp_path):
	"""
	Testa o caminho feliz: download, descompactação e limpeza bem-sucedidos.
	"""
	# 1. Arrange: Preparar os mocks e dados falsos
	url_falsa = "http://example.com/arquivo.zip"
	conteudo_zip_falso = criar_zip_falso_em_memoria("meu_arquivo.txt", "conteúdo de teste")

	# Mock da resposta do requests
	mock_response = MagicMock()
	mock_response.raise_for_status.return_value = None
	mock_response.iter_content.return_value = [conteudo_zip_falso]  # Simula o conteúdo do download

	# Mock do requests.get para retornar nossa resposta falsa
	mock_requests_get = mocker.patch("core.ibge_downloader.requests.get", return_value=MagicMock(__enter__=MagicMock(return_value=mock_response)))

	# 2. Act: Executar a função
	diretorio_resultado = _baixar_e_descompactar_zip(url_falsa, str(tmp_path))

	# 3. Assert: Verificar os resultados
	mock_requests_get.assert_called_once_with(url_falsa, stream=True)
	assert diretorio_resultado == str(tmp_path)

	# Verifica se o arquivo foi descompactado
	arquivo_descompactado = tmp_path / "meu_arquivo.txt"
	assert arquivo_descompactado.exists()
	assert arquivo_descompactado.read_text() == "conteúdo de teste"

	# Verifica se o arquivo .zip foi removido após a descompactação
	arquivo_zip_temporario = tmp_path / "arquivo.zip"
	assert not arquivo_zip_temporario.exists()


def test__baixar_e_descompactar_zip_com_uf(mocker, tmp_path):
	"""Testa se o subdiretório da UF é criado corretamente."""
	url_falsa = "http://example.com/arquivo_uf.zip"
	conteudo_zip_falso = criar_zip_falso_em_memoria("outro.txt", "dados")

	mock_response = MagicMock()
	mock_response.iter_content.return_value = [conteudo_zip_falso]
	mocker.patch("core.ibge_downloader.requests.get", return_value=MagicMock(__enter__=MagicMock(return_value=mock_response)))

	diretorio_resultado = _baixar_e_descompactar_zip(url_falsa, str(tmp_path), uf="MG")

	diretorio_esperado = tmp_path / "MG"
	assert diretorio_resultado == str(diretorio_esperado)
	assert (diretorio_esperado / "outro.txt").exists()


def test__baixar_e_descompactar_zip_falha_conexao(mocker, tmp_path):
	"""Testa o tratamento de erro para falha de conexão (RequestException)."""
	url_falsa = "http://host.invalido/arquivo.zip"
	# Mock para levantar uma exceção de conexão
	mocker.patch("core.ibge_downloader.requests.get", side_effect=requests.exceptions.RequestException("Erro de DNS"))
	mock_print = mocker.patch("builtins.print")

	resultado = _baixar_e_descompactar_zip(url_falsa, str(tmp_path))

	assert resultado is None
	mock_print.assert_any_call(f"Erro de conexão ao tentar baixar de {url_falsa}: Erro de DNS")


def test__baixar_e_descompactar_zip_arquivo_invalido(mocker, tmp_path):
	"""Testa o tratamento de erro para um arquivo que não é um .zip válido."""
	url_falsa = "http://example.com/nao_e_zip.zip"
	# Simula o download de um conteúdo que não é zip
	conteudo_invalido = b"isso nao e um zip"
	mock_response = MagicMock()
	mock_response.iter_content.return_value = [conteudo_invalido]
	mocker.patch("core.ibge_downloader.requests.get", return_value=MagicMock(__enter__=MagicMock(return_value=mock_response)))
	mock_print = mocker.patch("builtins.print")

	resultado = _baixar_e_descompactar_zip(url_falsa, str(tmp_path))

	assert resultado is None
	mock_print.assert_any_call(f"Erro: O arquivo baixado de {url_falsa} não é um .zip válido.")


# --- Testes para as funções públicas ---


def test_baixar_malha_municipal_sucesso(mocker, tmp_path):
	"""Testa se a função constrói a URL correta e chama o helper."""
	uf, ano = "SP", 2023
	diretorio_extraido_falso = tmp_path / uf
	diretorio_extraido_falso.mkdir()
	# Cria o arquivo .shp que a função deve encontrar
	caminho_shp_esperado = diretorio_extraido_falso / f"{uf}_Municipios_{ano}.shp"
	caminho_shp_esperado.touch()  # Cria um arquivo vazio

	# Mock da função helper
	mock_helper = mocker.patch("core.ibge_downloader._baixar_e_descompactar_zip", return_value=str(diretorio_extraido_falso))

	resultado = baixar_malha_municipal(str(tmp_path), uf=uf, ano=ano)

	url_esperada = f"https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_{ano}/UFs/{uf}/{uf}_Municipios_{ano}.zip"

	mock_helper.assert_called_once_with(url_esperada, str(tmp_path), uf)
	assert resultado == str(caminho_shp_esperado)


def test_baixar_malha_municipal_falha(mocker, tmp_path):
	"""Testa o caso de falha onde o helper retorna None."""
	# Mock do helper para simular uma falha de download
	mock_helper = mocker.patch("core.ibge_downloader._baixar_e_descompactar_zip", return_value=None)

	resultado = baixar_malha_municipal(str(tmp_path), uf="RJ", ano=2024)

	assert resultado is None
	mock_helper.assert_called_once()


def test_baixar_dados_censo_renda_sucesso(mocker, tmp_path):
	"""Testa se a função de download do censo constrói a URL e chama o helper."""
	ano = 2022
	diretorio_extraido_falso = tmp_path / "censo_data"
	diretorio_extraido_falso.mkdir()
	caminho_csv_esperado = diretorio_extraido_falso / "Agregados_por_setores_renda_responsavel_BR.csv"
	caminho_csv_esperado.touch()

	mock_helper = mocker.patch("core.ibge_downloader._baixar_e_descompactar_zip", return_value=str(diretorio_extraido_falso))

	resultado = baixar_dados_censo_renda(str(tmp_path), ano=ano)

	url_esperada = f"https://ftp.ibge.gov.br/Censos/Censo_Demografico_{ano}/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/Agregados_por_setores_renda_responsavel_BR_csv.zip"

	mock_helper.assert_called_once_with(url_esperada, str(tmp_path))
	assert resultado == str(caminho_csv_esperado)
