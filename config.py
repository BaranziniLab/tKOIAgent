"""
Configuration management for tKOIAgent MCP server.

Contains hardcoded SPOKE credentials and configurable default parameters.
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class SpokeConfig:
    """SPOKE Neo4j database configuration (hardcoded as per requirements)"""
    uri: str = "bolt://spokedev.cgl.ucsf.edu:7687"
    username: str = "neo4j"
    password: str = "SPOKEdev"
    database: str = "spoke"
    max_connection_pool_size: int = 10
    connection_timeout: int = 30
    max_transaction_retry_time: int = 30


@dataclass
class TKOIConfig:
    """tKOI analysis default parameters (user-configurable via environment variables)"""
    # Network propagation parameters
    alpha: float = 0.85  # Restart probability (damping_factor)
    max_iterations: int = 500  # Maximum propagation iterations (maximum_iteration)
    convergence_threshold: float = 1e-6  # Convergence threshold

    # Analysis threshold parameters (user-configurable)
    logfc_threshold: float = 0.25  # Log fold-change threshold for differential expression
    indirect_link_threshold: float = 3.0  # Threshold for indirect network links (required indirect connectivity)
    topology_similarity: float = 0.9  # Topology similarity threshold for selecting matched genes in permutations
    n_permutation: int = 30  # Number of permutations for statistical testing

    # Network construction parameters
    edge_weight_method: str = "jaccard"  # jaccard, dice, or overlap
    normalize: bool = True  # Normalize expression values
    remove_isolated: bool = True  # Remove isolated nodes
    min_network_size: int = 10  # Minimum network size

    # Reproducibility
    seed: int = 42  # Random seed

    def __post_init__(self):
        """Load user-configurable parameters from environment variables"""
        self.logfc_threshold = float(os.getenv("TKOI_LOGFC_THRESHOLD", self.logfc_threshold))
        self.indirect_link_threshold = float(os.getenv("TKOI_INDIRECT_LINK_THRESHOLD", self.indirect_link_threshold))
        self.topology_similarity = float(os.getenv("TKOI_TOPOLOGY_SIMILARITY", self.topology_similarity))
        self.n_permutation = int(os.getenv("TKOI_N_PERMUTATION", self.n_permutation))
        self.alpha = float(os.getenv("TKOI_DAMPING_FACTOR", self.alpha))
        self.max_iterations = int(os.getenv("TKOI_MAXIMUM_ITERATION", self.max_iterations))


@dataclass
class OutputConfig:
    """Output file configuration"""
    # Visualization settings
    dpi: int = 800  # Publication-quality resolution
    plot_width: float = 10  # inches
    plot_height: float = 8  # inches

    # File settings
    excel_engine: str = "openpyxl"  # Excel writer engine


@dataclass
class GeneConversionConfig:
    """Gene ID conversion settings"""
    target_format: str = "ensembl.gene"  # Target: human Ensembl IDs
    source_formats: List[str] = None  # Auto-detect
    species: str = "human"
    mouse_ortholog_mapping: bool = True  # Convert mouse genes to human orthologs

    def __post_init__(self):
        if self.source_formats is None:
            self.source_formats = ["ensembl.gene", "entrezgene", "hgnc", "symbol"]


class Config:
    """Main configuration container"""

    def __init__(self):
        self.spoke = SpokeConfig()
        self.tkoi = TKOIConfig()
        self.output = OutputConfig()
        self.gene_conversion = GeneConversionConfig()

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return {
            "spoke": {
                "uri": self.spoke.uri,
                "username": self.spoke.username,
                "database": self.spoke.database,
                "max_connection_pool_size": self.spoke.max_connection_pool_size,
                "connection_timeout": self.spoke.connection_timeout,
            },
            "tkoi": {
                "damping_factor": self.tkoi.alpha,
                "maximum_iteration": self.tkoi.max_iterations,
                "convergence_threshold": self.tkoi.convergence_threshold,
                "logfc_threshold": self.tkoi.logfc_threshold,
                "indirect_link_threshold": self.tkoi.indirect_link_threshold,
                "topology_similarity": self.tkoi.topology_similarity,
                "n_permutation": self.tkoi.n_permutation,
                "edge_weight_method": self.tkoi.edge_weight_method,
                "normalize": self.tkoi.normalize,
                "remove_isolated": self.tkoi.remove_isolated,
                "min_network_size": self.tkoi.min_network_size,
                "seed": self.tkoi.seed,
            },
            "output": {
                "dpi": self.output.dpi,
                "plot_width": self.output.plot_width,
                "plot_height": self.output.plot_height,
            },
            "gene_conversion": {
                "target_format": self.gene_conversion.target_format,
                "species": self.gene_conversion.species,
                "mouse_ortholog_mapping": self.gene_conversion.mouse_ortholog_mapping,
            }
        }


# Global configuration instance
config = Config()
