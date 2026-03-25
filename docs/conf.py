from __future__ import annotations

import datetime


project = "asynclit"
author = "asynclit contributors"
copyright = f"{datetime.datetime.now().year}, {author}"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "asynclet-spec.md"]

html_theme = "alabaster"

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "strikethrough",
]

autodoc_typehints = "description"
