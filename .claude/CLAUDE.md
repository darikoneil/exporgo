## Project Rules

## Running code

Always use `uv run` to execute Python code and tools. Never call `python`, `pytest`, `ruff`, or other tools directly. They may not resolve to the project's virtual environment.

- Run a script: `uv run python script.py`
- Run a module: `uv run python -m module_name`
- Run a tool: `uv run pytest`, `uv run ruff check .`
- One-off tool (not a project dependency): `uvx <tool>`

## Package management

This project uses uv. Do not use pip, pip-tools, poetry, or conda.

- Add runtime dependency: `uv add <package>` (writes to `[project.dependencies]`)
- Add dev dependency: `uv add --dev <package>` (writes to `[dependency-groups]` per PEP 735)
- Remove dependency: `uv remove <package>`
- Sync environment from lockfile: `uv sync`
- Regenerate lockfile from constraints: `uv lock`
- Upgrade locked versions: `uv lock --upgrade`
- Commit `uv.lock` to version control (current uv guidance is to commit it for applications, CLIs, and libraries)

## Linting and formatting

- Tool: ruff (handles both linting and formatting)
- Always format code before linting avoid unnecessary linting errors.
- Format: `uv run ruff format .`
- Check formatting: `uv run ruff format --check .`
- Lint: `uv run ruff check .`
- Lint and auto-fix: `uv run ruff check --fix .`
- Configuration lives in `pyproject.toml` under `[tool.ruff]`
- Ignore linting errors that are not relevant to the diff unless otherwise instructed.

## Code style
When writing python code
- For Python style and linting, follow the Ruff configuration in `pyproject.toml`.
- Do not introduce formatting that would conflict with `uv ruff format`.
- Import sorting is handled by ruff (`isort` rules enabled via `select = ["I"]`)
- Do not add `# type: ignore` comments without an error code
- Do not silence Ruff rules with `noqa` unless there is a concrete justification in a code comment.
- Prefer explicit names over abbreviations.
- Preface function names not intended to be used outside of the current file with `_`
- Do not include function names in __all__ if they are not intended or likely to be used directly by end-users
- When conducting large changes or implementations, start a planning conversation with the user to discuss changes and potential approaches
- When there are more than three arguments to a function and at least one argument 
  has a default value, enforce all arguments with defaults to be keyword-only.
- When there are more than three arguments to a function that do not have default 
  values, consider whether any or all arguments ought to be encapsulated in a data 
  structure
- Don't use from __future__ import annotations when using python 3.12 or later.
- Use full import names for local imports (e.g., use from this_project.module import 
  function instead of from .module import function)

## Docstyle
When editing Python:
- Write module, class, and function docstrings in Google style.
- Always include a one-line summary for all functions (even private ones). 
- When appropriate, add expanded documentation for the end-user.
- Documentation should describe both the user-focused API and scientific or mathemathical information when relevant.
- Include latex equations or formulas when possible.
- Add interpetation guidance when possible.
- Always add Args / Returns / Raises in the docstring when applicable. When useful, 
    include warning admonition, tips, examples, and information on performance 
    (e.g., space complexity, time complexity, wall-clock speed)
- Add type hints for all functions.
- Refrain from add verbose line-by-line comments to the code when the code is self-documenting.

## Type checking

- Tool: pyrefly
- Run: `uv run pyrefly check`
- Configuration lives in `pyproject.toml` under `[tool.pyrefly]`

## What NOT to do

- Do not create or activate virtual environments manually. uv manages `.venv/` automatically.
- Do not install packages globally or with `pip install`.
- Do not create `requirements.txt` for dependency management. Use `pyproject.toml` and `uv.lock`.
- Do not run `python setup.py` commands.
- Do not add dependencies to pyproject.toml by hand. Use `uv add`.
- If you must edit pyproject.toml directly, write dev dependencies under `[dependency-groups]` (PEP 735), not the legacy `[tool.uv.dev-dependencies]` table.
- Do not ever commit or push to version control. Only the user commits and pushes to 
  version control.
