"""
Neo4j client for SPOKE knowledge graph integration.

Provides read-only access to the SPOKE biomedical knowledge graph.
"""

from neo4j import GraphDatabase, READ_ACCESS
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import pandas as pd
from utils.logger import get_logger
from config import config

logger = get_logger(__name__)


class SpokeClient:
    """Read-only client for SPOKE Neo4j knowledge graph"""

    def __init__(self):
        self.uri = config.spoke.uri
        self.username = config.spoke.username
        self.password = config.spoke.password

        # Initialize driver with connection pooling
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=config.spoke.max_connection_pool_size,
                connection_timeout=config.spoke.connection_timeout,
                max_transaction_retry_time=config.spoke.max_transaction_retry_time
            )
            logger.info(f"Connected to SPOKE at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to SPOKE: {e}")
            self.driver = None

    def close(self):
        """Close driver and release connections"""
        if self.driver:
            self.driver.close()
            logger.info("SPOKE connection closed")

    @contextmanager
    def session(self):
        """Context manager for read-only sessions"""
        if not self.driver:
            raise RuntimeError("SPOKE driver not initialized")

        session = self.driver.session(default_access_mode=READ_ACCESS)
        try:
            yield session
        finally:
            session.close()

    def validate_query(self, cypher_query: str) -> bool:
        """
        Validate that query is read-only (no mutations).

        Args:
            cypher_query: Cypher query string

        Returns:
            True if read-only, False if contains mutations
        """
        # Check for mutation keywords
        mutation_keywords = [
            "CREATE", "DELETE", "DETACH DELETE",
            "MERGE", "SET", "REMOVE",
            "DROP", "ALTER"
        ]

        query_upper = cypher_query.upper()
        for keyword in mutation_keywords:
            if keyword in query_upper:
                logger.warning(f"Query contains mutation keyword: {keyword}")
                return False

        return True

    def execute_query(
        self,
        cypher_query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute custom read-only Cypher query.

        Args:
            cypher_query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records

        Raises:
            ValueError: If query contains mutation operations
            RuntimeError: If driver not initialized
        """
        if not self.validate_query(cypher_query):
            raise ValueError("Only read-only queries are allowed")

        logger.info("Executing custom Cypher query")

        try:
            with self.session() as session:
                result = session.run(cypher_query, parameters or {})
                records = [dict(record) for record in result]

            logger.info(f"Query returned {len(records)} records")
            return records
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def query_genes(
        self,
        gene_ids: List[str],
        relationship_types: Optional[List[str]] = None,
        max_depth: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Query SPOKE for gene information and relationships.

        Args:
            gene_ids: List of gene identifiers (Ensembl IDs)
            relationship_types: Filter by specific relationship types
            max_depth: Maximum traversal depth (1-3 recommended)

        Returns:
            List of result dictionaries
        """
        logger.info(f"Querying SPOKE for {len(gene_ids)} genes")

        # Build Cypher query
        if relationship_types:
            rel_filter = "|".join(relationship_types)
            query = f"""
            MATCH (g:Gene)
            WHERE g.identifier IN $gene_ids
            OPTIONAL MATCH path = (g)-[r:{rel_filter}*1..{max_depth}]-(related)
            RETURN g, path, related
            LIMIT 10000
            """
        else:
            query = f"""
            MATCH (g:Gene)
            WHERE g.identifier IN $gene_ids
            OPTIONAL MATCH path = (g)-[r*1..{max_depth}]-(related)
            RETURN g, path, related
            LIMIT 10000
            """

        try:
            with self.session() as session:
                result = session.run(query, gene_ids=gene_ids)
                records = [record.data() for record in result]

            logger.info(f"Retrieved {len(records)} records from SPOKE")
            return records
        except Exception as e:
            logger.error(f"Gene query failed: {e}")
            return []

    def extract_subnetwork(
        self,
        gene_ids: List[str],
        node_types: Optional[List[str]] = None,
        edge_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract subnetwork around specified genes.

        Args:
            gene_ids: Central gene identifiers
            node_types: Filter connected nodes by type (e.g., Disease, Compound)
            edge_types: Filter edges by type

        Returns:
            Dictionary with nodes and edges for network visualization
        """
        logger.info(f"Extracting subnetwork for {len(gene_ids)} genes")

        # Build type filters
        node_filter = ""
        if node_types:
            labels = "|".join(node_types)
            node_filter = f":{labels}"

        edge_filter = ""
        if edge_types:
            edge_filter = f":{' |'.join(edge_types)}"

        query = f"""
        MATCH (g:Gene)
        WHERE g.identifier IN $gene_ids
        MATCH path = (g)-[r{edge_filter}]-(n{node_filter})
        WITH g, r, n, path
        RETURN
            collect(DISTINCT {{
                id: id(g),
                labels: labels(g),
                properties: properties(g)
            }}) as source_nodes,
            collect(DISTINCT {{
                id: id(n),
                labels: labels(n),
                properties: properties(n)
            }}) as connected_nodes,
            collect(DISTINCT {{
                source: id(g),
                target: id(n),
                type: type(r),
                properties: properties(r)
            }}) as edges
        """

        try:
            with self.session() as session:
                result = session.run(query, gene_ids=gene_ids)
                record = result.single()

            if not record:
                return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}

            # Combine source and connected nodes
            all_nodes = record['source_nodes'] + record['connected_nodes']
            edges = record['edges']

            subnetwork = {
                "nodes": all_nodes,
                "edges": edges,
                "stats": {
                    "total_nodes": len(all_nodes),
                    "total_edges": len(edges),
                    "gene_nodes": len(record['source_nodes'])
                }
            }

            logger.info(f"Extracted subnetwork: {subnetwork['stats']}")
            return subnetwork
        except Exception as e:
            logger.error(f"Subnetwork extraction failed: {e}")
            return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}

    def get_gene_diseases(self, gene_ids: List[str]) -> pd.DataFrame:
        """
        Query gene-disease associations.

        Args:
            gene_ids: List of gene IDs

        Returns:
            DataFrame with gene-disease associations
        """
        query = """
        MATCH (g:Gene)-[r:ASSOCIATES_WITH]-(d:Disease)
        WHERE g.identifier IN $gene_ids
        RETURN
            g.identifier as gene_id,
            g.name as gene_name,
            d.identifier as disease_id,
            d.name as disease_name,
            r.source as evidence_source
        """

        try:
            with self.session() as session:
                result = session.run(query, gene_ids=gene_ids)
                records = [dict(record) for record in result]

            return pd.DataFrame(records)
        except Exception as e:
            logger.error(f"Gene-disease query failed: {e}")
            return pd.DataFrame()
