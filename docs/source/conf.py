import os
import sys
from datetime import date

import toml

# IMPORTS ps I can be done not so dumbly
sys.path.insert(0, os.path.dirname(os.path.dirname(os. getcwd())))

# get package details directly from pyproject
pyproject_file = os.path.join(os.path.dirname(os.path.dirname(os. getcwd())), "pyproject.toml")
package_details = toml.load(pyproject_file).get("project")

# get date for copyright
today = date.today().year

project = package_details.get("name")
#copyright = "".join([today, f" {package_details.authors}"])
#author = f"{package_details.authors}"  # f-string because maybe weird sphinx stuff if it gets list, not sure
release = package_details.get("version")

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.intersphinx',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints']

typehints_defaults = 'comma'
templates_path = ['_templates']
exclude_patterns = []

language = 'en'

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'ipykernel': ('https://ipykernel.readthedocs.io/en/stable/', None),
    'ipython': ('https://ipython.readthedocs.io/en/stable/', None),
    'joblib': ('https://joblib.readthedocs.io/en/latest/', None),
}

source_suffix = ".rst"

html_theme = 'sphinx_rtd_theme'

pygments_style = "sphinx"

latex_engine = "pdflatex"

todo_include_todos = True
