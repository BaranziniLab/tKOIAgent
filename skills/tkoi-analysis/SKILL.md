---
name: tkoi-analysis
description: Set up R and tKOI, prepare human differential-expression results, run knowledge-graph enrichment, and save the exact analysis graph for contextualization. Use for tKOI analyses and their input preparation.
---

# tKOI analysis

This skill and `tkoi-knowledge-graph` form the tKOI agent plugin for Codex,
Claude Code, and BioRouter. Use your coding agent's normal shell and file tools
for R execution. The bundled MCP server provides graph queries after analysis.

## Setup

Read [setup.md](references/setup.md) when R, tKOI, or the graph connection is
missing. Check `Rscript --version`, then check installed package versions in a
fresh R process. Install R if needed, its compiler toolchain, and tkoi >= 1.3.0
using `scripts/setup.R`. Keep project libraries explicit when one is in use.
Paths to scripts below are relative to this skill directory; resolve them to
absolute paths before running from another working directory.

## Prepare the input

Read [preprocessing.md](references/preprocessing.md) before transforming input.
Identify the organism, data type, contrast direction, gene identifier type,
log-fold-change scale, and p-value column. tKOI uses a human network. Ask for
missing experimental design information before fitting a differential-expression
model. Raw counts, normalized expression, and differential-expression results
are different input stages.

The prepared CSV needs exactly one row per mapped gene with:

| Column | Meaning |
|---|---|
| `gene_name` | Human Ensembl gene ID, without a version suffix |
| `logfc` | Finite signed log2 fold change for the stated contrast |
| `pvalue` | Numeric p-value in [0,1], with its raw/adjusted meaning recorded |

The preparation helper reads CSV, TSV, tab-delimited TXT, and XLSX. It maps
Ensembl, HGNC symbols, or Entrez IDs through the installed tKOI annotations;
reports unmapped genes; and rejects ambiguous mappings, invalid values, and
duplicate mapped genes by default. Review any exclusions and mapping coverage.
Do not silently average duplicates or fabricate missing statistics.

```sh
Rscript /absolute/plugin/skills/tkoi-analysis/scripts/prepare.R \
  differential-expression.csv prepared.csv \
  --gene-column gene --logfc-column log2FoldChange --pvalue-column pvalue \
  --id-type ensembl
```

## Run and retain the graph

Choose the graph before running. Use `tkoi::tkoi_net` by default or a specified
igraph RDS via `--graph`. Never analyze one graph and contextualize against a
different database or a newer package graph.

```sh
Rscript /absolute/plugin/skills/tkoi-analysis/scripts/analyze.R \
  prepared.csv tkoi-run --permutations 1000 --cores 2 --seed 42
```

The helper saves `analysis.rds` (a `tKOIList` with its original `subnetwork`),
the actual analyzed input, enrichment CSVs, preprocessing report if present,
`provenance.json`, and `sessionInfo.txt`. It refuses a nonempty output directory.
Two permutations are appropriate only for a software smoke test; use a suitable
permutation count for the scientific question and inspect stability. The default
1000 is a starting point, not a guarantee of calibrated significance.

Equivalent R code:

```r
set.seed(42)
graph = tkoi::tkoi_net  # or readRDS("chosen-graph.rds")
result = tkoi::run_tkoi(expression_data, subnetwork = graph,
                       n_permutation = 1000, n_cores = 2,
                       keep_permutations = FALSE)
stopifnot(identical(tkoi::get_analysis_graph(result), graph))
saveRDS(result, "analysis.rds")
```

## Contextualize

Load the bundled [tkoi-knowledge-graph skill](../tkoi-knowledge-graph/SKILL.md).
Call `connect_analysis` with the absolute `analysis.rds` path, retain its
`analysis_id`, and pass that ID to every schema, search, neighborhood, path, and
enrichment query. Inspect the schema before describing relation types.

Distinguish enrichment statistics from graph connectivity and external
literature. A path supports a network association or a hypothesis, not proof of
causation, effect direction, or a mechanism. Report graph identity, run settings,
mapping/exclusion counts, returned node IDs, edge endpoints and relation types, and any
query truncation alongside the interpretation.
