"""
Reporting tool for tKOIAgent.

Provides context for LLM-based analysis report generation.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_analysis_report(
    working_dir: str,
    analysis_params: Optional[Dict[str, Any]] = None,
    top_nodes: Optional[Dict[str, Any]] = None,
    interesting_nodes: Optional[list] = None,
    traversal_results: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Prepare comprehensive context for LLM-based analysis report generation.

    Instead of generating a rigid templated report, this function provides Claude with:
    1. Top 10 FDR-significant genes from the raw input data
    2. Top nodes from each modality (if provided)
    3. Interesting nodes identified by Claude (if provided)
    4. Network traversal results (if provided)
    5. Analysis parameters and file locations

    Claude will then generate a natural, contextualized report with:
    - Study summary and biological interpretation
    - Methods description
    - Results interpretation with biological context
    - Key findings and insights

    Args:
        working_dir: Directory containing analysis results
        analysis_params: Analysis parameters used (optional)
        top_nodes: Top nodes extracted from each modality (optional)
        interesting_nodes: Interesting nodes identified by LLM (optional)
        traversal_results: Network traversal results for interesting nodes (optional)

    Returns:
        Context dictionary for Claude to generate the report
    """
    logger.info("Preparing context for LLM-based report generation...")

    try:
        working_path = Path(working_dir)

        # Read top significant genes
        sig_genes_file = list(working_path.glob("*_significant.csv"))
        top_sig_genes = []

        if sig_genes_file:
            sig_genes_df = pd.read_csv(sig_genes_file[0])
            if not sig_genes_df.empty:
                # Get top 10 FDR-significant genes
                if 'fdr' in sig_genes_df.columns:
                    sig_genes_df_sorted = sig_genes_df.sort_values('fdr').head(10)
                elif 'FDR' in sig_genes_df.columns:
                    sig_genes_df_sorted = sig_genes_df.sort_values('FDR').head(10)
                else:
                    sig_genes_df_sorted = sig_genes_df.head(10)

                top_sig_genes = sig_genes_df_sorted.to_dict('records')
                logger.info(f"Loaded top 10 significant genes from {sig_genes_file[0].name}")
        else:
            logger.warning("No significant genes file found")

        # List output files
        output_files = {
            "analysis_results": [],
            "visualizations": [],
            "data_files": [],
            "logs": []
        }

        for file_path in working_path.iterdir():
            if file_path.is_file():
                if file_path.suffix == '.xlsx':
                    output_files["analysis_results"].append(str(file_path.name))
                elif file_path.suffix == '.png':
                    output_files["visualizations"].append(str(file_path.name))
                elif file_path.suffix in ['.csv', '.tsv']:
                    output_files["data_files"].append(str(file_path.name))
                elif file_path.suffix == '.log':
                    output_files["logs"].append(str(file_path.name))

        # Build comprehensive context
        context = {
            "analysis_metadata": {
                "working_directory": str(working_path),
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_significant_genes": len(sig_genes_df) if sig_genes_file else 0
            },
            "analysis_parameters": analysis_params or {},
            "top_significant_genes": top_sig_genes,
            "top_nodes_by_modality": top_nodes or {},
            "interesting_nodes": interesting_nodes or [],
            "network_traversal": traversal_results or {},
            "output_files": output_files
        }

        logger.info("Context prepared for LLM-based report generation")
        logger.info(f"  - Top significant genes: {len(top_sig_genes)}")
        logger.info(f"  - Modalities with top nodes: {len(top_nodes) if top_nodes else 0}")
        logger.info(f"  - Interesting nodes: {len(interesting_nodes) if interesting_nodes else 0}")

        return {
            "success": True,
            "report_context": context,
            "note": "Use this context to generate a comprehensive, natural language analysis report. "
                   "Include biological interpretation, key findings, and contextualize the results. "
                   "Write the report in markdown format and save to README.md in the working directory."
        }

    except Exception as e:
        logger.error(f"Error preparing report context: {e}")
        return {
            "success": False,
            "error": str(e)
        }
