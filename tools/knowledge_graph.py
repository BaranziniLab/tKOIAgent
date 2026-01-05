"""
Knowledge graph tools for tKOIAgent.

Provides SPOKE Neo4j knowledge graph integration tools.
"""

import json
from pathlib import Path
from typing import Optional, List
from utils.neo4j_client import SpokeClient
from utils.logger import get_logger

logger = get_logger(__name__)

# Global SPOKE client instance (reuse connection across calls)
_spoke_client = None


def get_spoke_client() -> SpokeClient:
    """Get or create SPOKE client instance."""
    global _spoke_client
    if _spoke_client is None:
        _spoke_client = SpokeClient()
    return _spoke_client


def query_spoke_genes(
    gene_ids: List[str],
    relationship_types: Optional[List[str]] = None,
    max_depth: int = 1
) -> dict:
    """
    Query SPOKE knowledge graph for gene information.

    Args:
        gene_ids: List of human Ensembl gene IDs
        relationship_types: Filter by relationship types (optional)
            Examples: ['ASSOCIATES_DaG', 'INTERACTS_GiG', 'PARTICIPATES_GpPW']
        max_depth: Maximum traversal depth (1-3, default: 1)

    Returns:
        Dictionary with query results and statistics
    """
    logger.info(f"Querying SPOKE for {len(gene_ids)} genes...")

    try:
        client = get_spoke_client()

        # Query SPOKE
        results = client.query_genes(
            gene_ids=gene_ids,
            relationship_types=relationship_types,
            max_depth=max_depth
        )

        logger.info(f"Retrieved {len(results)} records from SPOKE")

        return {
            "success": True,
            "total_records": len(results),
            "results": results[:100],  # Limit for readability
            "message": f"Full results contain {len(results)} records" if len(results) > 100 else "Complete results"
        }

    except Exception as e:
        logger.error(f"SPOKE query error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def extract_spoke_subnetwork(
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
            Examples: ['Disease', 'Compound', 'Pathway', 'Anatomy']
        edge_types: Filter edges by type (optional)

    Returns:
        Subnetwork statistics and file path
    """
    logger.info(f"Extracting subnetwork for {len(gene_ids)} genes...")

    try:
        client = get_spoke_client()

        # Extract subnetwork
        subnetwork = client.extract_subnetwork(
            gene_ids=gene_ids,
            node_types=node_types,
            edge_types=edge_types
        )

        # Save to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(subnetwork, f, indent=2)

        stats = subnetwork.get('stats', {})
        logger.info(f"Subnetwork extracted")
        logger.info(f"  Nodes: {stats.get('total_nodes', 0)}")
        logger.info(f"  Edges: {stats.get('total_edges', 0)}")
        logger.info(f"  Saved to: {output_file}")

        return {
            "success": True,
            "output_file": str(output_path),
            **stats
        }

    except Exception as e:
        logger.error(f"Subnetwork extraction error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_gene_disease_associations(
    gene_ids: List[str],
    output_file: Optional[str] = None
) -> dict:
    """
    Query gene-disease associations from SPOKE.

    Args:
        gene_ids: List of gene IDs (Ensembl)
        output_file: Optional output file path (CSV)

    Returns:
        Gene-disease associations
    """
    logger.info("Querying gene-disease associations...")

    try:
        client = get_spoke_client()

        # Query associations
        df = client.get_gene_diseases(gene_ids)

        # Save if requested
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            logger.info(f"Saved associations to: {output_file}")

        logger.info(f"Found {len(df)} gene-disease associations")

        return {
            "success": True,
            "total_associations": len(df),
            "associations": df.to_dict('records')[:50],  # Limit for display
            "output_file": str(output_file) if output_file else None
        }

    except Exception as e:
        logger.error(f"Gene-disease query error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def traverse_interesting_nodes(
    interesting_nodes: List[dict],
    significant_genes_file: str,
    max_hops: int = 2
) -> dict:
    """
    Perform network traversal to understand why nodes are ranked highly.

    For each interesting node identified by Claude:
    1. Find genes from significant_genes.csv that are related
    2. Traverse up to max_hops in SPOKE
    3. Identify connecting paths and intermediate nodes

    Args:
        interesting_nodes: List of interesting nodes from LLM interpretation
            Format: [{'modality': 'Pathway', 'name': 'Node Name', 'reason': '...'}, ...]
        significant_genes_file: Path to CSV with FDR-significant genes
        max_hops: Maximum network hops (1-3, default: 2)

    Returns:
        Traversal results with paths and explanations for each node
    """
    logger.info(f"Starting network traversal for {len(interesting_nodes)} interesting nodes...")

    try:
        import pandas as pd

        # Read significant genes
        genes_df = pd.read_csv(significant_genes_file)
        if genes_df.empty:
            return {
                "success": False,
                "error": "No genes found in significant genes file"
            }

        # Get gene IDs from first column
        gene_ids = genes_df.iloc[:, 0].astype(str).tolist()
        logger.info(f"Found {len(gene_ids)} significant genes for traversal")

        client = get_spoke_client()
        traversal_results = {}

        for node_info in interesting_nodes:
            node_name = node_info.get('name', 'Unknown')
            modality = node_info.get('modality', 'Unknown')

            logger.info(f"Traversing node: {node_name} ({modality})")

            try:
                # Build Cypher query to find paths between genes and this node
                # This is a simplified query - adjust based on SPOKE schema
                query = f"""
                MATCH path = (g:Gene)-[*1..{max_hops}]-(n:{modality})
                WHERE g.identifier IN $gene_ids AND n.name = $node_name
                WITH path, nodes(path) as path_nodes, relationships(path) as path_rels
                RETURN
                    [node IN path_nodes | {{label: labels(node)[0], name: node.name, id: node.identifier}}] as nodes,
                    [rel IN path_rels | type(rel)] as relationships,
                    length(path) as path_length
                LIMIT 50
                """

                params = {
                    "gene_ids": gene_ids,
                    "node_name": node_name
                }

                # Execute query
                results = client.execute_query(query, params)

                # Process results
                related_genes = set()
                paths = []
                intermediate_nodes = set()

                for record in results:
                    nodes = record.get('nodes', [])
                    relationships = record.get('relationships', [])
                    path_length = record.get('path_length', 0)

                    # Extract gene from first node
                    if nodes and nodes[0].get('label') == 'Gene':
                        related_genes.add(nodes[0].get('id'))

                    # Extract intermediate nodes (exclude first and last)
                    for node in nodes[1:-1]:
                        intermediate_nodes.add(f"{node.get('label')}:{node.get('name')}")

                    # Format path
                    path_str = " -> ".join([
                        f"{nodes[i].get('name')} [{relationships[i] if i < len(relationships) else ''}]"
                        for i in range(len(nodes))
                    ])
                    paths.append({
                        "path": path_str,
                        "length": path_length,
                        "nodes": nodes
                    })

                traversal_results[node_name] = {
                    "modality": modality,
                    "related_genes": list(related_genes),
                    "related_gene_count": len(related_genes),
                    "paths": paths[:10],  # Limit to 10 paths for readability
                    "total_paths_found": len(paths),
                    "intermediate_nodes": list(intermediate_nodes),
                    "reason": node_info.get('reason', 'Not specified'),
                    "explanation": f"Found {len(related_genes)} significant genes connected to {node_name} within {max_hops} hops"
                }

                logger.info(f"  Found {len(related_genes)} related genes, {len(paths)} paths")

            except Exception as e:
                logger.warning(f"  Error traversing {node_name}: {e}")
                traversal_results[node_name] = {
                    "modality": modality,
                    "error": str(e),
                    "reason": node_info.get('reason', 'Not specified')
                }

        logger.info(f"Network traversal complete for {len(traversal_results)} nodes")

        return {
            "success": True,
            "traversal_results": traversal_results,
            "total_nodes_traversed": len(traversal_results),
            "significant_genes_used": len(gene_ids),
            "max_hops": max_hops,
            "note": "Use these results to understand biological context of top-ranked nodes"
        }

    except Exception as e:
        logger.error(f"Network traversal error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
