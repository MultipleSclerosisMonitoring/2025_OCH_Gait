import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = '2025_OCH_GAIT'
copyright = '2026, Clarissa Otañez'
author = 'Clarissa Otañez'
release = '0.1'

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.graphviz",
    "sphinx.ext.napoleon",
]

templates_path = ['_templates']
exclude_patterns = []

html_theme = 'alabaster'
html_static_path = ['_static']
