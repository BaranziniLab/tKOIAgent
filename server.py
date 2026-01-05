#!/usr/bin/env python3
"""
tKOIAgent MCP Server

A Model Context Protocol server for automated transcriptomics analysis
using the tKOI (Transcriptomics Knowledge graph-driven Omics Integration)
R package and SPOKE biomedical knowledge graph.
"""

from mcp.server.fastmcp import FastMCP
from pathlib import Path
from typing import Optional, List

# Import tool functions
from tools.environment import (
    check_r_installation,
    check_tkoi_installation,
    install_tkoi_package,
    check_homebrew
)
from tools.data_processing import (
    validate_data_file,
    clean_data_file,
    convert_gene_ids
)
from tools.analysis import run_tkoi_analysis, extract_top_nodes
from tools.visualization import generate_plots
from tools.knowledge_graph import (
    query_spoke_genes,
    extract_spoke_subnetwork,
    get_gene_disease_associations,
    traverse_interesting_nodes
)
from tools.reporting import generate_analysis_report

# Setup logging (CRITICAL: stderr only for STDIO compliance)
from utils.logger import setup_logging
setup_logging()

# Create FastMCP server
mcp = FastMCP(
    "tKOIAgent",
    dependencies=["pandas", "openpyxl", "mygene", "neo4j"]
)


# ========== Environment Tools (3) ==========

@mcp.tool()
def tkoi_check_r_installation() -> dict:
    """
    Check if R is installed and available.

    Returns dictionary with R installation status, version, and path.
    """
    return check_r_installation()


@mcp.tool()
def tkoi_check_tkoi_installation() -> dict:
    """
    Check if tKOI R package is installed.

    Returns dictionary with tKOI installation status and version.
    """
    return check_tkoi_installation()


@mcp.tool()
def tkoi_install_tkoi_package(github_repo: str = "default/tkoi") -> dict:
    """
    Install tKOI R package from GitHub.

    Args:
        github_repo: GitHub repository path (user/repo)

    Returns dictionary with installation status and version.
    """
    return install_tkoi_package(github_repo)


@mcp.tool()
def tkoi_check_homebrew() -> dict:
    """
    Check if Homebrew is installed (macOS/Linux).

    Returns dictionary with Homebrew installation status and version.
    """
    return check_homebrew()


# ========== Data Processing Tools (3) ==========

@mcp.tool()
def tkoi_validate_data_file(
    file_path: str,
    sheet_name: Optional[str] = None
) -> dict:
    """
    Validate gene expression data file.

    Supported path formats:
    - Absolute path: /path/to/file.csv
    - Home-relative: ~/Desktop/ms_analysis/data.csv

    The tool will:
    1. Resolve the path to find the file
    2. Use the file's parent directory as working directory
    3. Validate the data structure
    4. All subsequent analysis outputs will be saved in the same directory

    Args:
        file_path: Path to data file (absolute or home-relative format)
        sheet_name: Sheet name for Excel files (optional)

    Returns: Validation report with 'working_dir' showing where outputs will be saved.
    If valid=false, STOP workflow and ask user for help.
    """
    return validate_data_file(file_path, sheet_name)


@mcp.tool()
def tkoi_clean_data_file(
    input_path: str,
    output_path: str,
    remove_duplicates: bool = True,
    remove_zero_variance: bool = True,
    missing_threshold: float = 0.5,
    sheet_name: Optional[str] = None
) -> dict:
    """
    Clean gene expression data.

    Supported path formats:
    - Absolute path: /path/to/file.csv
    - Home-relative: ~/Desktop/ms_analysis/data.csv

    The tool resolves the path and saves cleaned data to the same directory as input.

    Args:
        input_path: Path to input file (absolute or home-relative format)
        output_path: Output filename (will be saved in same directory as input)
        remove_duplicates: Remove duplicate gene IDs (default: True)
        remove_zero_variance: Remove genes with zero variance (default: True)
        missing_threshold: Maximum proportion of missing values 0-1 (default: 0.5)
        sheet_name: Excel sheet name (optional)

    Returns: Cleaning report with statistics and output file location.
    """
    return clean_data_file(
        input_path,
        output_path,
        remove_duplicates,
        remove_zero_variance,
        missing_threshold,
        sheet_name
    )


@mcp.tool()
def tkoi_convert_gene_ids(
    input_path: str,
    output_path: str,
    source_format: Optional[str] = None,
    include_mouse_orthologs: bool = True,
    sheet_name: Optional[str] = None
) -> dict:
    """
    Convert gene IDs to human Ensembl format.

    Supported path formats:
    - Absolute path: /path/to/file.csv
    - Home-relative: ~/Desktop/ms_analysis/data.csv

    IMPORTANT: Tool first checks if gene IDs are already in Ensembl format.
    If >80% are already Ensembl IDs, conversion is skipped and original file is used.

    Args:
        input_path: Path to input file (absolute or home-relative format)
        output_path: Output filename (will be saved in same directory as input)
        source_format: Source ID format - auto-detect if None
            Options: 'ensembl.gene', 'entrezgene', 'hgnc', 'symbol'
        include_mouse_orthologs: Convert mouse genes to human orthologs (default: True)
        sheet_name: Excel sheet name (optional)

    Returns: Conversion report with statistics. If skipped=True, IDs were already correct.
    """
    return convert_gene_ids(
        input_path,
        output_path,
        source_format,
        include_mouse_orthologs,
        sheet_name
    )


# ========== Analysis Tool (1) ==========

@mcp.tool()
def tkoi_run_analysis(
    data_file: str,
    output_dir: str,
    alpha: Optional[float] = None,
    max_iterations: Optional[int] = None,
    convergence_threshold: Optional[float] = None,
    edge_weight_method: Optional[str] = None,
    normalize: Optional[bool] = None,
    remove_isolated: Optional[bool] = None,
    min_network_size: Optional[int] = None,
    seed: Optional[int] = None
) -> dict:
    """
    Run tKOI network propagation analysis.

    IMPORTANT: This analysis may take 5-30 minutes to complete depending on dataset size
    and parameter settings (especially n_permutation). Do not timeout - this is expected
    behavior for large-scale network propagation analysis with permutation testing.

    Supported path formats for data_file:
    - Absolute path: /path/to/file.csv
    - Home-relative: ~/Desktop/ms_analysis/data.csv

    The tool resolves the path and runs all analysis in the file's directory.
    All outputs (RDA, CSV, plots) will be saved in the same directory as the input file.

    Args:
        data_file: Path to gene expression data (absolute or home-relative format)
        output_dir: (Optional) Ignored - output always goes to file's directory
        alpha: Restart probability 0-1 (default: 0.85)
        max_iterations: Maximum propagation iterations (default: 500)
        convergence_threshold: Convergence threshold (default: 1e-6)
        edge_weight_method: Edge weighting method (default: 'jaccard')
        normalize: Normalize expression values (default: True)
        remove_isolated: Remove isolated nodes (default: True)
        min_network_size: Minimum network size (default: 10)
        seed: Random seed for reproducibility (default: 42)

    Returns: Analysis results with output file paths in 'working_dir'.
    """
    return run_tkoi_analysis(
        data_file,
        output_dir,
        alpha,
        max_iterations,
        convergence_threshold,
        edge_weight_method,
        normalize,
        remove_isolated,
        min_network_size,
        seed
    )


# ========== Analysis Result Extraction (1) ==========

@mcp.tool()
def tkoi_extract_top_nodes(
    working_dir: str,
    top_n: int = 10
) -> dict:
    """
    Extract top N nodes from each modality in tKOI results.

    This tool should be called after tKOI analysis completes to extract
    the most significant findings from each modality (Pathway, Disease, etc.).

    The extracted nodes can then be presented to Claude for interpretation
    to identify the most biologically interesting or unexpected findings.

    Args:
        working_dir: Directory containing tKOI analysis results
        top_n: Number of top nodes to extract per modality (default: 10)

    Returns: Dictionary with top nodes by modality and formatted context for interpretation.
    The 'formatted_context' field contains a markdown summary ready for LLM review.
    """
    return extract_top_nodes(working_dir, top_n)


# ========== Visualization Tool (1) ==========

@mcp.tool()
def tkoi_generate_plots(
    analysis_results_file: str,
    output_dir: str,
    plot_types: Optional[List[str]] = None,
    dpi: Optional[int] = None,
    width: Optional[float] = None,
    height: Optional[float] = None
) -> dict:
    """
    Generate publication-quality ggplot2 visualizations.

    Args:
        analysis_results_file: Path to tKOI analysis results (RDA file)
        output_dir: Directory for output plots
        plot_types: List of plot types - ['volcano', 'score_distribution', 'top_genes']
            Default: all types
        dpi: Plot resolution (default: 800)
        width: Plot width in inches (default: 10)
        height: Plot height in inches (default: 8)

    Returns dictionary with generated plot file paths.
    """
    return generate_plots(
        analysis_results_file,
        output_dir,
        plot_types,
        dpi,
        width,
        height
    )


# ========== Knowledge Graph Tools (2) ==========

@mcp.tool()
def tkoi_query_spoke_genes(
    gene_ids: List[str],
    relationship_types: Optional[List[str]] = None,
    max_depth: int = 1
) -> dict:
    """
    Query SPOKE knowledge graph for gene information.

    Args:
        gene_ids: List of human Ensembl gene IDs
        relationship_types: Filter by relationship types (optional)
        max_depth: Maximum traversal depth 1-3 (default: 1)

    Returns dictionary with query results and statistics.
    """
    return query_spoke_genes(gene_ids, relationship_types, max_depth)


@mcp.tool()
def tkoi_extract_spoke_subnetwork(
    gene_ids: List[str],
    output_file: str,
    node_types: Optional[List[str]] = None,
    edge_types: Optional[List[str]] = None
) -> dict:
    """
    Extract and save subnetwork around specified genes.

    Args:
        gene_ids: List of central gene IDs (Ensembl)
        output_file: Output file path (JSON format)
        node_types: Filter connected nodes by type (optional)
        edge_types: Filter edges by type (optional)

    Returns subnetwork statistics and file path.
    """
    return extract_spoke_subnetwork(gene_ids, output_file, node_types, edge_types)


@mcp.tool()
def tkoi_get_gene_disease_associations(
    gene_ids: List[str],
    output_file: Optional[str] = None
) -> dict:
    """
    Query gene-disease associations from SPOKE.

    Args:
        gene_ids: List of gene IDs (Ensembl)
        output_file: Optional output file path (CSV)

    Returns gene-disease associations.
    """
    return get_gene_disease_associations(gene_ids, output_file)


@mcp.tool()
def tkoi_traverse_interesting_nodes(
    interesting_nodes: List[dict],
    significant_genes_file: str,
    max_hops: int = 2
) -> dict:
    """
    Perform network traversal to understand why nodes are ranked highly.

    After Claude identifies interesting nodes from top results, use this tool
    to explore the SPOKE knowledge graph and find which significant genes
    connect to these nodes and through what biological relationships.

    This provides biological context explaining why certain pathways, diseases,
    or other entities are highly ranked in the tKOI analysis.

    Args:
        interesting_nodes: List of interesting nodes identified by Claude
            Format: [{'modality': 'Pathway', 'name': 'Node Name', 'reason': '...'}, ...]
        significant_genes_file: Path to CSV file with FDR-significant genes
            (generated by tkoi_clean_data_file as *_significant.csv)
        max_hops: Maximum network hops for traversal 1-3 (default: 2)

    Returns: Traversal results with connecting genes, paths, and biological context
    for each interesting node.
    """
    return traverse_interesting_nodes(interesting_nodes, significant_genes_file, max_hops)


# ========== Reporting Tool (1) ==========

@mcp.tool()
def tkoi_generate_analysis_report(
    working_dir: str,
    analysis_params: Optional[dict] = None,
    top_nodes: Optional[dict] = None,
    interesting_nodes: Optional[List[dict]] = None,
    traversal_results: Optional[dict] = None
) -> dict:
    """
    Prepare comprehensive context for LLM-based analysis report generation.

    This tool DOES NOT generate a rigid templated report. Instead, it provides
    Claude with rich context to write a natural, biologically-informed report.

    The tool provides:
    1. Top 10 FDR-significant genes from the analysis
    2. Top nodes from each modality (if provided)
    3. Interesting nodes identified by Claude (if provided)
    4. Network traversal results explaining biological connections (if provided)
    5. Analysis parameters and file locations

    Claude should then use this context to write a comprehensive markdown report
    that includes:
    - Executive summary with biological interpretation
    - Methods section describing the analysis
    - Results with contextualized findings
    - Key biological insights and implications
    - References to output files and visualizations

    Args:
        working_dir: Directory containing analysis results
        analysis_params: Analysis parameters used (optional)
        top_nodes: Top nodes from tkoi_extract_top_nodes (optional)
        interesting_nodes: Interesting nodes identified by Claude (optional)
        traversal_results: Results from tkoi_traverse_interesting_nodes (optional)

    Returns: Context dictionary for Claude to generate a natural language report.
    Claude should write the final report as README.md in the working directory.
    """
    return generate_analysis_report(
        working_dir,
        analysis_params,
        top_nodes,
        interesting_nodes,
        traversal_results
    )


def main():
    """Main entry point for the MCP server."""
    mcp.run()


# Run server
if __name__ == "__main__":
    main()
