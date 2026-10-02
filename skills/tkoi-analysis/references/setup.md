# Environment setup

Use a terminal in the analysis project. Commands here run on the machine where
the coding agent and MCP server execute, which may differ from the desktop.

## R and build tools

1. Run `Rscript --version`. tKOI requires R >= 4.1.0; use a current supported R
   release for new installations. If absent, install R from
   [CRAN](https://cran.r-project.org/), choosing the operating system:
   - **macOS:** use the CRAN installer matching Apple Silicon or Intel, or
     `brew install r` when Homebrew is the chosen package manager. Install
     Xcode Command Line Tools with `xcode-select --install` if a C++ compiler is
     missing. Complete any operating-system installer prompts.
   - **Windows:** install R for Windows and the matching
     [Rtools](https://cran.r-project.org/bin/windows/Rtools/). Ensure the selected
     R `bin` directory is on PATH, or invoke its full `Rscript.exe` path.
   - **Linux:** follow the distribution instructions linked from CRAN. On
     Debian/Ubuntu, a typical setup is
     `sudo apt-get install r-base r-base-dev build-essential libcurl4-openssl-dev libssl-dev libxml2-dev`.
     Bioconductor dependencies can require additional distribution libraries;
     resolve the specific missing header/library reported by installation.
2. Verify `Rscript --vanilla -e 'cat(as.character(getRversion()), "\n")'`.
3. Use a fresh R process for upgrades. If other analyses depend on an existing
   library, create a project library and set `R_LIBS_USER` for both analysis
   commands and the MCP server instead of replacing their packages in place.

## Install tKOI

Run the included setup script by absolute path:

```sh
Rscript /absolute/plugin/skills/tkoi-analysis/scripts/setup.R
```

It installs missing `remotes`, `BiocManager`, `jsonlite`, and `readxl`, installs
missing `clusterProfiler` and `org.Hs.eg.db` through Bioconductor, and installs
`BaranziniLab/tkoi@v1.3.0` if tkoi >= 1.3.0 is not available. It leaves a newer
tKOI version in place. For exact reproducibility, use an isolated library and
pin tkoi to that tag, then retain `sessionInfo.txt` and your dependency lockfile.
An existing incompatible Bioconductor installation may need repair using
`BiocManager::valid()` and a release compatible with that R installation.

```r
install.packages(c("remotes", "BiocManager", "jsonlite", "readxl"))
BiocManager::install(c("clusterProfiler", "org.Hs.eg.db"), ask = FALSE, update = FALSE)
remotes::install_github("BaranziniLab/tkoi@v1.3.0", upgrade = "never")
```

Verify in a new process:

```sh
Rscript --vanilla -e 'stopifnot(packageVersion("tkoi") >= "1.3.0"); stopifnot(is.function(tkoi::get_analysis_graph)); cat("ready\n")'
```

The Shiny UI is optional for this workflow. Command-line enrichment and graph
queries do not require its optional Shiny dependencies.

## Graph server runtime

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) using the
method appropriate for your operating system. The plugin launches:

```sh
uv run --script /absolute/plugin/skills/tkoi-knowledge-graph/scripts/server.py
```

The script declares Python >= 3.10 and the official MCP Python SDK v1 dependency;
uv manages those in an isolated environment. The R worker separately needs R,
tkoi >= 1.3.0 and jsonlite in its R library. Restart the agent's MCP connection
after installing missing prerequisites. If `Rscript` is not on PATH, set
`TKOI_RSCRIPT` to its full executable path in the host's MCP environment. Set
`R_LIBS_USER` there too when using a project library. Paths containing spaces
must remain one argument; JSON argument arrays already preserve this.

See the [plugin README](../../../README.md) for the [Codex](https://openai.com/codex/),
[Claude Code](https://claude.com/product/claude-code), and
[BioRouter](https://biorouter.ucsf.edu/) installation commands. The server uses local stdio and reads the
analysis file you explicitly connect. It does not need a Neo4j endpoint or
SPOKE credentials. It retains one graph connection per server process; reconnect
when switching analyses and use the newly returned analysis ID.

The graph remains local to the R worker. Query results are returned to the
selected coding agent and may be sent to that agent's model provider according
to its normal configuration. Local graph access does not imply local inference.
