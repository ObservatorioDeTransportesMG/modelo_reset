@echo off
REM Nome do pacote (deve ser igual ao nome da pasta em src/ ou no pyproject.toml)
set PACKAGE_NAME=modelo_reset

REM Verifica qual comando foi passado (clean, build, etc.)
if "%1"=="" goto help
if "%1"=="clean" goto clean
if "%1"=="build" goto build
if "%1"=="publish-test" goto publish_test
if "%1"=="publish" goto publish
if "%1"=="install-test" goto install_test

:help
echo --------------- GERENCIADOR DO PACOTE %PACKAGE_NAME% (Windows) ---------------
echo Comandos disponiveis:
echo   make clean         -^> Remove arquivos de build antigos (dist, build, egg-info)
echo   make build         -^> Gera os arquivos de distribuicao (.tar.gz e .whl)
echo   make publish-test  -^> Gera build e sobe para o TestPyPI
echo   make publish       -^> Gera build e sobe para o PyPI Oficial (PRODUCAO)
echo   make install-test  -^> Instala do TestPyPI (buscando dependencias no PyPI oficial)
echo ---------------------------------------------------------------------
goto :eof

:clean
echo Limpando arquivos de build antigos...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist %PACKAGE_NAME%.egg-info rmdir /s /q %PACKAGE_NAME%.egg-info
goto :eof

:build
call :clean
echo Gerando novo build...
python -m build
goto :eof

:publish_test
call :build
echo Enviando para o TestPyPI...
twine upload --repository testpypi dist/*
goto :eof

:publish
call :build
echo ENVIANDO PARA O PYPI OFICIAL (PRODUCAO)...
twine upload --repository pypi dist/*
goto :eof

:install_test
echo Instalando %PACKAGE_NAME% do TestPyPI com fallback para PyPI...
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ %PACKAGE_NAME%
goto :eof