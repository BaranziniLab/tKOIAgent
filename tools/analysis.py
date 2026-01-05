"""
Analysis tool for tKOIAgent.

Provides tKOI network propagation analysis functionality.
"""

from pathlib import Path
from typing import Optional
import pandas as pd
from utils.r_executor import RExecutor, RExecutionError
from utils.logger import get_logger
from utils.path_handler import handle_input_file
from config import config

logger = get_logger(__name__)


def run_tkoi_analysis(
    data_file: str,
    output_dir: Optional[str] = None,
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

    Args:
        data_file: Path to gene expression data (absolute or ~/...)
        output_dir: (Optional) Ignored - output always goes to file's directory
        alpha: Restart probability (0-1, default: 0.85)
        max_iterations: Maximum propagation iterations (default: 500)
        convergence_threshold: Convergence threshold (default: 1e-6)
        edge_weight_method: Edge weighting method (default: 'jaccard')
            Options: 'jaccard', 'dice', 'overlap'
        normalize: Normalize expression values (default: True)
        remove_isolated: Remove isolated nodes (default: True)
        min_network_size: Minimum network size (default: 10)
        seed: Random seed for reproducibility (default: 42)

    Returns:
        Analysis results with output file paths
    """
    logger.info("Starting tKOI analysis...")

    try:
        # Resolve path and get working directory
        try:
            source_file, working_dir = handle_input_file(data_file)
        except (FileNotFoundError, ValueError) as e:
            return {
                "success": False,
                "error": str(e)
            }

        # Use file's directory for output
        working_dir.mkdir(parents=True, exist_ok=True)

        # Use config defaults for unspecified parameters
        params = {
            "data_file": str(source_file),
            "output_dir": str(working_dir),
            "alpha": alpha if alpha is not None else config.tkoi.alpha,
            "max_iterations": max_iterations if max_iterations is not None else config.tkoi.max_iterations,
            "convergence_threshold": convergence_threshold if convergence_threshold is not None else config.tkoi.convergence_threshold,
            "edge_weight_method": edge_weight_method or config.tkoi.edge_weight_method,
            "normalize": normalize if normalize is not None else config.tkoi.normalize,
            "remove_isolated": remove_isolated if remove_isolated is not None else config.tkoi.remove_isolated,
            "min_network_size": min_network_size if min_network_size is not None else config.tkoi.min_network_size,
            "seed": seed if seed is not None else config.tkoi.seed,
            # tKOI-specific parameters
            "logfc_threshold": config.tkoi.logfc_threshold,
            "indirect_link_threshold": config.tkoi.indirect_link_threshold,
            "topology_similarity": config.tkoi.topology_similarity,
            "n_permutation": config.tkoi.n_permutation
        }

        logger.info(f"Parameters: alpha={params['alpha']}, max_iter={params['max_iterations']}")

        # Execute R analysis script
        executor = RExecutor(Path(__file__).parent.parent / "scripts")
        result = executor.execute_script(
            "run_analysis.R",
            args=params,
            timeout=1800  # 30 minutes for large datasets
        )

        if result.get('success'):
            logger.info("tKOI analysis complete")
            logger.info(f"Output files: {result.get('output_files', [])}")

            # Add directory information to result
            result['working_dir'] = str(working_dir)
            result['note'] = f"Analysis completed. All outputs saved to: {working_dir}"
        else:
            logger.warning(f"Analysis issues: {result.get('message')}")

        return result

    except RExecutionError as e:
        logger.error(f"Analysis error: {e}")
        return {
            "success": False,
            "error": str(e),
            "stderr": e.stderr
        }
    except Exception as e:
        logger.error(f"Unexpected analysis error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def extract_top_nodes(working_dir: str, top_n: int = 10) -> dict:
    """
    Extract top N nodes from each modality in tKOI results.

    Args:
        working_dir: Directory containing tKOI analysis results
        top_n: Number of top nodes to extract per modality (default: 10)

    Returns:
        Dictionary with top nodes by modality and formatted context for LLM interpretation
    """
    logger.info(f"Extracting top {top_n} nodes from tKOI results...")

    try:
        working_path = Path(working_dir)
        summary_file = working_path / "tkoi_summary.xlsx"

        if not summary_file.exists():
            return {
                "success": False,
                "error": f"tKOI summary file not found: {summary_file}",
                "note": "Run tKOI analysis first using tkoi_run_analysis"
            }

        # Define modalities to extract
        modalities = [
            "Anatomy", "CellType", "Complex", "Pathway", "Disease",
            "BiologicalProcess", "CellularComponent", "MolecularFunction", "Gene"
        ]

        top_nodes = {}
        total_nodes_extracted = 0

        for modality in modalities:
            try:
                # Read sheet for this modality
                df = pd.read_excel(summary_file, sheet_name=modality)

                if df.empty:
                    continue

                # Sort by FDR (ascending) and take top N
                if 'fdr' in df.columns:
                    df_sorted = df.sort_values('fdr').head(top_n)
                    top_nodes[modality] = df_sorted.to_dict('records')
                    total_nodes_extracted += len(df_sorted)
                    logger.info(f"  {modality}: extracted {len(df_sorted)} nodes")

            except Exception as e:
                logger.warning(f"  {modality}: could not extract ({str(e)})")
                continue

        if not top_nodes:
            return {
                "success": False,
                "error": "No nodes could be extracted from any modality",
                "note": "Check if tKOI analysis completed successfully"
            }

        # Format context for LLM interpretation
        context_lines = [
            f"# Top {top_n} Nodes from tKOI Analysis",
            "",
            "## Overview",
            f"Extracted {total_nodes_extracted} total nodes across {len(top_nodes)} modalities.",
            ""
        ]

        for modality, nodes in top_nodes.items():
            context_lines.append(f"## {modality} (Top {len(nodes)})")
            context_lines.append("")

            for i, node in enumerate(nodes, 1):
                name = node.get('name', node.get('node', 'Unknown'))
                fdr = node.get('fdr', 'N/A')
                pvalue = node.get('pvalue', node.get('p.value', 'N/A'))

                context_lines.append(f"{i}. **{name}**")
                context_lines.append(f"   - FDR: {fdr}")
                context_lines.append(f"   - P-value: {pvalue}")
                context_lines.append("")

        formatted_context = "\n".join(context_lines)

        logger.info(f"Successfully extracted {total_nodes_extracted} nodes from {len(top_nodes)} modalities")

        return {
            "success": True,
            "top_nodes": top_nodes,
            "formatted_context": formatted_context,
            "total_nodes": total_nodes_extracted,
            "modalities_count": len(top_nodes),
            "working_dir": str(working_path),
            "note": f"Use this context to identify interesting nodes for network traversal"
        }

    except Exception as e:
        logger.error(f"Error extracting top nodes: {e}")
        return {
            "success": False,
            "error": str(e)
        }
