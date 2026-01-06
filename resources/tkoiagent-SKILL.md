# SKILL.md  
## tKOIAgent — Transcriptomics Knowledge Graph–Driven Omics Integration Agent

---

## 1. Purpose of This Skill

`tKOIAgent` is a **specialized multi-tool analysis agent** designed to:

1. Analyze **transcriptomics / gene expression data**
2. Convert differential expression results into **knowledge graph–based embeddings**
3. Perform **network propagation and enrichment analysis** using **tKOI**
4. Contextualize results using **AI-driven biological reasoning**
5. Validate and explore findings using a **Neo4j / Cypher biological knowledge graph**

This skill document **must be read and followed whenever the LLM invokes or decides to invoke `tKOIAgent`**.

---

## 2. High-Level Conceptual Model

`tKOIAgent` operates via **two coordinated toolchains**:

### Toolchain A — Local Computation & R Execution
Used for:
- Reading/writing local files
- Cleaning transcriptomics data
- Running R scripts
- Executing `tkoi` pathway/network analysis
- Exporting structured results (CSV, Excel, RDA)

### Toolchain B — Knowledge Graph Querying (Neo4j / Cypher)
Used for:
- Querying biological relationships
- Connecting differentially expressed genes to:
  - Pathways
  - Diseases
  - Cell types
  - Anatomical structures
  - Molecular functions
- Validating and contextualizing tKOI results

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
| Log fold change | Differential expression magnitude | `logFC`, `log_fc`, `logFoldChange`, variants |
| P-values | Statistical significance | `pvalue`, `p_value`, `P.Value`, variants |

> ✅ Column names may vary  
> ❌ Missing any component → STOP and ask user to re-upload or clarify

---

### 3.2 Study Context Requirement (CRITICAL)

The user **must provide study context**, including at least:

- Study type (e.g. disease vs control, perturbation, time series)
- Tissue or cell type
- Condition being compared
- Comparison groups
- Any relevant experimental or biological background

❗ **If no study context is provided:**
- STOP execution
- Prompt the user for clarification
- DO NOT proceed with analysis

---

## 4. Working Directory Rules

Once inputs are validated:

1. Extract the directory containing the user’s data file  
2. Set this directory as the **working directory**

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

In the working directory, generate an R script named:

```
clean_data.R
```

---

### 5.2 Responsibilities of `clean_data.R`

The script must:

1. Load the input file into R
2. Identify gene ID format
3. Convert gene identifiers to **Ensembl IDs** if needed
   - HGNC → Ensembl
   - Mouse → Human homolog (when appropriate)
4. Normalize column names
5. Subset and standardize the dataset

---

### 5.3 Final Required Data Structure

The cleaned `data.frame` **must contain exactly**:

| Column Name | Description |
|------------|------------|
| `gene_name` | Ensembl gene ID |
| `logfc` | Log fold change |
| `pvalue` | Raw p-value |
| `fdr` | FDR-adjusted p-value |

- Compute FDR using standard multiple testing correction
- Ensure numeric integrity

---

### 5.4 Required Output Files

Export:

1. **Full dataset**
```
dge_data.csv
```

2. **Significant genes only (FDR ≤ 0.05)**
```
dge_data_significant.csv
```

---

## 6. Step 2 — Running tKOI Analysis

### 6.1 Create `run_tkoi.R`

Generate a second R script:

```
run_tkoi.R
```

---

### 6.2 Package Installation Logic

At the start of the script:

```r
if (!requireNamespace("tkoi", quietly = TRUE)) {
  install.packages("devtools")
  devtools::install_github("Broccolito/tkoi")
}
```

Then load required libraries.

---

### 6.3 Load Expression Data

```r
expression_data <- fread(file_path)
head(expression_data)
```

---

### 6.4 Compute FDR Threshold

Before running `run_tkoi()`:

- Determine the **highest raw p-value** that corresponds to `fdr <= 0.05`
- Pass this as `pvalue_threshold`

---

### 6.5 Run tKOI (DEFAULT PARAMETERS)

```r
tkoi_result <- run_tkoi(
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

⚠️ **Do not change parameters unless explicitly requested by the user.**

---

### 6.6 Runtime Expectations

- Execution may take **30–60 minutes**
- The LLM **must remain patient**
- Do not assume failure prematurely

---

## 7. Step 3 — Export tKOI Results

### 7.1 Save Raw Results

- Save entire object:
```
tkoi_result.rda
```

---

### 7.2 Export Network Summary Statistics

`tkoI_result@network_summary_statistics` is a list of data.frames.

Each element represents one modality, e.g.:

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

### 7.3 Full Summary Export

- Save **all data.frames** as tabs in:
```
tkoi_summary.xlsx
```

(Tab names must match list element names exactly.)

---

### 7.4 Significant-Only Summary Export

For each data.frame:
- Filter `fdr <= 0.05`

Save to:
```
tkoi_summary_significant.xlsx
```

---

## 8. Step 4 — Contextual Analysis & Interpretation

Load into context:

- `dge_data_significant.csv`
- `tkoi_summary_significant.xlsx`

### Interpretation Rules

1. `dge_data_significant.csv`
   - Represents **significantly regulated genes**

2. `tkoi_summary_significant.xlsx`
   - Represents **key network nodes after propagation**

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

## 9. Step 5 — Knowledge Graph Exploration (Neo4j / Cypher)

### 9.1 Objective

Use Cypher queries to:

- Connect significant genes to significant network nodes
- Validate network propagation results
- Reveal mechanistic relationships

---

### 9.2 Query Construction Rules

- Use `node_id` or equivalent identifiers from `tkoi_summary_significant.xlsx`
- Use Ensembl gene IDs from `dge_data_significant.csv`
- Explicitly explore:
  - Gene → Pathway
  - Gene → Disease
  - Gene → CellType
  - Higher-order biological patterns

---

### 9.3 Iterative Exploration

- Write multiple Cypher queries as needed
- Follow interesting biological leads
- Look for **supporting, contradicting, or novel insights**

---

## 10. Step 6 — Final Summary Artifact (REQUIRED)

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

---

## 11. Visualization Rules

- **Do NOT generate plots by default**
- Only generate figures **if explicitly requested**
- When plotting:
  - Prefer **R + ggplot2**
  - Save plots and `.R` scripts in the working directory

---

## 12. Core Philosophy of tKOIAgent

`tKOIAgent` exists to:

> **Transform transcriptomics data into biologically meaningful, knowledge-graph–aware insight using structured computation + AI reasoning.**

It is **not** a black-box enrichment tool.  
It is a **context-aware, hypothesis-sensitive, graph-integrated analysis system**.

---

**End of SKILL.md**
