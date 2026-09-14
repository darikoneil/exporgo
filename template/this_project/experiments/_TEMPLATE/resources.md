# Resources: <experiment name>

Where this experiment's data and code physically live. Canonical locations only (GitHub URLs, UNC
share paths like `\\ktdata\snlkt\...`); local drive letters and clone folders differ per machine.
Never assume a path — if it's not here, it's not known.

## Code

- **Repo(s):** <https://github.com/org/repo> — <what part of the pipeline it holds>
- **Entry points:** <script/module a reader starts from>
- **Environment:** uv project (`uv sync`); Python <version>

## Data

- **Raw:** `\\ktdata\snlkt\data\<...>`
- **Processed / derived:** `\\ktdata\snlkt\processed\<...>`
- **Key datasets:** <session ids / recording ranges / manifest file>
- **Access notes:** <mounts, permissions, size, anything that bites>

## Outputs

- **Figures:** <where panels for this experiment go, e.g. `../../visuals/figures/<...>`>
- **Results / artifacts:** <where derived results are kept>
