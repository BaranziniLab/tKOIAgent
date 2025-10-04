"""
tKOIAgent - Transcriptomic Knowledge Organization & Integration Agent

A lightweight MCP server focused on biomedical knowledge graph queries.
Claude handles Excel parsing and analysis; the agent provides KG contextualization.

Usage: Upload Excel file to Claude, describe your study, then explore knowledge graph connections.
"""
import json
import logging
import os
import re
from typing import Any, Optional

from fastmcp.exceptions import ToolError
from fastmcp.server import FastMCP
from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import ToolAnnotations
from neo4j import GraphDatabase, Transaction
from neo4j.exceptions import ClientError, Neo4jError
from pydantic import BaseModel, Field

logger = logging.getLogger("tKOIAgent")

# Knowledge Graph Credentials
KNOWLEDGE_GRAPH_CONFIG = {
    "uri": "bolt://spokedev.cgl.ucsf.edu:7687",
    "username": "neo4j",
    "password": "SPOKEdev",
    "database": "spoke"
}


class AgentState(BaseModel):
    """Minimal agent state - just tracks if study is described"""
    study_described: bool = False
    study_description: str = ""


def _read_knowledge_graph(tx: Transaction, cypher_query: str, params: dict[str, Any]) -> str:
    """Execute read-only knowledge graph transaction"""
    raw_results = tx.run(cypher_query, params)
    eager_results = raw_results.to_eager_result()
    return json.dumps([r.data() for r in eager_results.records], default=str)


def _is_write_query(query: str) -> bool:
    """Check if query contains write operations"""
    return re.search(
        r"\b(MERGE|CREATE|SET|DELETE|REMOVE|ADD|INSERT|UPDATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|SP_)\b",
        query,
        re.IGNORECASE
    ) is not None


def create_tkoi_agent() -> FastMCP:
    """Create tKOI agent - a minimal knowledge graph query interface"""
    
    logging.basicConfig(level=logging.INFO)
    
    mcp = FastMCP(
        "tKOIAgent",
        dependencies=["neo4j", "pydantic"]
    )
    
    # Initialize knowledge graph connection
    try:
        kg_driver = GraphDatabase.driver(
            KNOWLEDGE_GRAPH_CONFIG["uri"],
            auth=(KNOWLEDGE_GRAPH_CONFIG["username"], KNOWLEDGE_GRAPH_CONFIG["password"])
        )
        logger.info(f"Connected to knowledge graph: {KNOWLEDGE_GRAPH_CONFIG['uri']}")
    except Exception as e:
        logger.error(f"Failed to connect to knowledge graph: {e}")
        raise ToolError(f"Knowledge graph connection failed: {e}")
    
    # Minimal state - just study description
    agent_state = AgentState()
    
    @mcp.tool(
        name="describe_study",
        annotations=ToolAnnotations(
            title="Describe RNAseq Study",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False
        )
    )
    def describe_study(
        study_description: str = Field(
            ..., 
            description="Detailed description of the RNAseq study: objectives, biological context, experimental conditions, and research questions"
        )
    ) -> ToolResult:
        """
        REQUIRED FIRST STEP: Record the RNAseq study description before any knowledge graph queries.
        
        This context is essential for interpreting knowledge graph results.
        Include: study objectives, tissue/cell types, conditions compared, and research questions.
        
        After recording the study description, Claude should:
        1. Read and analyze the uploaded Excel file
        2. Summarize: How many significant results in each tab? Key highlights?
        3. Then begin knowledge graph contextualization using query_knowledge_graph tool
        """
        agent_state.study_described = True
        agent_state.study_description = study_description
        
        result = {
            "status": "Study description recorded",
            "description": study_description,
            "next_steps": [
                "1. Read the uploaded Excel file and extract biological processes/concepts",
                "2. Summarize the Excel data: tabs, significant results count, key highlights",
                "3. Use query_knowledge_graph to contextualize concepts from the Excel file",
                "4. Interpret knowledge graph results in context of the study description"
            ],
            "note": "You can now query the knowledge graph using the query_knowledge_graph tool"
        }
        
        return ToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    @mcp.tool(
        name="query_knowledge_graph",
        annotations=ToolAnnotations(
            title="Query Knowledge Graph",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True
        )
    )
    def query_knowledge_graph(
        cypher_query: str = Field(..., description="Cypher query to execute on the knowledge graph"),
        parameters: dict[str, Any] = Field(default_factory=dict, description="Query parameters"),
        context_note: Optional[str] = Field(None, description="Optional note about what you're exploring")
    ) -> ToolResult:
        """
        Execute a read-only Cypher query on the biomedical knowledge graph.
        
        The knowledge graph contains: Genes, Proteins, Compounds, Diseases, BiologicalProcesses (GO terms),
        Anatomy, CellTypes, Pathways, and their relationships.
        
        You decide what queries to run based on:
        - Concepts extracted from the user's Excel file
        - The study description context
        - What connections would be most informative
        
        Common query patterns:
        - Find a biological process: MATCH (bp:BiologicalProcess) WHERE toLower(bp.name) CONTAINS 'inflammation' RETURN bp
        - Get connections: MATCH (bp:BiologicalProcess)-[r]-(connected) WHERE bp.name = 'inflammatory response' RETURN type(r), labels(connected), connected.name LIMIT 50
        - Multi-hop exploration: MATCH (bp:BiologicalProcess)-[r1]-(n1)-[r2]-(n2) WHERE bp.name = 'lipid metabolism' RETURN *
        """
        if not agent_state.study_described:
            raise ToolError(
                "You must call describe_study first before querying the knowledge graph. "
                "The study context is required for meaningful interpretation of results."
            )
        
        if _is_write_query(cypher_query):
            raise ToolError("Only read queries (MATCH, RETURN, WHERE, WITH, etc.) are allowed")
        
        try:
            with kg_driver.session(database=KNOWLEDGE_GRAPH_CONFIG["database"]) as session:
                results_json_str = session.execute_read(_read_knowledge_graph, cypher_query, parameters)
                results = json.loads(results_json_str)
                
                formatted_results = {
                    "status": "Query executed successfully",
                    "study_context": agent_state.study_description,
                    "context_note": context_note if context_note else "No context provided",
                    "query": cypher_query,
                    "parameters": parameters,
                    "result_count": len(results),
                    "results": results
                }
                
                return ToolResult(content=[TextContent(
                    type="text",
                    text=json.dumps(formatted_results, indent=2)
                )])
                
        except Neo4jError as e:
            logger.error(f"Neo4j error: {e}")
            raise ToolError(f"Knowledge graph query error: {e}")
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise ToolError(f"Failed to execute knowledge graph query: {e}")

    @mcp.tool(
        name="get_knowledge_graph_schema",
        annotations=ToolAnnotations(
            title="Get Knowledge Graph Schema",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True
        )
    )
    def get_knowledge_graph_schema() -> ToolResult:
        """
        Retrieve the knowledge graph schema showing available node types,
        relationships, and properties. Useful for understanding what queries are possible.
        
        This is optional - you can query the knowledge graph without retrieving the schema if you
        already know the structure.
        """
        schema_query = "CALL apoc.meta.schema();"
        
        try:
            with kg_driver.session(database=KNOWLEDGE_GRAPH_CONFIG["database"]) as session:
                results_json_str = session.execute_read(_read_knowledge_graph, schema_query, {})
                schema_data = json.loads(results_json_str)
                
                if schema_data and len(schema_data) > 0:
                    schema = schema_data[0].get('value', {})
                    node_types = sorted(list(schema.keys()))
                    
                    result = {
                        "status": "Knowledge graph schema retrieved",
                        "node_types": node_types,
                        "node_count": len(node_types),
                        "full_schema": schema,
                        "common_node_types": [
                            "BiologicalProcess",
                            "Gene", 
                            "Protein",
                            "Compound",
                            "Disease",
                            "Anatomy",
                            "CellType",
                            "Pathway"
                        ]
                    }
                else:
                    result = {"status": "Schema retrieved but empty", "data": schema_data}
                
                return ToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])
                
        except ClientError as e:
            if "ProcedureNotFound" in str(e):
                raise ToolError("APOC plugin not installed. You can still query the knowledge graph without the schema.")
            raise ToolError(f"Knowledge graph error: {e}")
        except Exception as e:
            logger.error(f"Error retrieving schema: {e}")
            raise ToolError(f"Failed to retrieve knowledge graph schema: {e}")

    @mcp.tool(
        name="get_workflow_status",
        annotations=ToolAnnotations(
            title="Get Workflow Status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_workflow_status() -> ToolResult:
        """
        Check the current workflow status. Shows whether study has been described
        and provides guidance on next steps.
        """
        status = {
            "study_described": agent_state.study_described,
            "study_description": agent_state.study_description if agent_state.study_described else None,
            "knowledge_graph_connection": {
                "uri": KNOWLEDGE_GRAPH_CONFIG["uri"],
                "database": KNOWLEDGE_GRAPH_CONFIG["database"],
                "status": "connected"
            },
            "workflow_guidance": {
                "current_step": "Study description recorded - ready for knowledge graph queries" if agent_state.study_described else "Awaiting study description",
                "available_tools": [
                    "describe_study - REQUIRED first step",
                    "query_knowledge_graph - Main tool for knowledge graph contextualization",
                    "get_knowledge_graph_schema - Optional, to understand graph structure"
                ],
                "recommended_workflow": [
                    "1. User uploads Excel file to Claude",
                    "2. Call describe_study with study context",
                    "3. Claude reads Excel and summarizes (tabs, significant results, highlights)",
                    "4. Claude extracts concepts to contextualize",
                    "5. Claude queries knowledge graph using query_knowledge_graph with custom Cypher queries",
                    "6. Claude interprets results in context of the study"
                ]
            }
        }
        
        return ToolResult(content=[TextContent(type="text", text=json.dumps(status, indent=2))])
    
    return mcp


def main() -> None:
    """Main entry point for tKOIAgent"""
    
    logger.info("=" * 70)
    logger.info("tKOIAgent - Knowledge Graph Query Interface")
    logger.info("=" * 70)
    logger.info(f"Knowledge Graph: {KNOWLEDGE_GRAPH_CONFIG['uri']} (database: {KNOWLEDGE_GRAPH_CONFIG['database']})")
    logger.info("")
    logger.info("AGENT DESIGN:")
    logger.info("  - Lightweight KG query interface")
    logger.info("  - Claude handles Excel reading and analysis")
    logger.info("  - Agent enforces study description before queries")
    logger.info("  - Claude decides what/how to query based on data")
    logger.info("")
    logger.info("WORKFLOW:")
    logger.info("  1. User uploads Excel to Claude")
    logger.info("  2. REQUIRED: describe_study (enforced)")
    logger.info("  3. Claude reads Excel and summarizes results")
    logger.info("  4. Claude queries knowledge graph using query_knowledge_graph")
    logger.info("  5. Claude interprets in study context")
    logger.info("")
    logger.info("Ready for contextualization!")
    logger.info("=" * 70)
    
    mcp = create_tkoi_agent()
    mcp.run()


if __name__ == "__main__":
    main()

