# tKOIAgent - MCP Server for Transcriptomics Analysis

A Model Context Protocol (MCP) server that automates transcriptomics analysis using the tKOI (Transcriptomics Knowledge graph-driven Omics Integration) R package and SPOKE biomedical knowledge graph integration.

## Overview

tKOIAgent provides 13 specialized tools for:
- Environment setup and validation
- Multi-format gene ID conversion
- tKOI network propagation analysis
- **Intelligent result interpretation with LLM**
- **Network traversal for biological context**
- Publication-quality visualizations
- SPOKE knowledge graph queries
- **LLM-powered report generation**

## Features

### Environment Management
- ✅ Check R and tKOI installation status
- ✅ Install tKOI package from GitHub
- ✅ Verify Homebrew availability

### Data Processing
- ✅ Validate gene expression files (Excel, CSV, TSV, TXT)
- ✅ Clean data (remove duplicates, zero-variance genes)
- ✅ Convert gene IDs (Ensembl, Entrez, HGNC, Symbol) to human Ensembl
- ✅ Mouse-to-human ortholog mapping

### Analysis & Visualization
- ✅ tKOI network propagation with 8 configurable parameters
- ✅ Extract top FDR-significant genes automatically
- ✅ Extract top 10 nodes from each modality (Pathway, Disease, etc.)
- ✅ Publication-quality plots at 800 dpi using tKOI's visualize_topn()
- ✅ ggplot2 visualizations following style guide

### Intelligent Interpretation
- ✅ **NEW**: Present top nodes to Claude for biological interpretation
- ✅ **NEW**: Identify interesting/unexpected findings automatically
- ✅ **NEW**: Network traversal (2-hop) to explain node rankings
- ✅ **NEW**: Connect significant genes to biological entities

### Knowledge Graph Integration
- ✅ Query SPOKE for gene relationships
- ✅ Extract subnetworks around genes
- ✅ Gene-disease association queries
- ✅ Network traversal for biological context
- ✅ Read-only Neo4j access with connection pooling

### Reporting
- ✅ **NEW**: LLM-powered report generation (not rigid templates)
- ✅ **NEW**: Natural language biological interpretation
- ✅ **NEW**: Context-aware insights from network traversal
- ✅ Markdown format with methods, results, and citations

## Installation

### Prerequisites

- **Python 3.10+**
- **R 4.0+**
- **Claude Desktop**
- **uv** (recommended) or pip

### Quick Install with uv (Recommended)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to project
cd /Users/wgu/Desktop/tKOIAgent

# Install dependencies (auto-creates venv)
uv sync

# Install R packages
Rscript -e 'install.packages(c("jsonlite", "devtools", "ggplot2", "tidyverse"))'
```

### Alternative: Install with pip

1. **Navigate to project directory**
   ```bash
   cd /Users/wgu/Desktop/tKOIAgent
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # OR
   venv\Scripts\activate  # On Windows
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install R packages**
   ```r
   # In R console
   install.packages(c("jsonlite", "devtools", "ggplot2", "reshape2", "tidyverse"))

   # Install tKOI (update with actual repository)
   devtools::install_github("user/tkoi")
   ```

5. **Configure Claude Desktop**

   Edit Claude Desktop config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

   **For uv installation:**
   ```json
   {
     "mcpServers": {
       "tKOIAgent": {
         "command": "uv",
         "args": [
           "--directory",
           "/Users/wgu/Desktop/tKOIAgent",
           "run",
           "tKOIAgent"
         ]
       }
     }
   }
   ```

   **Note**: When using the .mcpb bundle, configuration parameters can be customized through Claude Desktop's Settings → Extensions UI.

   **For pip installation:**
   ```json
   {
     "mcpServers": {
       "tKOIAgent": {
         "command": "python3",
         "args": [
           "/Users/wgu/Desktop/tKOIAgent/server.py"
         ],
         "env": {
           "PYTHONPATH": "/Users/wgu/Desktop/tKOIAgent"
         }
       }
     }
   }
   ```

6. **Restart Claude Desktop**

   Completely quit and restart Claude Desktop to load the MCP server.

## Configuration

tKOIAgent supports user-configurable parameters through environment variables:

### Option 1: Using .mcpb Bundle (Recommended)
When installed as a Claude Desktop extension from the .mcpb bundle, configuration parameters are managed through the **Claude Desktop UI**:
1. Open Claude Desktop
2. Go to Settings → Extensions → tKOIAgent
3. Configure parameters through the interactive UI forms
4. Changes are applied automatically

All configuration parameters appear as editable form fields with descriptions, defaults, and valid ranges.

### Option 2: Using Manual Installation
For manual installations, add environment variables to the `"env"` section in your Claude Desktop config file.

### Available Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TKOI_DEFAULT_WORKDIR` | `~/Desktop` | Default working directory for outputs |
| `TKOI_LOGFC_THRESHOLD` | `0.25` | Minimum log fold-change threshold for differential expression |
| `TKOI_INDIRECT_LINK_THRESHOLD` | `3` | Required indirect connectivity for downstream gene inclusion |
| `TKOI_TOPOLOGY_SIMILARITY` | `0.9` | Similarity for selecting matched genes in permutations (0.0-1.0) |
| `TKOI_N_PERMUTATION` | `30` | Number of permutations for statistical testing |
| `TKOI_DAMPING_FACTOR` | `0.85` | Network propagation damping factor (0.7-0.95) |
| `TKOI_MAXIMUM_ITERATION` | `500` | Maximum iterations for propagation convergence |

**Example manual configuration** (add to `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "tKOIAgent": {
      "command": "uv",
      "args": ["--directory", "/path/to/tKOIAgent", "run", "tKOIAgent"],
      "env": {
        "TKOI_DEFAULT_WORKDIR": "~/Desktop",
        "TKOI_LOGFC_THRESHOLD": "1.5",
        "TKOI_DAMPING_FACTOR": "0.9"
      }
    }
  }
}
```

## Quick Start

Once installed, you can interact with tKOIAgent through Claude Desktop:

### Basic Workflow
```
Please run a complete tKOI analysis on my data file at ~/Desktop/my_data.csv
```

Claude will automatically:
1. Validate the data file
2. Clean the data and extract FDR-significant genes
3. Run tKOI network propagation analysis
4. Generate publication-quality plots
5. **Extract and interpret top nodes** (NEW)
6. **Perform network traversal** for interesting findings (NEW)
7. **Generate an LLM-powered report** with biological insights (NEW)

### Intelligent Analysis Workflow (NEW)

After basic analysis, you can leverage the intelligent interpretation:

#### 1. Extract Top Nodes
```
Extract the top 10 nodes from the tKOI analysis results in ~/Desktop/my_data/
```

Claude will extract the most significant nodes from each modality (Pathway, Disease, CellType, etc.).

#### 2. Interpret Results
```
Review these top nodes and identify the most interesting or unexpected findings
```

Claude will analyze the biological context and highlight surprising results.

#### 3. Network Traversal
```
For the interesting nodes you identified, perform network traversal using the significant genes
```

Claude will explore SPOKE to find which genes connect to interesting nodes and explain why.

#### 4. Generate Contextualized Report
```
Generate a comprehensive report with biological interpretation
```

Claude will write a natural language report with context-aware biological insights.

### Step-by-Step Examples

#### 1. Check Environment
```
Check if R and tKOI are installed on my system
```

#### 2. Validate Data
```
Validate my gene expression file at /path/to/data.xlsx
```

#### 3. Run Complete Analysis
```
Run tKOI analysis on /path/to/converted_data.csv
```

## Available Tools

### Environment Tools

1. **tkoi_check_r_installation**
   - Check R installation status and version

2. **tkoi_check_tkoi_installation**
   - Verify tKOI package availability

3. **tkoi_install_tkoi_package**
   - Install tKOI from GitHub repository

4. **tkoi_check_homebrew**
   - Check Homebrew installation (macOS/Linux)

### Data Processing Tools

5. **tkoi_validate_data_file**
   - Validate gene expression file structure
   - Supports: Excel (.xlsx, .xls), CSV, TSV, TXT

6. **tkoi_clean_data_file**
   - Remove duplicates and zero-variance genes
   - Filter by missing value threshold
   - **NEW**: Automatically saves FDR-significant genes to separate CSV

7. **tkoi_convert_gene_ids**
   - Convert multiple gene ID formats to human Ensembl
   - Auto-detect source format
   - Mouse ortholog mapping support

### Analysis Tools

8. **tkoi_run_analysis**
   - Execute tKOI network propagation
   - 8 configurable parameters (alpha, iterations, thresholds, etc.)
   - Outputs: RDA, CSV files with scores and networks

9. **tkoi_extract_top_nodes** ✨ NEW
   - Extract top 10 nodes from each modality after analysis
   - Returns formatted context for LLM interpretation
   - Identifies most significant findings across Pathway, Disease, CellType, etc.

### Visualization Tool

10. **tkoi_generate_plots**
    - Generate publication-quality plots (800 dpi)
    - Uses tKOI's official visualize_topn() function
    - Top 20 results for 9 modalities
    - Follows ggplot style guide

### Knowledge Graph Tools

11. **tkoi_query_spoke_genes**
    - Query SPOKE for gene relationships
    - Filter by relationship types
    - Configurable traversal depth

12. **tkoi_extract_spoke_subnetwork**
    - Extract subnetwork around genes
    - Save as JSON with nodes and edges
    - Filter by node and edge types

13. **tkoi_traverse_interesting_nodes** ✨ NEW
    - Perform 2-hop network traversal for interesting nodes
    - Find genes connecting to biological entities
    - Explain why nodes are highly ranked
    - Provides biological context for top findings

14. **tkoi_get_gene_disease_associations**
    - Query gene-disease associations
    - Export to CSV

### Reporting Tool

15. **tkoi_generate_analysis_report** ✨ ENHANCED
    - **NEW**: LLM-powered report generation (not rigid templates)
    - Provides context for Claude to write natural language reports
    - Includes top genes, interesting nodes, and network traversal results
    - Claude generates biological interpretation and key insights

## Configuration

### Default Parameters

Configuration is managed in `config.py`:

- **SPOKE credentials**: Hardcoded for public SPOKE dev instance
- **tKOI parameters**: alpha=0.85, max_iterations=500, n_permutation=30
- **Output settings**: dpi=800, plot dimensions
- **Gene conversion**: Target format = human Ensembl

### SPOKE Connection

The server connects to:
- **URI**: `bolt://spokedev.cgl.ucsf.edu:7687`
- **Database**: spoke
- **Access**: Read-only with connection pooling

## Architecture

```
tKOIAgent/
├── server.py                 # FastMCP server entry point
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
│
├── utils/                    # Shared utilities
│   ├── logger.py            # STDIO-compliant logging
│   ├── r_executor.py        # R subprocess manager
│   ├── gene_converter.py    # MyGene API client
│   ├── neo4j_client.py      # SPOKE client
│   └── file_handler.py      # File I/O
│
├── tools/                    # MCP tool implementations
│   ├── environment.py       # Environment tools
│   ├── data_processing.py   # Data tools
│   ├── analysis.py          # Analysis tool
│   ├── visualization.py     # Visualization tool
│   ├── knowledge_graph.py   # SPOKE tools
│   └── reporting.py         # Report tool
│
└── scripts/                 # R script templates
    ├── check_tkoi.R
    ├── install_tkoi.R
    ├── run_analysis.R
    └── generate_plots.R
```

## Technical Details

### MCP Protocol Compliance

- **Transport**: STDIO (standard for Claude Desktop)
- **Protocol**: JSON-RPC 2.0
- **Logging**: All logs to stderr (stdout reserved for JSON-RPC)

### R Integration

- Uses subprocess execution (not rpy2) for process isolation
- JSON communication via temporary files
- Comprehensive error capture and reporting

### Gene ID Conversion

- Uses MyGene.info API
- Auto-detects input format
- Supports: Ensembl, Entrez, HGNC, Symbol
- Mouse-to-human ortholog mapping

### Neo4j Integration

- Connection pooling for efficiency
- Read-only query enforcement
- Query validation (rejects mutations)

## Troubleshooting

### R Not Found
```
Error: R executable not found
Solution: Install R from https://cran.r-project.org/
macOS: brew install r
```

### tKOI Package Missing
```
Error: tkoi package is not installed
Solution: Use tkoi_install_tkoi_package tool or install manually:
devtools::install_github("user/tkoi")
```

### SPOKE Connection Failed
```
Error: Failed to connect to SPOKE
Solution: Check network connectivity. SPOKE dev instance may be down.
The analysis can continue without SPOKE integration.
```

### File Format Not Supported
```
Error: Unsupported file format
Solution: Convert to Excel (.xlsx), CSV, TSV, or TXT format
```

### Gene ID Conversion Low Success Rate
```
Warning: <50% genes successfully mapped
Solution:
1. Check that gene IDs are correctly formatted
2. Try specifying source_format explicitly
3. Verify species (human vs mouse)
```

## Testing

### Test STDIO Compliance
```bash
cd /Users/wgu/Desktop/tKOIAgent
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python3 server.py 2>/dev/null | jq .
```

Should output JSON-RPC response without any log messages.

### Test Tool Availability
In Claude Desktop:
```
List all available tKOI tools
```

Should show all 11 tools with descriptions.

## Contributing

This is a specialized MCP server for transcriptomics analysis. To extend:

1. Add new tools in `tools/` directory
2. Register tools in `server.py` using `@mcp.tool()` decorator
3. Follow STDIO compliance (stderr-only logging)
4. Update documentation

## License

[Specify license]

## Citations

### SPOKE
> Scalable Precision Medicine Open Knowledge Engine (SPOKE): A massive knowledge graph of biomedical information. *Bioinformatics* (2023). doi: 10.1093/bioinformatics/btad080

### tKOI
> tKOI: Transcriptomics Knowledge graph-driven Omics Integration
> [Citation to be provided]

## Support

For issues or questions:
- GitHub Issues: [repository URL]
- Documentation: This README

---

**Generated by tKOIAgent v1.0.0**
