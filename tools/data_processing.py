"""
Data processing tools for tKOIAgent.

Provides tools for validating, cleaning, and converting gene expression data.
"""

from pathlib import Path
from typing import Optional
import pandas as pd
from utils.file_handler import FileHandler
from utils.gene_converter import GeneConverter
from utils.logger import get_logger
from utils.path_handler import handle_input_file, check_gene_id_format

logger = get_logger(__name__)


def validate_data_file(file_path: str, sheet_name: Optional[str] = None) -> dict:
    """
    Validate gene expression data file.

    Args:
        file_path: Path to data file (absolute or ~/... format)
        sheet_name: Sheet name for Excel files (optional)

    Returns:
        Validation report with issues and statistics
    """
    logger.info(f"Validating data file: {file_path}")

    try:
        # Resolve path and get working directory
        try:
            source_file, working_dir = handle_input_file(file_path)
            logger.info(f"File location: {source_file}")
            logger.info(f"Working directory: {working_dir}")
        except (FileNotFoundError, ValueError) as e:
            return {
                "valid": False,
                "issues": [str(e), "Please provide a valid file path."],
                "warnings": ["WORKFLOW STOPPED: File not accessible. Cannot proceed."],
                "stats": {},
                "instruction": "Supported path formats: absolute (/path/to/file) or home-relative (~/path/to/file)"
            }

        # Read file
        df = FileHandler.read_data_file(str(source_file), sheet_name)

        # Validate structure
        report = FileHandler.validate_gene_expression_data(df)

        if report['valid']:
            logger.info("Data file is valid")
        else:
            logger.warning(f"Validation issues found: {report['issues']}")

        if report['warnings']:
            logger.warning(f"Warnings: {report['warnings']}")

        # Add file location info
        report['file_path'] = str(source_file)
        report['working_dir'] = str(working_dir)
        report['note'] = f"All outputs will be saved to: {working_dir}"

        return report

    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {
            "valid": False,
            "issues": [str(e)],
            "warnings": [],
            "stats": {}
        }


def clean_data_file(
    input_path: str,
    output_path: str,
    remove_duplicates: bool = True,
    remove_zero_variance: bool = True,
    missing_threshold: float = 0.5,
    sheet_name: Optional[str] = None
) -> dict:
    """
    Clean gene expression data.

    Args:
        input_path: Input file path (absolute or ~/...)
        output_path: Output filename (will be saved in same directory as input)
        remove_duplicates: Remove duplicate gene IDs
        remove_zero_variance: Remove genes with zero variance
        missing_threshold: Maximum proportion of missing values (0-1)
        sheet_name: Excel sheet name (optional)

    Returns:
        Cleaning report with statistics
    """
    logger.info(f"Cleaning data file: {input_path}")

    try:
        # Resolve path and get working directory
        try:
            source_file, working_dir = handle_input_file(input_path)
        except (FileNotFoundError, ValueError) as e:
            return {
                "success": False,
                "error": str(e)
            }

        # Read data
        df = FileHandler.read_data_file(str(source_file), sheet_name)
        initial_count = len(df)

        # Clean data
        df_clean = FileHandler.clean_gene_expression_data(
            df,
            remove_duplicates=remove_duplicates,
            remove_zero_variance=remove_zero_variance,
            remove_missing_threshold=missing_threshold
        )

        # Save cleaned data to same directory as input
        output_path_obj = working_dir / Path(output_path).name
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        if output_path_obj.suffix == '.xlsx':
            df_clean.to_excel(output_path_obj, index=True)
        else:
            df_clean.to_csv(output_path_obj, index=True)

        # Save FDR-significant genes if FDR column exists
        fdr_col = None
        if 'fdr' in df_clean.columns:
            fdr_col = 'fdr'
        elif 'FDR' in df_clean.columns:
            fdr_col = 'FDR'

        significant_file = None
        significant_count = 0

        if fdr_col:
            df_significant = df_clean[df_clean[fdr_col] <= 0.05]
            if len(df_significant) > 0:
                sig_filename = f"{output_path_obj.stem}_significant.csv"
                significant_file = working_dir / sig_filename
                df_significant.to_csv(significant_file, index=True)
                significant_count = len(df_significant)
                logger.info(f"Saved {significant_count} FDR-significant genes to: {significant_file}")
            else:
                logger.info("No genes with FDR <= 0.05 found")
        else:
            logger.info("No FDR column found in cleaned data")

        report = {
            "success": True,
            "initial_genes": initial_count,
            "final_genes": len(df_clean),
            "removed_genes": initial_count - len(df_clean),
            "output_file": str(output_path_obj),
            "working_dir": str(working_dir),
            "note": f"Cleaned data saved to: {output_path_obj}",
            "significant_genes_file": str(significant_file) if significant_file else None,
            "significant_genes_count": significant_count
        }

        logger.info(f"Cleaned data saved: {output_path_obj}")
        logger.info(f"Retained {len(df_clean)}/{initial_count} genes")

        return report

    except Exception as e:
        logger.error(f"Cleaning error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def convert_gene_ids(
    input_path: str,
    output_path: str,
    source_format: Optional[str] = None,
    include_mouse_orthologs: bool = True,
    sheet_name: Optional[str] = None
) -> dict:
    """
    Convert gene IDs to human Ensembl format.

    Args:
        input_path: Input file with gene IDs (absolute or ~/...)
        output_path: Output filename (will be saved in same directory as input)
        source_format: Source ID format (auto-detect if None)
            Options: 'ensembl.gene', 'entrezgene', 'hgnc', 'symbol'
        include_mouse_orthologs: Convert mouse genes to human orthologs
        sheet_name: Excel sheet name (optional)

    Returns:
        Conversion report with statistics
    """
    logger.info(f"Converting gene IDs: {input_path}")

    try:
        # Resolve path and get working directory
        try:
            source_file, working_dir = handle_input_file(input_path)
        except (FileNotFoundError, ValueError) as e:
            return {
                "success": False,
                "error": str(e)
            }

        # Check if gene IDs are already in Ensembl format
        id_check = check_gene_id_format(source_file)
        if id_check['is_ensembl']:
            logger.info(f"Gene IDs are already in Ensembl format ({id_check['ensembl_count']}/{id_check['total_checked']} checked)")
            return {
                "success": True,
                "skipped": True,
                "reason": "Gene IDs are already in human Ensembl format",
                "file_path": str(source_file),
                "working_dir": str(working_dir),
                "total_checked": id_check['total_checked'],
                "ensembl_count": id_check['ensembl_count'],
                "note": "Conversion skipped - IDs already in correct format. Use original file for analysis."
            }

        # Read data
        df = FileHandler.read_data_file(str(source_file), sheet_name)
        gene_ids = df.iloc[:, 0].astype(str).tolist()

        # Convert IDs
        converter = GeneConverter()
        conversion_df, stats = converter.convert_to_human_ensembl(
            gene_ids,
            source_format=source_format,
            include_orthologs=include_mouse_orthologs
        )

        # Merge with original data
        df_converted = df.copy()

        # Add converted columns
        if not conversion_df.empty and 'human_ensembl' in conversion_df.columns:
            df_converted.insert(1, 'human_ensembl', conversion_df['human_ensembl'].values)
            if 'symbol' in conversion_df.columns:
                df_converted.insert(2, 'gene_symbol', conversion_df['symbol'].values)

        # Save results to same directory as input
        output_path_obj = working_dir / Path(output_path).name
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        if output_path_obj.suffix == '.xlsx':
            # Multi-sheet: data + conversion report
            with pd.ExcelWriter(str(output_path_obj), engine='openpyxl') as writer:
                df_converted.to_excel(writer, sheet_name='Converted_Data', index=False)
                if not conversion_df.empty:
                    conversion_df.to_excel(writer, sheet_name='Conversion_Details', index=False)
        else:
            df_converted.to_csv(output_path_obj, index=False)

        logger.info(f"Conversion complete: {stats['success_rate']:.1f}% success")
        logger.info(f"Mapped: {stats['successfully_mapped']}/{stats['total_input']} genes")

        result = {
            "success": True,
            "skipped": False,
            "output_file": str(output_path_obj),
            "working_dir": str(working_dir),
            "note": f"Converted data saved to: {output_path_obj}",
            **stats
        }

        return result

    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
