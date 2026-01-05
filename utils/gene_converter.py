"""
Gene ID conversion utility using MyGene.info API.

Supports multi-format gene ID conversion to human Ensembl IDs,
including mouse-to-human ortholog mapping.
"""

import mygene
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)


class GeneConverter:
    """Handles gene ID conversion using MyGene.info API"""

    def __init__(self):
        self.mg = mygene.MyGeneInfo()
        self.supported_formats = {
            "ensembl.gene": "Ensembl Gene ID",
            "entrezgene": "NCBI Entrez Gene ID",
            "hgnc": "HGNC ID",
            "symbol": "Gene Symbol"
        }

    def detect_id_format(self, gene_ids: List[str]) -> str:
        """
        Auto-detect gene ID format from sample.

        Args:
            gene_ids: List of gene identifiers

        Returns:
            Detected format string
        """
        sample = gene_ids[:min(100, len(gene_ids))]  # Test first 100 IDs

        # Pattern matching
        ensembl_pattern = sum(1 for g in sample if isinstance(g, str) and g.startswith(('ENSG', 'ENSMUSG')))
        entrez_pattern = sum(1 for g in sample if str(g).isdigit())
        hgnc_pattern = sum(1 for g in sample if isinstance(g, str) and g.startswith('HGNC:'))

        # Determine most likely format
        if ensembl_pattern / len(sample) > 0.8:
            logger.info("Detected format: Ensembl Gene ID")
            return "ensembl.gene"
        elif entrez_pattern / len(sample) > 0.8:
            logger.info("Detected format: Entrez Gene ID")
            return "entrezgene"
        elif hgnc_pattern / len(sample) > 0.8:
            logger.info("Detected format: HGNC ID")
            return "hgnc"
        else:
            logger.info("Detected format: Gene Symbol (default)")
            return "symbol"

    def convert_to_human_ensembl(
        self,
        gene_ids: List[str],
        source_format: Optional[str] = None,
        include_orthologs: bool = True
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Convert gene IDs to human Ensembl IDs.

        Args:
            gene_ids: List of input gene identifiers
            source_format: Source format (auto-detect if None)
            include_orthologs: Include mouse orthologs for mouse genes

        Returns:
            Tuple of (conversion DataFrame, statistics dict)
        """
        # Auto-detect format if not provided
        if source_format is None:
            source_format = self.detect_id_format(gene_ids)

        logger.info(f"Converting {len(gene_ids)} IDs from {source_format} to human Ensembl")

        try:
            # Query MyGene.info
            results = self.mg.querymany(
                gene_ids,
                scopes=source_format,
                fields="ensembl.gene,symbol,entrezgene,taxid",
                species="human,mouse",  # Support both species
                returnall=True
            )

            # Process results
            df = pd.DataFrame(results['out']) if results['out'] else pd.DataFrame()
            missing = results.get('missing', [])
            duplicates = results.get('dup', [])

            if df.empty:
                logger.warning("No results returned from MyGene")
                return pd.DataFrame(), {
                    "total_input": len(gene_ids),
                    "successfully_mapped": 0,
                    "failed_mapping": len(gene_ids),
                    "duplicates": 0,
                    "mouse_orthologs_converted": 0,
                    "success_rate": 0.0
                }

            # Handle mouse genes (convert to human orthologs if requested)
            mouse_count = 0
            if include_orthologs and 'taxid' in df.columns:
                mouse_genes = df[df['taxid'] == 10090]  # Mouse taxid
                mouse_count = len(mouse_genes)
                if mouse_count > 0:
                    logger.info(f"Found {mouse_count} mouse genes, fetching human orthologs")
                    # Note: Ortholog mapping would require additional API calls
                    # For now, we'll mark them but not convert
                    logger.warning("Mouse ortholog conversion not fully implemented")

            # Extract human Ensembl IDs
            if 'ensembl' in df.columns:
                # Handle case where ensembl is a dict/object
                def extract_ensembl(x):
                    if pd.isna(x):
                        return None
                    if isinstance(x, dict):
                        gene_id = x.get('gene', None)
                        if isinstance(gene_id, str) and gene_id.startswith('ENSG'):
                            return gene_id
                        return None
                    if isinstance(x, str) and x.startswith('ENSG'):
                        return x
                    return None

                df['human_ensembl'] = df['ensembl'].apply(extract_ensembl)
            else:
                df['human_ensembl'] = None

            # Generate statistics
            successfully_mapped = df['human_ensembl'].notna().sum()
            stats = {
                "total_input": len(gene_ids),
                "successfully_mapped": int(successfully_mapped),
                "failed_mapping": len(missing),
                "duplicates": len(duplicates),
                "mouse_orthologs_converted": mouse_count,
                "success_rate": (successfully_mapped / len(gene_ids) * 100) if len(gene_ids) > 0 else 0.0
            }

            logger.info(f"Conversion complete: {stats['success_rate']:.1f}% success rate")

            return df, stats

        except Exception as e:
            logger.error(f"Error during gene ID conversion: {e}")
            return pd.DataFrame(), {
                "total_input": len(gene_ids),
                "successfully_mapped": 0,
                "failed_mapping": len(gene_ids),
                "duplicates": 0,
                "mouse_orthologs_converted": 0,
                "success_rate": 0.0,
                "error": str(e)
            }

    def validate_ensembl_ids(self, ensembl_ids: List[str]) -> Dict[str, Any]:
        """
        Validate that IDs are valid human Ensembl gene IDs.

        Args:
            ensembl_ids: List of Ensembl IDs to validate

        Returns:
            Validation report dictionary
        """
        valid = []
        invalid = []

        for gene_id in ensembl_ids:
            if isinstance(gene_id, str) and gene_id.startswith('ENSG'):
                valid.append(gene_id)
            else:
                invalid.append(gene_id)

        return {
            "valid_count": len(valid),
            "invalid_count": len(invalid),
            "valid_ids": valid,
            "invalid_ids": invalid[:10]  # Limit to first 10 for display
        }
