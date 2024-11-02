import os
import sys

import toml


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Path Setup and Package Details
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

# IMPORTS ps I can be done not so dumbly
sys.path.insert(0, os.path.dirname(os.path.dirname(os. getcwd())))

# get package details directly from pyproject
pyproject_file = os.path.join(os.path.dirname(os.path.dirname(os. getcwd())), "pyproject.toml")
package_details = toml.load(pyproject_file).get("project")

project = package_details.get("name")
author = "Darik A. O'Neil"
#author = f"{package_details.authors}"  # f-string because maybe weird sphinx stuff if it gets list, not sure
release = package_details.get("version")


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Sphinx Configuration
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""
master_docs = 'index'

extensions = [
    'sphinx.ext.todo',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.intersphinx',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    "autoclasstoc",
    'sphinxcontrib.autodoc_pydantic',
    'sphinx_autodoc_typehints']

autodoc_default_options = {
    'members': True,
    'special-members': True,
    'private-members': True,
    'inherited-members': True,
    'undoc-members': True,
    'exclude-members': '__weakref__',
}
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

todo_include_todos = True


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Sphinx Autodoc Typehints
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""

typehints_defaults = 'comma'


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// AutoClassToc Configuration
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


autoclasstoc_sections = [
    'read-only',
    ]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Custom Sections (AutoClassToc)
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


from autoclasstoc import Section


class ReadOnlySection(Section):
    key = 'read-only'
    title = "Read-Only Properties:"

    def predicate(self, name, attr, meta):
        return 'read-only' in meta
