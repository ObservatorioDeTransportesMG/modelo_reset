# Implementação Computacional do Método RESET

Este repositório contém a implementação em Python do Método RESET (Rede de Estudos de Engenharia e Socioeconómica de Transportes) para o planeamento de redes de transporte público urbano.

O software automatiza a análise territorial utilizando dados do IBGE, identifica polos de desenvolvimento e gera rotas otimizadas baseadas em grafos ponderados pela atratividade de pontos de interesse.

## 📄 Contexto Teórico

O projeto baseia-se na dissertação de Bruna Oliveira Rosa (COPPE/UFRJ, 2016). O objetivo é superar o modelo radiocêntrico (bairro-centro) tradicional, promovendo conexões diretas entre Polos de Desenvolvimento (Consolidados, Emergentes e Planeados) e utilizando Pontos de Articulação para moldar o traçado das linhas.

## 🚀 Funcionalidades

1. Aquisição Automática de Dados (ibge_downloader.py)

   - Download automático de malhas territoriais (Shapefiles) do servidor FTP do IBGE.

   - Download e extração de dados de rendimento do Censo Demográfico.

2. Análise Socioeconómica (analysis.py)

   - Identificação de Polos: Classificação automática dos bairros utilizando estatística de quantis (percentis) baseada em:

   - Densidade Populacional.

   - Rendimento Médio.

   - Fluxo de Origem/Destino (O/D).

   - Cruzamento espacial entre setores censitários e bairros locais.

3. Modelação de Rede e Grafos (network_design.py)

   - Conversão da malha viária em MultiDiGraph (NetworkX).

   - Peso Atrativo: Diferente de um GPS comum, o algoritmo ajusta o "custo" das arestas (ruas) com base na proximidade de Pontos de Articulação (escolas, hospitais, terminais). Ruas próximas a estes pontos tornam-se "mais baratas" matematicamente, atraindo o traçado da rota.

4. Roteamento (workflow.py)

   - Cálculo de caminhos mínimos (Dijkstra) entre os bairros e o centro/polos.

   - Gera rotas de IDA e VOLTA.

   - Filtragem de sub-linhas para evitar redundâncias geométricas.

## 📂 Estrutura do Projeto

O código está modularizado para separar a ingestão de dados, a lógica de negócio e a visualização:

```
├── core/
│ ├── workflow.py # Orquestrador principal (Classe ModeloReset)
│ ├── analysis.py # Lógica de processamento de dados (Pandas/GeoPandas)
│ ├── network_design.py # Criação de grafos e algoritmos de roteamento
│ ├── ibge_downloader.py # Scripts de download do IBGE
│ ├── data_loader.py # Leitura de SHP, KML e CSV com tratamento de CRS
│ └── visualization.py # Geração de mapas e gráficos (Matplotlib)
├── data/ # Pasta para armazenamento de dados brutos
├── arquivos/ # Shapefiles locais (bairros, vias) e KMLs
└── main.py # Script de execução
```

## 🛠️ Pré-requisitos

O projeto utiliza bibliotecas robustas de geoprocessamento. Recomenda-se utilizar um ambiente virtual (venv ou conda).

```
pip install geopandas networkx matplotlib shapely pyogrio requests pandas
```

## 💻 Como Utilizar

A classe ModeloReset no módulo workflow.py atua como a interface principal.

Exemplo de Execução

```python
from modelo_reset import ModeloReset

# 1. Inicializar o modelo

# Define o CRS projetado para cálculos métricos (Ex: SIRGAS 2000 / UTM 23S para MG)

model = ModeloReset(crs_projetado=31983)

# 2. Carregar dados do IBGE (Download automático)

model.carregar_dados_ibge(ano_censo=2022, uf="MG")

# 3. Carregar dados locais

# É necessário fornecer os shapefiles da cidade e os pontos de articulação (KML)

model.carregar_dados_base(path_bairros="arquivos/bairros.shp", epsg_bairros=4326)
model.carregar_rede_viaria(path_vias="arquivos/sistema_viario.shp")
model.carregar_pontos_articulacao(path_pontos="arquivos/pontos_interesse.kml")

# 4. Processar indicadores

# Filtra setores censitários, calcula densidade e renda por bairro

model.processar_dados(municipio="Montes Claros")

# 5. Identificação de Polos

# Define manualmente polos planeados (futuros) e calcula os restantes estatisticamente

model.identificar_polos_planejados("Distrito Industrial")

# 6. Otimização da Rede

# Gera o grafo ponderado e calcula as rotas ideais

model.gerar_rotas_otimizadas(bairro_central="Centro")

# 7. Visualização

model.mostrar_polos() # Mapa de classificação dos bairros
model.plotar_densidade() # Mapa coroplético de densidade
model.mostrar_rotas_otimizadas() # Plotagem das linhas geradas

```

## 📊 Detalhes Metodológicos Implementados

### Cálculo do Peso Atrativo

No arquivo network_design.py, a função calcular_peso_atrativo aplica um fator de desconto ao comprimento real da via:

$$ Peso*{final} = Peso*{original} \times (1 - (FatorAtracao \times 0.5)) $$

Onde o FatorAtracao é inversamente proporcional à distância do Ponto de Articulação mais próximo (até um raio de 1000 metros). Isso força o algoritmo de Dijkstra a preferir ruas que passam perto de equipamentos urbanos importantes.

### Classificação de Polos

No arquivo analysis.py, os bairros são classificados automaticamente:

Consolidado: Alta densidade + Alta renda + Alto fluxo.

Emergente: Alta densidade + Baixa renda (prioridade social).

Planeado: Definido manualmente (novas urbanizações ou distritos industriais).

# 🤝 Contribuição

Sinta-se à vontade para abrir issues ou enviar pull requests para melhorar a eficiência dos algoritmos de grafos ou adicionar novos métodos de visualização.
