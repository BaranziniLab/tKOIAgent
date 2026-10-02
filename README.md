# tKOI Agent

A plugin for [Codex](https://openai.com/codex/), [Claude Code](https://claude.com/product/claude-code), and
[BioRouter](https://biorouter.ucsf.edu/) that prepares human
differential-expression data, runs [tKOI](https://github.com/BaranziniLab/tkoi),
and contextualizes enrichment by traversing the **exact igraph saved with that
analysis**.

The plugin contains two skills and one local MCP server:

- **tkoi-analysis:** R installation, tKOI setup, input formats, preprocessing,
  reproducible enrichment, and saved run artifacts.
- **tkoi-knowledge-graph:** connect the saved analysis, inspect its schema, search
  nodes, explore connection layers, find paths, and read enrichment results.
- **tkoi-graph MCP:** six read-only tools backed by R/igraph. No separate Neo4j
  database or SPOKE credentials are required.

Version 2 replaces the former Claude Desktop extension and its independent
remote graph connection. Desktop bundles, the bundled Python runtime and the
old general-purpose R/Neo4j server are retired from the current distribution.
Historical versions remain in Git history.

## Install prerequisites

Install R >= 4.1, a C++ compiler, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
See the [setup guide](skills/tkoi-analysis/references/setup.md) for macOS,
Windows and Linux instructions, R libraries, Bioconductor dependencies, and
runtime checks. The installed MCP process must see the same R library used by
your analysis.

From a checkout or extracted plugin directory:

```sh
Rscript skills/tkoi-analysis/scripts/setup.R
```

This installs tkoi >= 1.3.0 and missing dependencies. Installing the plugin alone
does not install R or its packages. The server's inline Python dependency is
managed by uv. Restart the MCP connection after setting up missing prerequisites.

## [Codex](https://openai.com/codex/)

```sh
codex plugin marketplace add BaranziniLab/tKOIAgent --ref main
codex plugin add tkoi-agent@tkoi
```

Use `$tkoi-analysis` for preparation/enrichment and `$tkoi-knowledge-graph` for
saved-result contextualization. Check the plugin and MCP tools in your Codex
session after installation. This repository supplies the portable Agent Plugins
format and a native Codex compatibility manifest.

## [Claude Code](https://claude.com/product/claude-code)

```sh
claude plugin marketplace add BaranziniLab/tKOIAgent
claude plugin install tkoi-agent@tkoi
```

Invoke `/tkoi-agent:tkoi-analysis` or `/tkoi-agent:tkoi-knowledge-graph`. For a
local checkout, launch `claude --plugin-dir /absolute/path/tKOIAgent` instead.
The Claude adapter discovers the same skills and starts the same graph server.

## [BioRouter](https://biorouter.ucsf.edu/)

```sh
biorouter skill install https://github.com/BaranziniLab/tKOIAgent
biorouter skill list
```

BioRouter imports both skills as one package and preserves their scripts.
Skill installation does not automatically attach an MCP server. Use the printed
installed package path to attach the included server to a BioRouter session:

```sh
biorouter run --with-extension "uv run --script /absolute/plugin/skills/tkoi-knowledge-graph/scripts/server.py" \
  --text "Use tkoi-analysis to help me prepare and analyze my differential-expression table."
```

The CLI command string requires paths without spaces. For other paths, configure
an external stdio extension in BioRouter with command `uv` and separate arguments
`run`, `--script`, and the full server path. The terminology "extension" here is
BioRouter's standard MCP connection; this plugin does not ship a desktop
extension bundle. Both skills also include direct R commands when MCP is not
attached.

## Prepare, run and connect

Input is a gene-level differential-expression table. The normalized CSV has
`gene_name` (human Ensembl gene ID), `logfc` (signed log2 fold change), and
`pvalue` (numeric in [0,1]). Raw expression/count matrices first require an
appropriate differential-expression analysis with biological replicates and a
specified contrast.

Read the [preprocessing guide](skills/tkoi-analysis/references/preprocessing.md)
for column mapping, Excel/TSV inputs, identifiers, missing values, duplicate
policies, bulk-count modeling, and single-cell pseudobulk preparation.

```sh
Rscript skills/tkoi-analysis/scripts/prepare.R de.csv prepared.csv \
  --gene-column ensembl_id --logfc-column log2FoldChange --pvalue-column pvalue
Rscript skills/tkoi-analysis/scripts/analyze.R prepared.csv tkoi-run \
  --permutations 1000 --cores 2 --seed 42
```

Supply `--graph /absolute/chosen-graph.rds` to use a custom igraph for enrichment.
The run saves `analysis.rds`, analyzed expression, enrichment tables, provenance,
preprocessing details and R session information. Output directories must be new
or empty. Review mapping coverage and exclusions before interpreting results.

Connect `/absolute/tkoi-run/analysis.rds` with `connect_analysis`. Retain the
returned `analysis_id` and pass it to every query:

| Tool | Purpose |
|---|---|
| `connect_analysis(path)` | Open the saved result and its original igraph |
| `get_graph_schema(analysis_id)` | Inspect real node/edge types and attributes |
| `search_nodes(analysis_id, query, node_type=None, limit=25)` | Resolve identifiers to graph node IDs |
| `get_node_neighbors(analysis_id, node_id, hops=1, limit=100)` | Explore 1-3 layers with hop distances and edge attributes |
| `get_path_between_nodes(analysis_id, source_id, target_id, max_hops=3)` | Return one unweighted shortest path within 1-6 hops |
| `get_enrichment_results(analysis_id, node_type, limit=25)` | Read the saved enrichment tables |

The server rejects results without a saved graph, stale analysis IDs and changed
files. It never substitutes the currently installed package graph. A connection
ID checks the saved file's identity; it does not authenticate manually edited
artifacts. The graph remains in the local R worker, while returned query results
are available to the selected coding agent and its configured model provider.

Direct access in R uses the same object:

```r
result = readRDS("tkoi-run/analysis.rds")
graph = tkoi::get_analysis_graph(result)
tkoi::get_neighboring_nodes(node_id, 2, subnetwork = graph)
```

The bundled network is undirected and records `edge_type`. Inspect actual
attributes before interpreting a custom network. Graph paths are associations,
not proof of causation, activation/inhibition or clinical validity. Truncated
query output is incomplete and cannot establish absence of a connection.

## Development and testing

```sh
claude plugin validate .claude-plugin/plugin.json --strict
Rscript tests/create_fixture.R /tmp/tkoi-agent-test
uv run --with 'mcp>=1.12,<2' python tests/smoke_mcp.py /tmp/tkoi-agent-test
python3 scripts/build_release.py
```

The smoke test runs real enrichment on a small graph, reloads the saved result,
queries it through MCP, verifies its edge types and topology, and rejects a
missing graph and stale IDs. Tests also exercise preprocessing validation. The
release ZIP contains both skills, the same graph tools, host adapters and guides.

## Documentation and formats

- [tKOI documentation](https://baranzinilab.github.io/tkoi/)
- [Agent workflow guide](https://baranzinilab.github.io/tkoi/articles/agent-workflows.html)
- [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins-reference)
- [Portable Agent Plugins format](https://agent-plugins.org/)
- [BioRouter](https://biorouter.ucsf.edu/)

MIT license. Maintained by the Baranzini Lab.
