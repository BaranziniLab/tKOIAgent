"""
Visualization tool for tKOIAgent.

Provides publication-quality plot generation using ggplot2.
"""

from pathlib import Path
from typing import Optional, List
from utils.r_executor import RExecutor, RExecutionError
from utils.logger import get_logger
from config import config

logger = get_logger(__name__)


def generate_plots(
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
        plot_types: List of plot types to generate
            Options: ['volcano', 'score_distribution', 'top_genes']
            Default: all types
        dpi: Plot resolution (default: 800)
        width: Plot width in inches (default: 10)
        height: Plot height in inches (default: 8)

    Returns:
        Dictionary with generated plot file paths
    """
    logger.info("Generating publication-quality plots...")

    # Use config defaults
    params = {
        "results_file": str(Path(analysis_results_file).absolute()),
        "output_dir": str(Path(output_dir).absolute()),
        "plot_types": plot_types or ['volcano', 'score_distribution', 'top_genes'],
        "dpi": dpi if dpi is not None else config.output.dpi,
        "width": width if width is not None else config.output.plot_width,
        "height": height if height is not None else config.output.plot_height
    }

    logger.info(f"Plot types: {params['plot_types']}")
    logger.info(f"Resolution: {params['dpi']} dpi")

    try:
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Execute R plotting script
        executor = RExecutor(Path(__file__).parent.parent / "scripts")
        result = executor.execute_script(
            "generate_plots.R",
            args=params,
            timeout=600  # 10 minutes
        )

        if result.get('success'):
            plots = result.get('plot_files', [])
            logger.info(f"Generated {len(plots)} plots")
            for plot_file in plots:
                logger.info(f"  - {plot_file}")
        else:
            logger.warning(f"Plotting issues: {result.get('message')}")

        return result

    except RExecutionError as e:
        logger.error(f"Plotting error: {e}")
        return {
            "success": False,
            "error": str(e),
            "stderr": e.stderr
        }
    except Exception as e:
        logger.error(f"Unexpected plotting error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
