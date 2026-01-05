"""
Path handler for tKOIAgent.

Handles resolving user-provided paths and using the file's directory
as the working directory for tKOI analysis workflows.
"""

from pathlib import Path
import shutil
import re
from typing import Tuple, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


def resolve_user_path(user_path: str) -> Path:
    """
    Resolve user-provided path to absolute path.

    Supports two path formats:
    1. Absolute paths: /absolute/path/to/file.csv
    2. Home-relative paths: ~/Documents/data.csv

    Args:
        user_path: User-provided file path

    Returns:
        Absolute Path object
    """
    user_path = user_path.strip()

    # Handle home directory expansion
    if user_path.startswith('~'):
        resolved = Path(user_path).expanduser()
        logger.info(f"Resolved home path: {user_path} -> {resolved}")
        return resolved

    # Handle absolute paths
    resolved = Path(user_path).resolve()
    logger.info(f"Using absolute path: {resolved}")
    return resolved


def check_gene_id_format(file_path: Path) -> dict:
    """
    Check if gene IDs in file are already in human Ensembl format.

    Args:
        file_path: Path to gene expression file

    Returns:
        dict with 'is_ensembl' bool and 'sample_ids' list
    """
    try:
        import pandas as pd

        # Read first column (gene IDs)
        if file_path.suffix == '.xlsx':
            df = pd.read_excel(file_path, nrows=100)
        else:
            df = pd.read_csv(file_path, nrows=100, sep=None, engine='python')

        gene_ids = df.iloc[:, 0].astype(str).tolist()

        # Check if IDs match Ensembl format (ENSG followed by 11 digits)
        ensembl_pattern = re.compile(r'^ENSG\d{11}$')
        ensembl_count = sum(1 for gid in gene_ids if ensembl_pattern.match(gid))

        # If >80% are Ensembl IDs, consider it already in correct format
        is_ensembl = (ensembl_count / len(gene_ids)) > 0.8

        logger.info(f"Gene ID check: {ensembl_count}/{len(gene_ids)} are Ensembl IDs")

        return {
            'is_ensembl': is_ensembl,
            'sample_ids': gene_ids[:5],
            'ensembl_count': ensembl_count,
            'total_checked': len(gene_ids)
        }
    except Exception as e:
        logger.warning(f"Could not check gene ID format: {e}")
        return {'is_ensembl': False, 'sample_ids': [], 'ensembl_count': 0, 'total_checked': 0}


# Legacy functions removed - no longer needed with new working directory approach
# Previously used for creating project subdirectories, now obsolete


def handle_input_file(user_path: str, project_name: Optional[str] = None) -> Tuple[Path, Path]:
    """
    Handle input file by resolving path and using its parent directory as working directory.

    Args:
        user_path: User-provided file path (absolute or ~/...)
        project_name: Unused (kept for backward compatibility)

    Returns:
        Tuple of (source_file_path, working_directory)
        - source_file_path: The original file at its location
        - working_directory: The parent directory of the file

    Raises:
        FileNotFoundError: If the source file doesn't exist
    """
    # Resolve user path to absolute path
    source_file = resolve_user_path(user_path)

    # Verify file exists
    if not source_file.exists():
        error_msg = f"File not found: {source_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    if not source_file.is_file():
        error_msg = f"Path is not a file: {source_file}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Use the file's parent directory as the working directory
    working_dir = source_file.parent
    logger.info(f"Using working directory: {working_dir}")

    return source_file, working_dir


# Legacy save_text_data function removed - not used in current implementation


def cleanup_temp_dir(temp_dir: Path) -> None:
    """
    Clean up temporary directory.

    Args:
        temp_dir: Temporary directory to remove
    """
    if temp_dir and temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Could not clean up temporary directory {temp_dir}: {e}")
