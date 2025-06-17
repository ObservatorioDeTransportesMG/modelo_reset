import ast
import os
import os.path
import shutil
import subprocess
import unicodedata
import webbrowser
import zipfile

import processing
import requests

# Import the code for the dialog

# Initialize Qt resources from file resources.py

lista_estados = {
	"": "",
	"Acre": ("AC", "12"),
	"Alagoas": ("AL", "27"),
	"Amapá": ("AP", "16"),
	"Amazonas": ("AM", "13"),
	"Bahia": ("BA", "29"),
	"Ceará": ("CE", "23"),
	"Espírito Santo": ("ES", "32"),
	"Distrito Federal": ("DF", "53"),
	"Goiás": ("GO", "52"),
	"Maranhão": ("MA", "21"),
	"Mato Grosso": ("MT", "51"),
	"Mato Grosso do Sul": ("MS", "50"),
	"Minas Gerais": ("MG", "31"),
	"Pará": ("PA", "15"),
	"Paraíba": ("PB", "25"),
	"Paraná": ("PR", "41"),
	"Pernambuco": ("PE", "26"),
	"Piauí": ("PI", "22"),
	"Rio de Janeiro": ("RJ", "33"),
	"Rio Grande do Norte": ("RN", "24"),
	"Rio Grande do Sul": ("RS", "43"),
	"Rondônia": ("RO", "11"),
	"Roraima": ("RR", "14"),
	"Santa Catarina": ("SC", "42"),
	"São Paulo - exceto capital": ("SP_Exceto_Capital", "35"),
	"São Paulo - Capital": ("SP_Capital", "35"),
	"Sergipe": ("SE", "28"),
	"Tocantins": ("TO", "17"),
}
lista_estados_22 = {
	"": "",
	"Acre": ("AC", "12"),
	"Alagoas": ("AL", "27"),
	"Amapá": ("AP", "16"),
	"Amazonas": ("AM", "13"),
	"Bahia": ("BA", "29"),
	"Ceará": ("CE", "23"),
	"Espírito Santo": ("ES", "32"),
	"Distrito Federal": ("DF", "53"),
	"Goiás": ("GO", "52"),
	"Maranhão": ("MA", "21"),
	"Mato Grosso": ("MT", "51"),
	"Mato Grosso do Sul": ("MS", "50"),
	"Minas Gerais": ("MG", "31"),
	"Pará": ("PA", "15"),
	"Paraíba": ("PB", "25"),
	"Paraná": ("PR", "41"),
	"Pernambuco": ("PE", "26"),
	"Piauí": ("PI", "22"),
	"Rio de Janeiro": ("RJ", "33"),
	"Rio Grande do Norte": ("RN", "24"),
	"Rio Grande do Sul": ("RS", "43"),
	"Rondônia": ("RO", "11"),
	"Roraima": ("RR", "14"),
	"Santa Catarina": ("SC", "42"),
	"São Paulo": ("SP", "35"),
	"Sergipe": ("SE", "28"),
	"Tocantins": ("TO", "17"),
}
lista_municipios = {}


class DadosCenso:
	"""QGIS Plugin Implementation."""

	def __init__(self):
		"""Constructor.

		:param iface: An interface instance that will be passed to this class
			which provides the hook by which you can manipulate the QGIS
			application at run time.
		:type iface: QgsInterface
		"""
		# Save reference to the QGIS interface
		# initialize plugin directory
		self.plugin_dir = os.path.dirname(__file__)
