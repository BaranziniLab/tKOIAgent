# SKILL.md  
## tKOIAgent — Transcriptomics Knowledge Graph–Driven Omics Integration Agent

---

## 1. Purpose of This Skill

`tKOIAgent` is a **specialized multi-tool analysis agent** designed to:

1. Analyze **transcriptomics / gene expression data**
2. Convert differential expression results into **knowledge graph–based embeddings**
3. Perform **network propagation and enrichment analysis** using **tkoi**
4. Contextualize results using **AI-driven biological reasoning**
5. Validate and explore findings using the **SPOKE Neo4j biological knowledge graph**

This skill document **must be read and followed whenever the LLM invokes or decides to invoke `tKOIAgent`**.

---

## 2. High-Level Conceptual Model

`tKOIAgent` operates via **two coordinated toolchains**:

### Toolchain A — Local Computation & R Execution
Used for:
- Setting working directories and managing files
- Cleaning and processing transcriptomics data
- Running R scripts for data transformation
- Executing `tkoi` pathway/network analysis
- Exporting structured results (CSV, Excel, RDA)

**Available Tools:**
| Tool | Description |
|------|-------------|
| `set_workdir` | Set working directory for all operations |
| `get_state` | Get current server state and configuration |
| `create_R_file` | Create new R script files |
| `write_R_code` | Write R code to files (replaces content) |
| `append_R_code` | Append R code to existing files |
| `run_R_script` | Execute R scripts (supports long-running tkoi) |
| `run_R_expression` | Execute single R expressions |
| `list_exports` | List files in working directory |
| `read_export` | Read file contents |
| `preview_table` | Preview CSV/TSV data |
| `inspect_R_objects` | Inspect R objects from saved session |
| `ggplot_style_check` | Check ggplot2 code for publication quality |
| `which_R` | Find R executable |
| `list_R_files` | List R script files |
| `set_primary_file` | Set primary R script |

### Toolchain B — Knowledge Graph Querying (Neo4j / Cypher)
Used for:
- Querying biological relationships in SPOKE
- Connecting differentially expressed genes to:
  - Pathways
  - Diseases
  - Cell types
  - Anatomical structures
  - Molecular functions
- Validating and contextualizing tkoi results

**Available Tools:**
| Tool | Description |
|------|-------------|
| `get_knowledge_graph_schema` | Get SPOKE schema (nodes, relationships, properties) |
| `query_knowledge_graph` | Execute custom Cypher queries (READ-ONLY) |
| `search_nodes` | Search nodes by name/identifier |
| `get_node_neighbors` | Get connected nodes |
| `get_path_between_nodes` | Find paths between nodes |
| `get_gene_pathways` | Get pathways for genes |
| `get_gene_disease_associations` | Get disease associations for genes |

The **goal** is to move from **raw gene expression → interpretable biological insight**.

---

## 3. Invocation Preconditions (MANDATORY CHECKS)

Before proceeding, the LLM **must verify all conditions below**.

### 3.1 Required User Inputs

The user **must provide**:

#### A. A data file path  
The file must be readable into an R `data.frame`.

Accepted formats:
- `.csv`
- `.tsv`
- `.txt` (delimiter-separated)
- `.xlsx` / `.xls`

> If the file **cannot be read into R**, STOP and request a valid file.

---

#### B. Required Data Columns (Flexible Naming Allowed)

The uploaded dataset **must contain all three components**:

| Required Component | Description | Acceptable Variations |
|-------------------|------------|-----------------------|
| Gene identifiers | Any valid gene ID system | Ensembl IDs, HGNC symbols, mouse gene IDs, homologs |
| Log fold change | Differential expression magnitude | `logFC`, `log_fc`, `logFoldChange`, `log2FoldChange`, variants |
| P-values | Statistical significance | `pvalue`, `p_value`, `P.Value`, `pval`, variants |

> ✅ Column names may vary  
> ❌ Missing any component → STOP and ask user to re-upload or clarify

---

### 3.2 Study Context Requirement (CRITICAL)

The user **must provide study context**, including at least:

- Study type (e.g., disease vs control, perturbation, time series)
- Tissue or cell type
- Condition being compared
- Comparison groups
- Any relevant experimental or biological background

⚠ **If no study context is provided:**
- STOP execution
- Prompt the user for clarification
- DO NOT proceed with analysis

---

## 4. Working Directory Rules

Once inputs are validated:

1. Extract the directory containing the user's data file  
2. Call `set_workdir` with this directory path

### Example
```
User file path:
~/Desktop/project/data.csv

Working directory:
~/Desktop/project/
```

All generated files **must be created in this directory**.

---

## 5. Step 1 — Data Cleaning & Harmonization

### 5.1 Create `clean_data.R`

In the working directory, generate an R script using:

```python
create_R_file(filename="clean_data.R", scaffold=True)
```

---

### 5.2 Responsibilities of `clean_data.R`

The script must:

1. Load the input file into R
2. Identify gene ID format
3. Convert gene identifiers to **Ensembl IDs** if needed
   - HGNC → Ensembl
   - Mouse → Human homolog (when appropriate)
4. Normalize column names to **exact required names**
5. Compute FDR if not present
6. Export cleaned datasets

---

### 5.3 Final Required Data Structure (EXACT COLUMN NAMES)

The cleaned `data.frame` **must contain exactly these 4 columns with these exact names**:

| Column Name | Description |
|------------|------------|
| `gene_name` | Ensembl gene ID (e.g., ENSG00000141510) |
| `logfc` | Log fold change (lowercase) |
| `pvalue` | Raw p-value (lowercase, no underscore) |
| `fdr` | FDR-adjusted p-value (lowercase) |

⚠️ **CRITICAL**: Column names must be exactly `gene_name`, `logfc`, `pvalue`, `fdr` — no variations.

---

### 5.4 Required Output Files from clean_data.R

Export exactly **2 files**:

1. **Full cleaned dataset**
```
dge_data.csv
```

2. **Significant genes only (FDR ≤ 0.05)**
```
dge_data_significant.csv
```

Both files must have the exact 4 columns: `gene_name`, `logfc`, `pvalue`, `fdr`

---

### 5.5 Example clean_data.R Structure

```r
# Load required libraries
library(data.table)

# Read input data
data = fread("input_file.csv")  # Adjust filename as needed

# Rename columns to required exact names
# (Adjust source column names based on user's data)
colnames(data)[colnames(data) == "original_gene_col"] = "gene_name"
colnames(data)[colnames(data) == "original_logfc_col"] = "logfc"
colnames(data)[colnames(data) == "original_pvalue_col"] = "pvalue"

# Compute FDR if not present
data$fdr = p.adjust(data$pvalue, method = "BH")

# Select only required columns
dge_data = data[, .(gene_name, logfc, pvalue, fdr)]

# Export full dataset
fwrite(dge_data, "dge_data.csv")

# Export significant genes only
dge_data_significant = dge_data[fdr <= 0.05]
fwrite(dge_data_significant, "dge_data_significant.csv")

cat("Exported", nrow(dge_data), "total genes\n")
cat("Exported", nrow(dge_data_significant), "significant genes (FDR <= 0.05)\n")
```

Use `write_R_code` to write the script, then `run_R_script` to execute.

---

## 6. Step 2 — Running tkoi Analysis

### 6.1 Create `run_tkoi.R`

Generate a second R script:

```python
create_R_file(filename="run_tkoi.R", scaffold=True)
```

---

### 6.2 Package Installation Logic

At the start of the script, check for **`tkoi`** (all lowercase):

```r
if (!requireNamespace("tkoi", quietly = TRUE)) {
  if (!requireNamespace("devtools", quietly = TRUE)) {
    install.packages("devtools")
  }
  devtools::install_github("Broccolito/tkoi")
}
library(tkoi)
library(data.table)
library(writexl)
```

⚠️ **CRITICAL**: The library is `tkoi` (all lowercase), not `tKOI`.

---

### 6.3 Load Expression Data

```r
expression_data = fread("dge_data.csv")
cat("Loaded", nrow(expression_data), "genes\n")
head(expression_data)
```

---

### 6.4 Compute FDR Threshold

Before running `run_tkoi()`:

- Determine the **highest raw p-value** that corresponds to `fdr <= 0.05`
- Pass this as `pvalue_threshold`

```r
fdr_threshold = max(expression_data$pvalue[expression_data$fdr <= 0.05], na.rm = TRUE)
cat("FDR threshold (p-value corresponding to FDR=0.05):", fdr_threshold, "\n")
```

---

### 6.5 Run tkoi (EXACT PARAMETERS — DO NOT MODIFY)

```r
tkoi_result = run_tkoi(
  expression_data = expression_data,
  subnetwork = tkoi::tkoi_net,
  pvalue_threshold = fdr_threshold,
  logfc_threshold = 0.25,
  indirect_link_threshold = 3,
  topology_similarity = 0.9,
  n_permutation = 30,
  damping_factor = 0.85,
  maximum_iteration = 500
)
```

⚠️ **CRITICAL RULES:**
- **DO NOT change any parameters** unless explicitly requested by user
- **`n_permutation = 30`** is required — higher values will take too long
- **DO NOT use any other tkoi functions** (no enrichment, no plotting, no other analysis)
- Only run `run_tkoi()` and export results

---

### 6.6 Runtime Expectations

- Execution may take **30–60 minutes**
- Use `timeout_sec=3600` (1 hour) when calling `run_R_script`
- The LLM **must remain patient**
- Do not assume failure prematurely

---

## 7. Step 3 — Export tkoi Results

### 7.1 Save Raw R Object (EXACT NAMING)

```r
save(tkoi_result, file = "tkoi_result.rda")
```

⚠️ **CRITICAL**: 
- Variable must be named `tkoi_result`
- File must be named `tkoi_result.rda`
- Do not change these names

---

### 7.2 Understanding Network Summary Statistics

`tkoi_result@network_summary_statistics` is a **list of data.frames**.

Each element represents one modality:
- Anatomy
- CellType
- Complex
- Pathway
- Disease
- BiologicalProcess
- CellularComponent
- MolecularFunction
- Gene

---

### 7.3 Export Full Summary as Multi-Tab Excel

Use **`writexl`** library (NOT openxlsx):

```r
# Export full summary as multi-tab Excel
write_xlsx(tkoi_result@network_summary_statistics, "tkoi_summary.xlsx")
cat("Exported tkoi_summary.xlsx\n")
```

⚠️ **CRITICAL**: 
- Use `writexl::write_xlsx()`, NOT `openxlsx`
- Export as **single multi-tab Excel file**, NOT separate CSV files
- File must be named `tkoi_summary.xlsx`

---

### 7.4 Export Significant-Only Summary as Multi-Tab Excel

Filter each data.frame to FDR ≤ 0.05, then export:

```r
# Filter each modality to significant results only
sig_list = lapply(tkoi_result@network_summary_statistics, function(df) {
  if ("fdr" %in% colnames(df)) {
    df[df$fdr <= 0.05, ]
  } else {
    df  # Return as-is if no fdr column
  }
})

# Remove empty data.frames
sig_list = sig_list[sapply(sig_list, nrow) > 0]

# Export as multi-tab Excel
write_xlsx(sig_list, "tkoi_summary_significant.xlsx")
cat("Exported tkoi_summary_significant.xlsx\n")
```

⚠️ **CRITICAL**: 
- File must be named `tkoi_summary_significant.xlsx`
- Must be multi-tab Excel, NOT separate CSV files

---

### 7.5 Complete run_tkoi.R Template

```r
# =============================================================================
# run_tkoi.R - tkoi Network Propagation Analysis
# =============================================================================

# Install tkoi if needed
if (!requireNamespace("tkoi", quietly = TRUE)) {
  if (!requireNamespace("devtools", quietly = TRUE)) {
    install.packages("devtools")
  }
  devtools::install_github("Broccolito/tkoi")
}

# Load libraries
library(tkoi)
library(data.table)
library(writexl)

# Load expression data
expression_data = fread("dge_data.csv")
cat("Loaded", nrow(expression_data), "genes\n")

# Compute FDR threshold
fdr_threshold = max(expression_data$pvalue[expression_data$fdr <= 0.05], na.rm = TRUE)
cat("FDR threshold:", fdr_threshold, "\n")

# Run tkoi analysis (DO NOT MODIFY PARAMETERS)
cat("Starting tkoi analysis... This may take 30-60 minutes.\n")
tkoi_result = run_tkoi(
  expression_data = expression_data,
  subnetwork = tkoi::tkoi_net,
  pvalue_threshold = fdr_threshold,
  logfc_threshold = 0.25,
  indirect_link_threshold = 3,
  topology_similarity = 0.9,
  n_permutation = 30,
  damping_factor = 0.85,
  maximum_iteration = 500
)
cat("tkoi analysis complete.\n")

# Save raw R object
save(tkoi_result, file = "tkoi_result.rda")
cat("Saved tkoi_result.rda\n")

# Export full summary as multi-tab Excel
write_xlsx(tkoi_result@network_summary_statistics, "tkoi_summary.xlsx")
cat("Exported tkoi_summary.xlsx\n")

# Export significant-only summary as multi-tab Excel
sig_list = lapply(tkoi_result@network_summary_statistics, function(df) {
  if ("fdr" %in% colnames(df)) {
    df[df$fdr <= 0.05, ]
  } else {
    df
  }
})
sig_list = sig_list[sapply(sig_list, nrow) > 0]
write_xlsx(sig_list, "tkoi_summary_significant.xlsx")
cat("Exported tkoi_summary_significant.xlsx\n")

cat("All exports complete.\n")
```

---

## 8. Expected Output Files (COMPLETE LIST)

After running `clean_data.R` and `run_tkoi.R`, the working directory should contain **exactly these files**:

### R Scripts (2 files)
| File | Description |
|------|-------------|
| `clean_data.R` | Data cleaning script |
| `run_tkoi.R` | tkoi analysis script |

### Data Outputs (5 files)
| File | Description |
|------|-------------|
| `dge_data.csv` | Full cleaned DGE data (4 columns: gene_name, logfc, pvalue, fdr) |
| `dge_data_significant.csv` | FDR-significant genes only |
| `tkoi_result.rda` | Complete tkoi result R object |
| `tkoi_summary.xlsx` | Full network summary (multi-tab Excel) |
| `tkoi_summary_significant.xlsx` | Significant network summary (multi-tab Excel) |

⚠️ **DO NOT create any other files** during initial analysis. Users may request additional files/analyses later.

---

## 9. Step 4 — Contextual Analysis & Interpretation

After tkoi completes, use `read_export` or `preview_table` to load:

- `dge_data_significant.csv`
- `tkoi_summary_significant.xlsx` (use `read_export` to examine)

### Interpretation Rules

1. `dge_data_significant.csv`
   - Represents **significantly regulated genes**

2. `tkoi_summary_significant.xlsx`
   - Represents **key network nodes after propagation**
   - Each tab = one modality (Pathway, Disease, CellType, etc.)

---

### Focus Node Types

Prioritize:
- Anatomy
- CellType
- Complex
- Pathway
- Disease
- BiologicalProcess
- CellularComponent
- MolecularFunction
- Gene

But **do not ignore other node types** if biologically compelling.

---

## 10. Step 5 — Knowledge Graph Exploration (Neo4j / Cypher)

### 10.1 Objective

Use the Knowledge Graph tools to:

- Connect significant genes to significant network nodes
- Validate network propagation results
- Reveal mechanistic relationships

---

### 10.2 Available Tools

| Tool | Use Case |
|------|----------|
| `get_knowledge_graph_schema` | First step - understand available node types and relationships |
| `query_knowledge_graph` | Custom Cypher queries for complex exploration |
| `search_nodes` | Find nodes by name (genes, diseases, pathways) |
| `get_node_neighbors` | Explore connections from a specific node |
| `get_path_between_nodes` | Find how two entities are connected |
| `get_gene_pathways` | Get pathways for a list of genes |
| `get_gene_disease_associations` | Get disease associations for genes |

---

### 10.3 Query Construction Rules

- Use `node_id` or equivalent identifiers from `tkoi_summary_significant.xlsx`
- Use Ensembl gene IDs from `dge_data_significant.csv`
- Explicitly explore:
  - Gene → Pathway
  - Gene → Disease
  - Gene → CellType
  - Higher-order biological patterns

---

### 10.4 Example Workflow

```python
# 1. Get schema first
get_knowledge_graph_schema(include_properties=True, response_format="markdown")

# 2. Get pathways for significant genes
get_gene_pathways(
    gene_ids=["ENSG00000141510", "ENSG00000171862", "ENSG00000134057"],
    include_shared=True,
    response_format="markdown"
)

# 3. Get disease associations
get_gene_disease_associations(
    gene_ids=["ENSG00000141510", "ENSG00000171862"],
    response_format="markdown"
)

# 4. Custom query for specific patterns
query_knowledge_graph(
    query="""
    MATCH (g:Gene)-[:PARTICIPATES_GpPW]->(p:Pathway)
    WHERE g.identifier IN ['ENSG00000141510', 'ENSG00000171862']
    RETURN g.name, p.name, p.source
    ORDER BY p.name
    """,
    response_format="markdown"
)
```

---

### 10.5 Iterative Exploration

- Write multiple queries as needed
- Follow interesting biological leads
- Look for **supporting, contradicting, or novel insights**

---

## 11. Step 6 — Final Summary Artifact (REQUIRED)

Produce a **final narrative artifact** that includes:

### 1. Study Context
- Experimental design
- Tissue, condition, comparison

### 2. Analysis Statistics
- Total genes analyzed
- Number of FDR-significant genes
- Number of significant network nodes
- Breakdown by node type

### 3. Biological Interpretation
- Key differentially expressed genes
- Key pathways / processes / diseases
- Integration of gene-level and network-level signals
- Biological story supported by the data

### 4. Knowledge Graph Validation
- Connections discovered between genes and biological entities
- Novel or unexpected findings
- Confidence in conclusions

---

## 12. Visualization Rules

- **Do NOT generate plots by default**
- Only generate figures **if explicitly requested by the user**
- When plotting:
  - Use `ggplot_style_check` to optimize code
  - Prefer **R + ggplot2**
  - Save plots and `.R` scripts in the working directory
  - Follow publication-quality guidelines:
    - `theme_minimal(base_size=14)`
    - `scale_color_brewer(palette="Set2")`
    - `ggsave(width=5, height=4, dpi=800)`

---

## 13. Error Handling

### R Execution Errors
- If `run_R_script` fails, examine stderr output
- Check for missing packages, syntax errors, or data issues
- Use `inspect_R_objects` to examine workspace state

### Knowledge Graph Errors
- If queries fail, check Cypher syntax
- Verify node identifiers exist using `search_nodes`
- Use `get_knowledge_graph_schema` to confirm available labels

### Timeout Issues
- tkoi analysis requires `timeout_sec=3600` (1 hour)
- For very large datasets, may need even longer timeouts

---

## 14. Environment Variables

The following environment variables must be configured:

```bash
# Knowledge Graph (Neo4j)
KNOWLEDGE_GRAPH_URI=bolt://spokedev.cgl.ucsf.edu:7687
KNOWLEDGE_GRAPH_USERNAME=neo4j
KNOWLEDGE_GRAPH_PASSWORD=<your_password>
KNOWLEDGE_GRAPH_DATABASE=spoke

# Optional
TKOIAGENT_LOG_LEVEL=INFO
TKOIAGENT_NAMESPACE=tKOIAgent
```

---

## 15. Core Philosophy of tKOIAgent

`tKOIAgent` exists to:

> **Transform transcriptomics data into biologically meaningful, knowledge graph–aware insight using structured computation + AI reasoning.**

It is **not** a black-box enrichment tool.  
It is a **context-aware, hypothesis-sensitive, graph-integrated analysis system**.

The LLM should:
1. Understand the biological question
2. Clean and standardize data appropriately
3. Run network analysis with appropriate parameters
4. Validate findings against the knowledge graph
5. Synthesize results into actionable biological insight

---

## 16. Quick Reference: Tool Sequence

```
1. set_workdir → Set working directory to user's data folder
2. create_R_file → Create clean_data.R
3. write_R_code → Write data cleaning code
4. run_R_script → Execute cleaning
5. create_R_file → Create run_tkoi.R  
6. write_R_code → Write tkoi analysis code
7. run_R_script → Execute tkoi (timeout_sec=3600)
8. list_exports → Verify output files exist
9. preview_table → Examine results
10. get_knowledge_graph_schema → Understand KG structure
11. get_gene_pathways → Query pathways
12. get_gene_disease_associations → Query diseases
13. query_knowledge_graph → Custom exploration
14. Synthesize final report
```

---

## 17. Critical Rules Summary

| Rule | Details |
|------|---------|
| Library name | `tkoi` (all lowercase) |
| Column names | Exactly: `gene_name`, `logfc`, `pvalue`, `fdr` |
| tkoi parameters | Use EXACT parameters shown, especially `n_permutation = 30` |
| R object name | `tkoi_result` (exact name) |
| RDA filename | `tkoi_result.rda` (exact name) |
| Excel export | Use `writexl::write_xlsx()`, NOT openxlsx |
| Excel format | Multi-tab Excel files, NOT separate CSVs |
| tkoi functions | ONLY use `run_tkoi()` — no other tkoi functions |
| Initial files | Only create `clean_data.R` and `run_tkoi.R` |
| Output files | Exactly 5 data files + 2 R scripts |

---

**End of SKILL.md**

