"""
File handling utilities for tKOIAgent.

Supports multiple formats: Excel (.xlsx, .xls), CSV, TSV, TXT
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from utils.logger import get_logger

logger = get_logger(__name__)


class FileHandler:
    """Handles reading and writing various file formats"""

    SUPPORTED_INPUT_FORMATS = ['.xlsx', '.xls', '.csv', '.tsv', '.txt']
    SUPPORTED_OUTPUT_FORMATS = ['.xlsx', '.csv', '.tsv', '.png', '.json']

    @staticmethod
    def detect_delimiter(file_path: Path) -> str:
        """
        Auto-detect delimiter for text files.

        Args:
            file_path: Path to text file

        Returns:
            Detected delimiter character
        """
        with open(file_path, 'r') as f:
            first_line = f.readline()

        if '\t' in first_line:
            return '\t'
        elif ',' in first_line:
            return ','
        elif ';' in first_line:
            return ';'
        else:
            return ','  # Default to comma

    @classmethod
    def read_data_file(
        cls,
        file_path: Union[str, Path],
        sheet_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Read data file in multiple formats.

        Args:
            file_path: Path to input file
            sheet_name: Excel sheet name (for .xlsx/.xls files)

        Returns:
            pandas DataFrame

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format not supported
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix not in cls.SUPPORTED_INPUT_FORMATS:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                f"Supported: {cls.SUPPORTED_INPUT_FORMATS}"
            )

        logger.info(f"Reading data file: {file_path}")

        try:
            if suffix in ['.xlsx', '.xls']:
                df = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name or 0,
                    engine='openpyxl' if suffix == '.xlsx' else None
                )
            elif suffix == '.csv':
                df = pd.read_csv(file_path)
            elif suffix in ['.tsv', '.txt']:
                delimiter = cls.detect_delimiter(file_path)
                df = pd.read_csv(file_path, sep=delimiter)

            logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
            return df

        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise

    @staticmethod
    def write_excel_multi_sheet(
        data_dict: Dict[str, pd.DataFrame],
        output_path: Union[str, Path],
        include_index: bool = False
    ):
        """
        Write multiple DataFrames to Excel with separate sheets.

        Args:
            data_dict: Dictionary mapping sheet names to DataFrames
            output_path: Output Excel file path
            include_index: Whether to include DataFrame index
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing multi-sheet Excel to {output_path}")

        with pd.ExcelWriter(
            output_path,
            engine='openpyxl',
            mode='w'
        ) as writer:
            for sheet_name, df in data_dict.items():
                # Truncate sheet name if too long (Excel limit: 31 chars)
                sheet_name_truncated = sheet_name[:31]
                df.to_excel(
                    writer,
                    sheet_name=sheet_name_truncated,
                    index=include_index
                )
                logger.info(f"  Sheet '{sheet_name_truncated}': {len(df)} rows")

        logger.info(f"Excel file created: {output_path}")

    @staticmethod
    def validate_gene_expression_data(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate gene expression data structure.

        Expected format:
        - First column: Gene IDs
        - Remaining columns: Sample expression values (numeric)

        Args:
            df: DataFrame to validate

        Returns:
            Validation report dictionary with 'valid', 'issues', 'warnings', 'stats'
        """
        issues = []
        warnings = []

        # Check minimum dimensions
        if len(df) == 0:
            issues.append("DataFrame is empty")
        if len(df.columns) < 2:
            issues.append("Need at least 2 columns (gene IDs + 1 sample)")

        # Check for missing values in gene ID column
        if len(df) > 0:
            gene_col = df.iloc[:, 0]
            if gene_col.isna().any():
                issues.append(f"Found {gene_col.isna().sum()} missing gene IDs")

            # Check for duplicate gene IDs
            duplicates = gene_col.duplicated().sum()
            if duplicates > 0:
                warnings.append(f"Found {duplicates} duplicate gene IDs")

        # Check numeric columns
        if len(df.columns) > 1:
            numeric_cols = df.iloc[:, 1:]
            non_numeric = []
            for col in numeric_cols.columns:
                if not pd.api.types.is_numeric_dtype(numeric_cols[col]):
                    non_numeric.append(col)

            if non_numeric:
                issues.append(f"Non-numeric expression columns: {non_numeric[:5]}")

            # Check for negative values (warn only)
            if (numeric_cols < 0).any().any():
                warnings.append("Found negative expression values")

        # Statistics
        stats = {
            "total_genes": len(df),
            "total_columns": len(df.columns) - 1 if len(df.columns) > 1 else 0,  # Data columns (excluding gene ID)
            "missing_values": df.iloc[:, 1:].isna().sum().sum() if len(df.columns) > 1 else 0,
            "zero_values": (df.iloc[:, 1:] == 0).sum().sum() if len(df.columns) > 1 else 0
        }

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": stats
        }

    @staticmethod
    def clean_gene_expression_data(
        df: pd.DataFrame,
        remove_duplicates: bool = True,
        remove_zero_variance: bool = True,
        remove_missing_threshold: float = 0.5
    ) -> pd.DataFrame:
        """
        Clean gene expression data.

        Args:
            df: Input DataFrame
            remove_duplicates: Remove duplicate gene IDs (keep first)
            remove_zero_variance: Remove genes with no variance
            remove_missing_threshold: Remove genes with >X proportion missing

        Returns:
            Cleaned DataFrame
        """
        logger.info(f"Cleaning data: {len(df)} rows initial")

        # Set first column as index (gene IDs)
        df_clean = df.copy()
        df_clean.set_index(df_clean.columns[0], inplace=True)

        # Remove duplicates
        if remove_duplicates:
            before = len(df_clean)
            df_clean = df_clean[~df_clean.index.duplicated(keep='first')]
            removed = before - len(df_clean)
            if removed > 0:
                logger.info(f"  Removed {removed} duplicate genes")

        # Remove genes with too many missing values
        missing_prop = df_clean.isna().sum(axis=1) / len(df_clean.columns)
        genes_to_keep = missing_prop <= remove_missing_threshold
        removed = (~genes_to_keep).sum()
        if removed > 0:
            logger.info(f"  Removed {removed} genes with >{remove_missing_threshold*100}% missing")
            df_clean = df_clean[genes_to_keep]

        # Remove zero variance genes
        if remove_zero_variance:
            variance = df_clean.var(axis=1)
            zero_var = variance == 0
            removed = zero_var.sum()
            if removed > 0:
                logger.info(f"  Removed {removed} zero-variance genes")
                df_clean = df_clean[~zero_var]

        logger.info(f"Cleaning complete: {len(df_clean)} rows remaining")
        return df_clean
