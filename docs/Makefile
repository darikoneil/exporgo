# Minimal makefile for Sphinx documentation (uv-driven).
# Run e.g. `make html`; SPHINXBUILD defaults to `uv run sphinx-build` to honor the
# project's uv-only workflow.

SPHINXBUILD   ?= uv run sphinx-build
SPHINXOPTS    ?=
SOURCEDIR     = source
BUILDDIR      = build

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all: route any target (html, clean, linkcheck, ...) to sphinx-build.
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
