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
    'special-members': False,
    'private-members': False,
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

always_document_param_types = True

typehints_fully_qualified = False

typehints_document_rtype = True

always_use_bars_union = True

simplify_optional_unions = False

typehints_use_signature = False

typehints_use_signature_return = False


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// AutoClassToc Configuration
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


autoclasstoc_sections = [
    'read-only-properties',
    'read-write-properties',
    'public-methods-without-dunders',
    ]


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Custom Sections (AutoClassToc)
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


from autoclasstoc import Section
from autoclasstoc import PublicMethodsWithoutDunders


class PropertiesSection(Section):
    key = 'read-write-properties'
    title = "Properties:"

    def predicate(self, name, attr, meta):
        return 'read-write-properties' in meta


class ReadOnlyPropertiesSection(Section):
    key = 'read-only-properties'
    title = "Read-Only Properties:"

    def predicate(self, name, attr, meta):
        return 'read-only-properties' in meta


"""
class PublicAttributes(Section):
    key = 'public-attrs'
    title = "Public Attributes:"

    def predicate(self, name, attr, meta):
        return 'attribute' in meta
    
    
class PublicInstanceMethods(Section):
    key = 'public-methods'
    title = "Public Methods:"

    def predicate(self, name, attr, meta):
        return 'method' in meta
    

class PublicClassMethods(Section):
    key = 'public-class-methods'
    title = "Public Class Methods:"

    def predicate(self, name, attr, meta):
        return 'classmethod' in meta
    
    
class PublicStaticMethods(Section):
    key = 'public-static-methods'
    title = "Public Static Methods:"

    def predicate(self, name, attr, meta):
        return 'staticmethod' in meta
    

class PrivateAttributes(Section):
    key = 'private-attrs'
    title = "Private Attributes:"
    
    def predicate(self, name, attr, meta):
        return 'private' in meta
    
    
class PrivateInstanceMethods(Section):
    key = 'private-methods'
    title = "Private Methods:"
    
    def predicate(self, name, attr, meta):
        return 'private' in meta
    
    
class PrivateClassMethods(Section):
    key = 'private-class-methods'
    title = "Private Class Methods:"
    
    def predicate(self, name, attr, meta):
        return 'private' in meta and 'classmethod' in meta
    

class PrivateStaticMethods(Section):
    key = 'private-static-methods'
    title = "Private Static Methods:"
    
    def predicate(self, name, attr, meta):
        return 'private' in meta and 'staticmethod' in meta
"""
