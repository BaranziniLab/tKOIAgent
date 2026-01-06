# tKOIAgent

<div align="center">
  <img src="assets/icon.png" alt="tKOIAgent Logo" width="200"/>

  **Transcriptomics Knowledge Graph-Driven Omics Integration Agent**

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![MCP](https://img.shields.io/badge/MCP-Compatible-blue.svg)](https://modelcontextprotocol.io)
  [![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
  [![R Required](https://img.shields.io/badge/R-Required-276DC3.svg)](https://www.r-project.org/)
</div>


## Overview

**tKOIAgent** is a specialized Model Context Protocol (MCP) server that brings advanced transcriptomics analysis capabilities to Claude Desktop. It seamlessly combines:

- 🧬 **R-based transcriptomics analysis** with the powerful [tKOI](https://github.com/Broccolito/tkoi) network propagation algorithm
- 🕸️ **Neo4j knowledge graph querying** using the [SPOKE](https://spoke.ucsf.edu/) biomedical knowledge graph
- 🤖 **AI-driven biological interpretation** through Claude's natural language understanding

With tKOIAgent, you can transform raw differential gene expression data into actionable biological insights through an intuitive conversational interface.


## Key Features

### 🔬 Transcriptomics Analysis Pipeline
- **Data cleaning and harmonization**: Automatically convert gene identifiers to Ensembl IDs
- **tKOI network propagation**: Identify key biological networks affected by differential expression
- **Statistical rigor**: FDR-adjusted p-values and comprehensive quality control
- **Publication-ready outputs**: Multi-tab Excel reports with complete network summaries

### 🧠 Knowledge Graph Integration
- **SPOKE database access**: Query 27+ million biomedical relationships
- **Multi-modal exploration**: Genes, pathways, diseases, cell types, anatomical structures, and more
- **Cypher query support**: Write custom queries or use pre-built specialized tools
- **Validation and contextualization**: Cross-reference network results with established biological knowledge

### 📊 Comprehensive Toolset
- **17+ specialized tools** for end-to-end transcriptomics workflows
- **R script management**: Create, edit, and execute R code with long-running job support
- **File operations**: List, read, preview CSV/TSV/Excel files
- **Visualization support**: ggplot2 style checking for publication-quality figures


## Installation

### Prerequisites

Before installing tKOIAgent, ensure you have:

1. **Claude Desktop** - [Download here](https://claude.ai/download)
2. **R (version 4.0+)** - [Download here](https://www.r-project.org/)
3. **R packages** (will be auto-installed on first use):
   - `tkoi` (from GitHub: `Broccolito/tkoi`)
   - `data.table`
   - `writexl`

### Quick Install via GitHub Releases

1. **Download the latest release**:
   - Go to the [Releases page](https://github.com/YOUR_USERNAME/tKOIAgent/releases)
   - Download the `tKOIAgent-v1.0.0.mcpb` bundle file

2. **Install in Claude Desktop**:
   - Open Claude Desktop
   - Go to **Settings** → **Developer** → **MCP Servers**
   - Click **Install from Bundle** (or drag and drop the `.mcpb` file)
   - Select the downloaded `tKOIAgent-v1.0.0.mcpb` file
   - Click **Install**

3. **Verify installation**:
   - Restart Claude Desktop
   - Start a new conversation
   - Type: "Can you check if tKOIAgent is available?"
   - Claude should confirm the agent is loaded with all tools available

### Manual Installation

If you prefer to install from source:

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/tKOIAgent.git
cd tKOIAgent

# The bundle includes a pre-configured Python environment
# No additional setup needed!

# Configure Claude Desktop
# Add to your Claude Desktop MCP settings:
{
  "tKOIAgent": {
    "command": "/path/to/tKOIAgent/.python/bin/python3.12",
    "args": ["/path/to/tKOIAgent/server/main.py"],
    "env": {
      "KNOWLEDGE_GRAPH_URI": "bolt://spokedev.cgl.ucsf.edu:7687",
      "KNOWLEDGE_GRAPH_USERNAME": "neo4j",
      "KNOWLEDGE_GRAPH_PASSWORD": "SPOKEdev",
      "KNOWLEDGE_GRAPH_DATABASE": "spoke"
    }
  }
}
```


## Available Tools

tKOIAgent provides 17 specialized tools organized into three categories:

### 📋 Core Setup Tools

| Tool | Description |
|------|-------------|
| `get_instructions` | Load complete operational guidelines (call this first!) |
| `set_workdir` | Set the working directory for all operations |
| `get_state` | Check current state, R availability, and configuration |

### 🧬 R Analysis Toolchain

| Tool | Description |
|------|-------------|
| `create_R_file` | Create new R script files |
| `write_R_code` | Write R code to files (replaces content) |
| `append_R_code` | Append code to existing R scripts |
| `run_R_script` | Execute R scripts (supports 1-hour timeouts for tKOI) |
| `run_R_expression` | Run quick R expressions |
| `list_exports` | List generated files |
| `read_export` | Read file contents |
| `preview_table` | Preview CSV/TSV data |
| `inspect_R_objects` | Inspect R workspace objects |
| `ggplot_style_check` | Optimize ggplot2 code for publication |
| `which_R` | Find R executable path |
| `list_R_files` | List R scripts |
| `set_primary_file` | Set default R script |

### 🕸️ Knowledge Graph Toolchain

| Tool | Description |
|------|-------------|
| `get_knowledge_graph_schema` | Get SPOKE schema (nodes, relationships) |
| `query_knowledge_graph` | Execute custom Cypher queries |
| `search_nodes` | Search nodes by name/identifier |
| `get_node_neighbors` | Get connected nodes |
| `get_path_between_nodes` | Find paths between entities |
| `get_gene_pathways` | Get pathways for gene lists |
| `get_gene_disease_associations` | Get disease associations |


## Example Workflow

Here's a complete example of analyzing differential gene expression data:

### Step 1: Start the Analysis

```
User: I have a differential expression dataset from a cancer vs normal comparison.
The file is at ~/Desktop/cancer_dge.csv with columns: gene_symbol, log2FC, pvalue, padj

Claude: I'll help you analyze this data using tKOIAgent! Let me start by:
1. Loading the operational guidelines
2. Setting up your working directory
3. Examining your data
```

### Step 2: Data Cleaning

Claude will automatically:
- Set the working directory to `~/Desktop`
- Create a `clean_data.R` script
- Convert gene symbols to Ensembl IDs
- Normalize column names to required format (`gene_name`, `logfc`, `pvalue`, `fdr`)
- Export cleaned datasets:
  - `dge_data.csv` (all genes)
  - `dge_data_significant.csv` (FDR ≤ 0.05)

### Step 3: tKOI Network Analysis

Claude will:
- Create `run_tkoi.R` script
- Install tkoi package if needed
- Run network propagation analysis (may take 30-60 minutes)
- Export results:
  - `tkoi_result.rda` (R object)
  - `tkoi_summary.xlsx` (multi-tab Excel with all results)
  - `tkoi_summary_significant.xlsx` (FDR-filtered results)

### Step 4: Knowledge Graph Validation

Claude will query SPOKE to:
- Find pathways associated with significant genes
- Identify disease connections
- Explore cell type and anatomical context
- Validate network propagation findings

### Step 5: Biological Interpretation

Claude will synthesize:
- Key differentially expressed genes
- Enriched pathways and biological processes
- Disease associations
- A coherent biological narrative explaining your results

### Complete Session Example

```
User: Analyze my cancer DEG data at ~/Desktop/cancer_vs_normal.csv

Claude: I'll analyze your cancer differential expression data. Let me start by
loading the tKOIAgent instructions... [calls get_instructions]

Now setting up the working directory... [calls set_workdir]

I can see your dataset has 15,234 genes with log2FC and adjusted p-values.
I'll now:

1. Clean and standardize the data...
   ✓ Created clean_data.R
   ✓ Converted 14,892 gene symbols to Ensembl IDs
   ✓ Exported dge_data.csv (14,892 genes)
   ✓ Exported dge_data_significant.csv (1,247 genes, FDR ≤ 0.05)

2. Running tKOI network propagation analysis...
   ⏳ This will take approximately 45 minutes
   ✓ Analysis complete!
   ✓ Identified 342 significant network nodes across 9 modalities

3. Querying SPOKE knowledge graph...
   ✓ Found 89 enriched pathways
   ✓ Identified associations with 156 diseases
   ✓ Key finding: Strong enrichment in cell cycle and DNA repair pathways

4. Biological Interpretation:

   Your cancer vs normal comparison reveals:

   **Top Differentially Expressed Genes:**
   - TP53, BRCA1, MYC (tumor suppressors/oncogenes)
   - CDK1, CCNB1 (cell cycle regulation)

   **Key Pathways:**
   - Cell cycle progression (p < 0.001)
   - DNA damage response (p < 0.001)
   - p53 signaling pathway (p < 0.005)

   **Disease Associations:**
   - Multiple cancer types (breast, lung, colorectal)
   - Cell proliferation disorders

   **Biological Story:**
   Your data shows classic hallmarks of cancer: dysregulated cell cycle,
   compromised DNA repair, and altered tumor suppressor activity. The tKOI
   network analysis reveals that these changes propagate through interconnected
   pathways, suggesting systemic disruption of growth control mechanisms.

All results are saved in ~/Desktop/ including detailed Excel reports.
```


## Output Files

After a complete analysis, you'll find these files in your working directory:

### R Scripts
- `clean_data.R` - Data cleaning and harmonization script
- `run_tkoi.R` - tKOI network analysis script

### Data Files
- `dge_data.csv` - Full cleaned dataset (4 columns: gene_name, logfc, pvalue, fdr)
- `dge_data_significant.csv` - FDR-significant genes only

### Results
- `tkoi_result.rda` - Complete tKOI R object (for advanced users)
- `tkoi_summary.xlsx` - Multi-tab Excel with all network results
  - Tabs: Anatomy, CellType, Complex, Pathway, Disease, BiologicalProcess, etc.
- `tkoi_summary_significant.xlsx` - FDR-filtered network results


## Important Guidelines

### ⚠️ Critical: tkoi-ONLY Analysis Policy

tKOIAgent **exclusively** uses the `tkoi` R package for pathway/network analysis:

- ✅ **USE**: `tkoi::run_tkoi()` for all network analysis
- ❌ **DO NOT USE**: clusterProfiler, enrichR, fgsea, GSEA, ReactomePA, pathfindR, gprofiler2, or any other pathway tools

This ensures consistent, reproducible network propagation analysis using the validated tKOI methodology.

### Required Data Format

Your input data must contain:
1. **Gene identifiers** (Ensembl IDs, HGNC symbols, or other formats - will be converted)
2. **Log fold change** (any format: logFC, log2FC, etc.)
3. **P-values** (raw p-values for FDR calculation)

### Study Context

Always provide:
- Study type (e.g., disease vs control)
- Tissue or cell type
- Experimental conditions
- Comparison groups

This context is essential for accurate biological interpretation.


## Configuration

### Environment Variables

Configure these in your MCP settings:

```json
{
  "env": {
    "KNOWLEDGE_GRAPH_URI": "bolt://spokedev.cgl.ucsf.edu:7687",
    "KNOWLEDGE_GRAPH_USERNAME": "neo4j",
    "KNOWLEDGE_GRAPH_PASSWORD": "your_password",
    "KNOWLEDGE_GRAPH_DATABASE": "spoke",
    "TKOIAGENT_LOG_LEVEL": "INFO"
  }
}
```

### SPOKE Database Access

The default configuration connects to UCSF's SPOKE development server. For production use or private deployments, update the credentials accordingly.


## Troubleshooting

### Common Issues

**Problem**: "R not found in PATH"
- **Solution**: Install R and ensure `Rscript` is accessible from terminal
- **Test**: Run `which Rscript` in terminal

**Problem**: "tkoi package not found"
- **Solution**: tKOIAgent will auto-install on first use. If it fails, manually install:
  ```r
  devtools::install_github("Broccolito/tkoi")
  ```

**Problem**: "tKOI analysis timeout"
- **Solution**: Default timeout is 1 hour. For very large datasets, the analysis may need more time. Consider filtering to top N genes by p-value.

**Problem**: "Neo4j connection failed"
- **Solution**: Check your network connection and verify SPOKE credentials in MCP settings


## Architecture

tKOIAgent is built on:

- **FastMCP**: Python MCP server framework
- **Neo4j Python Driver**: For SPOKE knowledge graph queries
- **R (via subprocess)**: For statistical analysis and tKOI execution
- **SPOKE**: UCSF's comprehensive biomedical knowledge graph

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/tKOIAgent.git
cd tKOIAgent

# The .python directory contains a complete Python environment
# For development, you may want to create a new virtual environment:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```


## Citation

If you use tKOIAgent in your research, please cite:

```bibtex
@software{tKOIAgent2024,
  author = {Gu, Wanjun},
  title = {tKOIAgent: Transcriptomics Knowledge Graph-Driven Omics Integration Agent},
  year = {2024},
  url = {https://github.com/YOUR_USERNAME/tKOIAgent}
}
```

And please cite the tKOI package:
```bibtex
@article{tkoi2024,
  title={tKOI: Network propagation for transcriptomics knowledge graph integration},
  author={Your tKOI citation here},
  year={2024}
}
```


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Acknowledgments

- **tKOI**: Network propagation algorithm by [Broccolito](https://github.com/Broccolito/tkoi)
- **SPOKE**: Biomedical knowledge graph by UCSF
- **Anthropic**: For Claude Desktop and MCP framework
- **R Community**: For the amazing statistical computing ecosystem


## Contact

**Author**: Wanjun Gu
**Email**: wanjun.gu@ucsf.edu
**GitHub**: [tKOIAgent Repository](https://github.com/YOUR_USERNAME/tKOIAgent)

