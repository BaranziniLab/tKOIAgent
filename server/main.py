#!/usr/bin/env python3
"""
tKOIAgent: Transcriptomics Knowledge Graph–Driven Omics Integration Agent
MCP Server for R-based transcriptomics analysis and Neo4j biological knowledge graph querying

Purpose: Analyze transcriptomics/gene expression data, perform network propagation using tKOI,
         and contextualize results using the SPOKE biological knowledge graph.

Requirements: Python 3.12+, MCP SDK, R runtime (Rscript in PATH), Neo4j Python driver

Tools Overview:
  R Toolchain (Toolchain A):
    - set_workdir: Set working directory for all operations
    - get_state: Get current server state
    - create_R_file: Create new R script files
    - write_R_code: Write R code to files
    - append_R_code: Append R code to existing files
    - run_R_script: Execute R scripts (supports long-running tKOI analysis)
    - run_R_expression: Execute single R expressions
    - list_exports: List files in working directory
    - read_export: Read file contents
    - preview_table: Preview CSV/TSV data
    - inspect_R_objects: Inspect R objects from saved session
    - ggplot_style_check: Check ggplot2 code for publication quality
    - which_R: Find R executable
    - list_R_files: List R script files
    - set_primary_file: Set primary R script

  Knowledge Graph Toolchain (Toolchain B):
    - get_knowledge_graph_schema: Get SPOKE schema (nodes, relationships, properties)
    - query_knowledge_graph: Execute custom Cypher queries
    - search_nodes: Search for nodes by name/identifier
    - get_node_neighbors: Get connected nodes
    - get_path_between_nodes: Find paths between nodes
    - get_gene_pathways: Get pathways for genes
    - get_gene_disease_associations: Get disease associations for genes
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import base64
import csv
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
from enum import Enum

# Load environment variables from .env file before anything else
from dotenv import load_dotenv

def load_environment():
    """Load environment variables from .env file.
    
    Searches for .env file in the following order:
    1. Current working directory
    2. Directory containing this script
    3. Parent directory of this script
    """
    # Try current working directory first
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        return str(env_path)
    
    # Try script directory
    script_dir = Path(__file__).parent.resolve()
    env_path = script_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        return str(env_path)
    
    # Try parent of script directory
    env_path = script_dir.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        return str(env_path)
    
    # Try default dotenv loading (searches up directory tree)
    load_dotenv()
    return None

# Load .env file immediately
_env_file_loaded = load_environment()

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError, CypherSyntaxError

# Configure logging (after dotenv is loaded so LOG_LEVEL can be read from .env)
logging.basicConfig(
    level=os.environ.get("TKOIAGENT_LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Log which .env file was loaded
if _env_file_loaded:
    logger.info(f"Loaded environment from: {_env_file_loaded}")
else:
    logger.info("No .env file found, using system environment variables")


def print_ascii_banner():
    """Print ASCII art banner with current date/time and configuration status."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kg_uri = os.environ.get("KNOWLEDGE_GRAPH_URI", "not configured")
    kg_db = os.environ.get("KNOWLEDGE_GRAPH_DATABASE", "not configured")
    kg_configured = "✓" if os.environ.get("KNOWLEDGE_GRAPH_PASSWORD") else "✗"
    
    banner = f"""
╔════════════════════════════════════════════════════════════════════╗

    tKOIAgent - Transcriptomics Knowledge Graph Omics Integration
    MCP Server for R Script Management & SPOKE Knowledge Graph
    Author: Wanjun Gu (wanjun.gu@ucsf.edu)
    Started: {current_time}

    Configuration:
    - Knowledge Graph URI: {kg_uri}
    - Knowledge Graph DB:  {kg_db}
    - KG Credentials:      {kg_configured}

╚════════════════════════════════════════════════════════════════════╝
"""
    logger.info(banner)


# =============================================================================
# Environment Configuration
# =============================================================================

KNOWLEDGE_GRAPH_URI = os.environ.get("KNOWLEDGE_GRAPH_URI", "bolt://spokedev.cgl.ucsf.edu:7687")
KNOWLEDGE_GRAPH_USERNAME = os.environ.get("KNOWLEDGE_GRAPH_USERNAME", "neo4j")
KNOWLEDGE_GRAPH_PASSWORD = os.environ.get("KNOWLEDGE_GRAPH_PASSWORD", "")
KNOWLEDGE_GRAPH_DATABASE = os.environ.get("KNOWLEDGE_GRAPH_DATABASE", "spoke")
TKOIAGENT_NAMESPACE = os.environ.get("TKOIAGENT_NAMESPACE", "tKOIAgent")


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


GGPLOT_STYLE_GUIDE = """
# ggplot Style Guide - Publication-Quality Plots

## Core Principles:
1. Use = instead of <- for assignment
2. Use theme_minimal() or theme_classic() with base_size=14
3. Use muted color palettes (Set2 for categorical, viridis for continuous)
4. Optimize dimensions to 5x4 inches (width x height)
5. Set base font size >= 14pt
6. Use size >= 2.5 for points, linewidth >= 0.8 for lines
7. Export with dpi=800

## Example:
```r
library(ggplot2)
p = ggplot(data, aes(x=x_var, y=y_var, color=group)) +
  geom_point(size=2.5, alpha=0.8) +
  scale_color_brewer(palette="Set2") +
  theme_minimal(base_size=14) +
  labs(x="X Label", y="Y Label", title="Title")
ggsave("plot.png", p, width=5, height=4, dpi=800)
```
"""


# =============================================================================
# Pydantic Input Models - R Toolchain
# =============================================================================

class SetWorkdirInput(BaseModel):
    """Input model for setting the working directory."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    path: str = Field(..., description="Absolute or relative path to the working directory", min_length=1)
    create: bool = Field(default=True, description="Create the directory if it doesn't exist")


class CreateRFileInput(BaseModel):
    """Input model for creating a new R script file."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    filename: str = Field(..., description="Name of the R script file to create", min_length=1, max_length=255)
    overwrite: bool = Field(default=False, description="Overwrite the file if it already exists")
    scaffold: bool = Field(default=False, description="Include a basic R scaffold template")


class WriteRCodeInput(BaseModel):
    """Input model for writing R code to a file."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    code: str = Field(..., description="The R code to write to the file", min_length=1)
    filename: Optional[str] = Field(default=None, description="Target filename (uses primary file if not specified)")
    overwrite: bool = Field(default=False, description="Overwrite existing file content")


class AppendRCodeInput(BaseModel):
    """Input model for appending R code to an existing file."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    code: str = Field(..., description="The R code to append to the file", min_length=1)
    filename: Optional[str] = Field(default=None, description="Target filename (uses primary file if not specified)")


class RunRScriptInput(BaseModel):
    """Input model for executing an R script."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    filename: Optional[str] = Field(default=None, description="R script filename to execute")
    args: Optional[List[str]] = Field(default=None, description="Command-line arguments to pass to the script")
    timeout_sec: int = Field(default=3600, description="Maximum execution time in seconds (default 1 hour)", ge=10, le=86400)
    save_rdata: bool = Field(default=True, description="Save R workspace after execution")


class RunRExpressionInput(BaseModel):
    """Input model for executing a single R expression."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    expr: str = Field(..., description="R expression to execute", min_length=1)
    timeout_sec: int = Field(default=120, description="Maximum execution time in seconds", ge=5, le=3600)


class ListExportsInput(BaseModel):
    """Input model for listing files in the working directory."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    glob: str = Field(default="*", description="Glob pattern to filter files")
    sort_by: str = Field(default="mtime", description="Sort by: 'mtime', 'size', or 'name'")
    descending: bool = Field(default=True, description="Sort in descending order")
    limit: int = Field(default=100, description="Maximum number of files to return", ge=1, le=500)


class ReadExportInput(BaseModel):
    """Input model for reading a file from the working directory."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    name: str = Field(..., description="Filename to read", min_length=1)
    max_bytes: int = Field(default=100000, description="Maximum file size to read in bytes", ge=1000, le=10000000)
    as_text: bool = Field(default=True, description="Read as text or binary base64")
    encoding: str = Field(default="utf-8", description="Text encoding for text files")


class PreviewTableInput(BaseModel):
    """Input model for previewing tabular data files."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    name: str = Field(..., description="CSV/TSV filename to preview", min_length=1)
    delimiter: str = Field(default=",", description="Column delimiter")
    max_rows: int = Field(default=50, description="Maximum number of rows to preview", ge=1, le=1000)


class InspectRObjectsInput(BaseModel):
    """Input model for inspecting R objects from saved session."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    objects: Optional[List[str]] = Field(default=None, description="Specific object names to inspect")
    str_max_level: int = Field(default=2, description="Maximum nesting level for str() output", ge=1, le=5)
    timeout_sec: int = Field(default=120, description="Maximum execution time in seconds", ge=10, le=600)


class GgplotStyleCheckInput(BaseModel):
    """Input model for analyzing ggplot code quality."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    code: str = Field(..., description="R/ggplot2 code to analyze", min_length=1)


class SetPrimaryFileInput(BaseModel):
    """Input model for setting the primary R script file."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    filename: str = Field(..., description="Filename to set as primary R script", min_length=1, max_length=255)


# =============================================================================
# Pydantic Input Models - Knowledge Graph Toolchain
# =============================================================================

class GetKnowledgeGraphSchemaInput(BaseModel):
    """Input model for retrieving knowledge graph schema."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    include_properties: bool = Field(default=True, description="Include node and relationship properties")
    include_counts: bool = Field(default=False, description="Include node counts (slower)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class QueryKnowledgeGraphInput(BaseModel):
    """Input model for executing Cypher queries on the knowledge graph."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    query: str = Field(..., description="Cypher query to execute (READ-ONLY)", min_length=5)
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    limit: int = Field(default=100, description="Maximum number of results", ge=1, le=10000)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Output format")
    
    @field_validator('query')
    @classmethod
    def validate_read_only(cls, v: str) -> str:
        """Ensure query is read-only."""
        write_keywords = ['CREATE', 'DELETE', 'SET', 'MERGE', 'REMOVE', 'DROP', 'DETACH']
        query_upper = v.upper()
        for keyword in write_keywords:
            if keyword in query_upper:
                raise ValueError(f"Write operations ({keyword}) are not allowed.")
        return v


class SearchNodesInput(BaseModel):
    """Input model for searching nodes in the knowledge graph."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    search_term: str = Field(..., description="Term to search for", min_length=2)
    node_types: Optional[List[str]] = Field(default=None, description="Limit search to specific node types")
    limit: int = Field(default=25, description="Maximum number of results", ge=1, le=100)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetNodeNeighborsInput(BaseModel):
    """Input model for retrieving neighbors of a node."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    node_id: str = Field(..., description="Node identifier", min_length=1)
    node_type: Optional[str] = Field(default=None, description="Node type/label")
    relationship_types: Optional[List[str]] = Field(default=None, description="Filter by relationship types")
    direction: str = Field(default="both", description="Relationship direction: 'outgoing', 'incoming', or 'both'")
    limit: int = Field(default=50, description="Maximum number of neighbors", ge=1, le=500)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetPathBetweenNodesInput(BaseModel):
    """Input model for finding paths between two nodes."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    source_id: str = Field(..., description="Source node identifier", min_length=1)
    target_id: str = Field(..., description="Target node identifier", min_length=1)
    source_type: Optional[str] = Field(default=None, description="Source node type")
    target_type: Optional[str] = Field(default=None, description="Target node type")
    max_hops: int = Field(default=3, description="Maximum path length", ge=1, le=5)
    limit: int = Field(default=10, description="Maximum number of paths", ge=1, le=50)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetGenePathwaysInput(BaseModel):
    """Input model for retrieving pathways associated with genes."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    gene_ids: List[str] = Field(..., description="List of gene identifiers (Ensembl IDs)", min_length=1, max_length=100)
    include_shared: bool = Field(default=True, description="Include pathways shared by multiple genes")
    limit: int = Field(default=50, description="Maximum pathways per gene", ge=1, le=200)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetGeneDiseaseAssociationsInput(BaseModel):
    """Input model for retrieving disease associations for genes."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    gene_ids: List[str] = Field(..., description="List of gene identifiers", min_length=1, max_length=100)
    limit: int = Field(default=50, description="Maximum associations per gene", ge=1, le=200)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


# =============================================================================
# tKOIAgent Server Class
# =============================================================================

class TKOIAgentServer:
    """Main server class managing R execution and Neo4j connections."""
    
    def __init__(self):
        self.state_dir: Optional[Path] = None
        self.state_file: Optional[Path] = None
        self.workdir: Optional[Path] = None
        self.primary_file: str = "agent.R"
        self._neo4j_driver = None
    
    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file."""
        if not self.state_file or not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return {}
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state to JSON file."""
        if not self.state_file:
            return
        temp_file = self.state_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            temp_file.replace(self.state_file)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            if temp_file.exists():
                temp_file.unlink()
    
    def ensure_workdir_set(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if workdir is set and valid."""
        if not self.workdir:
            return False, {"code": "NO_WORKDIR", "message": "Working directory not set. Use set_workdir first."}
        if not self.workdir.exists():
            return False, {"code": "WORKDIR_MISSING", "message": f"Working directory {self.workdir} no longer exists"}
        return True, None
    
    def is_safe_path(self, path: Path) -> bool:
        """Check if path is within workdir."""
        if not self.workdir:
            return False
        try:
            return path.resolve().is_relative_to(self.workdir)
        except (ValueError, RuntimeError):
            return False
    
    def find_r_executable(self) -> Optional[str]:
        """Find R executable."""
        return shutil.which("Rscript") or shutil.which("R")
    
    def run_r_command(self, args: List[str], timeout: int = 120) -> Dict[str, Any]:
        """Execute R command and capture output."""
        r_exe = self.find_r_executable()
        if not r_exe:
            return {"ok": False, "error": {"code": "R_NOT_FOUND", "message": "Rscript not found in PATH"}}
        
        try:
            original_cwd = os.getcwd()
            if self.workdir:
                os.chdir(self.workdir)
            
            result = subprocess.run([r_exe] + args, capture_output=True, text=True, timeout=timeout, check=False)
            os.chdir(original_cwd)
            
            stdout_lines = [l for l in result.stdout.strip().split('\n') if l] if result.stdout else []
            stderr_lines = [l for l in result.stderr.strip().split('\n') if l and "no visible binding" not in l] if result.stderr else []
            
            if result.returncode != 0:
                return {"ok": False, "error": {"code": "R_EXECUTION_ERROR", "message": f"R failed with code {result.returncode}", "details": {"stdout": stdout_lines[-50:], "stderr": stderr_lines[-50:]}}}
            
            return {"ok": True, "data": {"stdout": stdout_lines[-100:], "stderr": stderr_lines[-50:], "returncode": result.returncode}}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": {"code": "TIMEOUT", "message": f"R execution timed out after {timeout} seconds"}}
        except Exception as e:
            return {"ok": False, "error": {"code": "EXECUTION_ERROR", "message": str(e)}}
    
    def get_neo4j_driver(self):
        """Get or create Neo4j driver."""
        if self._neo4j_driver is None:
            if not KNOWLEDGE_GRAPH_PASSWORD:
                raise ValueError("KNOWLEDGE_GRAPH_PASSWORD environment variable is required")
            self._neo4j_driver = GraphDatabase.driver(KNOWLEDGE_GRAPH_URI, auth=(KNOWLEDGE_GRAPH_USERNAME, KNOWLEDGE_GRAPH_PASSWORD))
        return self._neo4j_driver
    
    def close_neo4j_driver(self):
        """Close Neo4j driver."""
        if self._neo4j_driver:
            self._neo4j_driver.close()
            self._neo4j_driver = None
    
    def execute_cypher(self, query: str, parameters: Optional[Dict] = None, limit: int = 100) -> Dict[str, Any]:
        """Execute a Cypher query and return results."""
        try:
            driver = self.get_neo4j_driver()
            with driver.session(database=KNOWLEDGE_GRAPH_DATABASE) as session:
                result = session.run(query, parameters or {})
                records = []
                for i, record in enumerate(result):
                    if i >= limit:
                        break
                    record_dict = {key: self._convert_neo4j_value(record[key]) for key in record.keys()}
                    records.append(record_dict)
                summary = result.consume()
                return {"ok": True, "data": {"records": records, "count": len(records), "query_time_ms": summary.result_available_after}}
        except AuthError as e:
            return {"ok": False, "error": {"code": "AUTH_ERROR", "message": "Authentication failed", "details": str(e)}}
        except ServiceUnavailable as e:
            return {"ok": False, "error": {"code": "CONNECTION_ERROR", "message": f"Cannot connect to {KNOWLEDGE_GRAPH_URI}", "details": str(e)}}
        except CypherSyntaxError as e:
            return {"ok": False, "error": {"code": "SYNTAX_ERROR", "message": "Invalid Cypher syntax", "details": str(e)}}
        except Exception as e:
            return {"ok": False, "error": {"code": "QUERY_ERROR", "message": str(e)}}
    
    def _convert_neo4j_value(self, value):
        """Convert Neo4j types to JSON-serializable Python types."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._convert_neo4j_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._convert_neo4j_value(v) for k, v in value.items()}
        if hasattr(value, 'labels') and hasattr(value, 'items'):
            return {"_type": "node", "labels": list(value.labels), "properties": dict(value.items())}
        if hasattr(value, 'type') and hasattr(value, 'start_node'):
            return {"_type": "relationship", "type": value.type, "properties": dict(value.items()) if hasattr(value, 'items') else {}}
        if hasattr(value, 'nodes') and hasattr(value, 'relationships'):
            return {"_type": "path", "nodes": [self._convert_neo4j_value(n) for n in value.nodes], "relationships": [self._convert_neo4j_value(r) for r in value.relationships]}
        return str(value)


# =============================================================================
# Initialize MCP Server
# =============================================================================

tkoiagent = TKOIAgentServer()

@asynccontextmanager
async def app_lifespan(app):
    """Manage server lifecycle."""
    print_ascii_banner()
    logger.info("tKOIAgent MCP server starting...")
    yield {"server": tkoiagent}
    tkoiagent.close_neo4j_driver()
    logger.info("tKOIAgent MCP server stopped.")

mcp = FastMCP("tkoiagent_mcp", lifespan=app_lifespan)


# =============================================================================
# R Toolchain Tools
# =============================================================================

@mcp.tool(name="set_workdir", annotations={"title": "Set Working Directory", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def set_workdir(params: SetWorkdirInput) -> str:
    """Set the working directory for all R operations and file management.
    
    This should be the directory containing the user's transcriptomics data file.
    All generated files (clean_data.R, run_tkoi.R, outputs) will be created here.
    """
    try:
        workdir = Path(params.path).expanduser().resolve()
        if not workdir.exists():
            if params.create:
                workdir.mkdir(parents=True, exist_ok=True)
            else:
                return json.dumps({"ok": False, "error": {"code": "DIR_NOT_FOUND", "message": f"Directory {params.path} does not exist"}}, indent=2)
        elif not workdir.is_dir():
            return json.dumps({"ok": False, "error": {"code": "NOT_A_DIR", "message": f"Path {params.path} is not a directory"}}, indent=2)
        
        tkoiagent.workdir = workdir
        tkoiagent.state_dir = workdir / ".tkoiagent"
        tkoiagent.state_dir.mkdir(exist_ok=True)
        tkoiagent.state_file = tkoiagent.state_dir / "state.json"
        
        state = tkoiagent.load_state()
        state.update({"workdir": str(tkoiagent.workdir), "primary_file": tkoiagent.primary_file, "updated_at": datetime.now().isoformat()})
        tkoiagent.save_state(state)
        
        return json.dumps({"ok": True, "data": {"workdir": str(tkoiagent.workdir), "state_dir": str(tkoiagent.state_dir), "primary_file": tkoiagent.primary_file}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "SET_DIR_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="get_state", annotations={"title": "Get Current State", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def get_state() -> str:
    """Get current tKOIAgent state including workdir, R availability, and Neo4j configuration."""
    state = tkoiagent.load_state() if tkoiagent.state_file else {}
    state.update({"workdir": str(tkoiagent.workdir) if tkoiagent.workdir else None, "primary_file": tkoiagent.primary_file, "r_available": tkoiagent.find_r_executable() is not None, "neo4j_configured": bool(KNOWLEDGE_GRAPH_PASSWORD)})
    return json.dumps({"ok": True, "data": state}, indent=2)


@mcp.tool(name="create_R_file", annotations={"title": "Create R Script File", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def create_R_file(params: CreateRFileInput) -> str:
    """Create a new R script file in the working directory (e.g., clean_data.R, run_tkoi.R)."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filename = params.filename if params.filename.endswith(('.R', '.r')) else params.filename + '.R'
    filepath = tkoiagent.workdir / filename
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if filepath.exists() and not params.overwrite:
        return json.dumps({"ok": False, "error": {"code": "FILE_EXISTS", "message": f"File {filename} already exists"}}, indent=2)
    
    try:
        scaffold = f"# tKOIAgent R Script\n# Generated: {datetime.now().isoformat()}\n\n" if params.scaffold else ""
        filepath.write_text(scaffold)
        
        state = tkoiagent.load_state()
        state.setdefault("files", [])
        if filename not in state["files"]:
            state["files"].append(filename)
        state["updated_at"] = datetime.now().isoformat()
        tkoiagent.save_state(state)
        
        return json.dumps({"ok": True, "data": {"filename": filename, "filepath": str(filepath)}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "CREATE_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="write_R_code", annotations={"title": "Write R Code to File", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def write_R_code(params: WriteRCodeInput) -> str:
    """Write R code to a script file (replaces existing content)."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filename = params.filename or tkoiagent.primary_file
    filename = filename if filename.endswith(('.R', '.r')) else filename + '.R'
    filepath = tkoiagent.workdir / filename
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if filepath.exists() and not params.overwrite:
        return json.dumps({"ok": False, "error": {"code": "FILE_EXISTS", "message": f"File {filename} exists. Set overwrite=true"}}, indent=2)
    
    try:
        content = params.code if params.code.endswith('\n') else params.code + '\n'
        filepath.write_text(content)
        
        state = tkoiagent.load_state()
        state.setdefault("files", [])
        if filename not in state["files"]:
            state["files"].append(filename)
        state["updated_at"] = datetime.now().isoformat()
        tkoiagent.save_state(state)
        
        return json.dumps({"ok": True, "data": {"filename": filename, "lines_written": len(content.splitlines())}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "WRITE_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="append_R_code", annotations={"title": "Append R Code to File", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def append_R_code(params: AppendRCodeInput) -> str:
    """Append R code to an existing script file."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filename = params.filename or tkoiagent.primary_file
    filename = filename if filename.endswith(('.R', '.r')) else filename + '.R'
    filepath = tkoiagent.workdir / filename
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {filename} does not exist"}}, indent=2)
    
    try:
        existing = filepath.read_text()
        code = params.code if params.code.endswith('\n') else params.code + '\n'
        existing = existing if existing.endswith('\n') else existing + '\n'
        filepath.write_text(existing + code)
        
        return json.dumps({"ok": True, "data": {"filename": filename, "lines_appended": len(params.code.splitlines())}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "APPEND_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="run_R_script", annotations={"title": "Execute R Script", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def run_R_script(params: RunRScriptInput) -> str:
    """Execute an R script file. IMPORTANT: tKOI analysis can take 30-60 minutes. Use timeout_sec=3600."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filename = params.filename or tkoiagent.primary_file
    filename = filename if filename.endswith(('.R', '.r')) else filename + '.R'
    filepath = tkoiagent.workdir / filename
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"Script {filename} does not exist"}}, indent=2)
    
    cmd_args = ["--save" if params.save_rdata else "--no-save", str(filepath)]
    if params.args:
        cmd_args.extend(params.args)
    
    result = tkoiagent.run_r_command(cmd_args, timeout=params.timeout_sec)
    if result["ok"]:
        result["data"]["filename"] = filename
    return json.dumps(result, indent=2)


@mcp.tool(name="run_R_expression", annotations={"title": "Execute R Expression", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def run_R_expression(params: RunRExpressionInput) -> str:
    """Execute a single R expression for quick checks."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    result = tkoiagent.run_r_command(["-e", params.expr, "--slave"], timeout=params.timeout_sec)
    if result["ok"]:
        result["data"]["expression"] = params.expr[:100] + "..." if len(params.expr) > 100 else params.expr
    return json.dumps(result, indent=2)


@mcp.tool(name="list_exports", annotations={"title": "List Files in Working Directory", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def list_exports(params: ListExportsInput) -> str:
    """List files in the working directory with filtering and sorting."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    try:
        files = []
        for item in tkoiagent.workdir.glob(params.glob):
            if item.is_file():
                stat = item.stat()
                files.append({"name": item.name, "size": stat.st_size, "mtime": stat.st_mtime, "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"), "extension": item.suffix})
        
        if params.sort_by == "mtime":
            files.sort(key=lambda x: x["mtime"], reverse=params.descending)
        elif params.sort_by == "size":
            files.sort(key=lambda x: x["size"], reverse=params.descending)
        else:
            files.sort(key=lambda x: x["name"], reverse=not params.descending)
        
        return json.dumps({"ok": True, "data": {"files": files[:params.limit], "count": len(files[:params.limit])}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "LIST_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="read_export", annotations={"title": "Read File Content", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def read_export(params: ReadExportInput) -> str:
    """Read content of a file from the working directory."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filepath = tkoiagent.workdir / params.name
    if not tkoiagent.is_safe_path(filepath) or not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {params.name} not found"}}, indent=2)
    
    try:
        file_size = filepath.stat().st_size
        if file_size > params.max_bytes:
            return json.dumps({"ok": False, "error": {"code": "FILE_TOO_LARGE", "message": f"File size ({file_size}) exceeds max ({params.max_bytes})"}}, indent=2)
        
        if params.as_text:
            content = filepath.read_text(encoding=params.encoding)
            return json.dumps({"ok": True, "data": {"content": content, "filename": params.name, "size": file_size, "lines": len(content.splitlines())}}, indent=2)
        else:
            content_b64 = base64.b64encode(filepath.read_bytes()).decode('ascii')
            return json.dumps({"ok": True, "data": {"content_base64": content_b64, "filename": params.name, "size": file_size}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "READ_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="preview_table", annotations={"title": "Preview Tabular Data", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def preview_table(params: PreviewTableInput) -> str:
    """Preview a CSV/TSV file as structured tabular data."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filepath = tkoiagent.workdir / params.name
    if not tkoiagent.is_safe_path(filepath) or not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {params.name} not found"}}, indent=2)
    
    try:
        rows = []
        delimiter = "\t" if params.delimiter in ["\\t", "tab"] else params.delimiter
        
        with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
            if delimiter == "auto":
                sample = csvfile.read(1024)
                csvfile.seek(0)
                delimiter = csv.Sniffer().sniff(sample).delimiter
            
            reader = csv.reader(csvfile, delimiter=delimiter)
            header = next(reader, None)
            if not header:
                return json.dumps({"ok": False, "error": {"code": "EMPTY_FILE", "message": "File is empty"}}, indent=2)
            
            total_rows = 0
            for row in reader:
                total_rows += 1
                if len(rows) < params.max_rows:
                    rows.append(row)
        
        return json.dumps({"ok": True, "data": {"header": header, "rows": rows, "total_rows": total_rows, "displayed_rows": len(rows), "truncated": total_rows > params.max_rows}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "PREVIEW_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="inspect_R_objects", annotations={"title": "Inspect R Objects from Session", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def inspect_R_objects(params: InspectRObjectsInput) -> str:
    """Inspect R objects from the saved .RData workspace."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    rdata_file = tkoiagent.workdir / ".RData"
    if not rdata_file.exists():
        return json.dumps({"ok": False, "error": {"code": "NO_RDATA", "message": "No .RData file found"}}, indent=2)
    
    r_code = 'load(".RData"); all_objects = ls(); '
    if params.objects:
        obj_list = ', '.join([f'"{o}"' for o in params.objects])
        r_code += f'objects_to_inspect = intersect(c({obj_list}), all_objects); '
    else:
        r_code += 'objects_to_inspect = all_objects; '
    
    r_code += f'''for (obj_name in objects_to_inspect) {{ cat("\\n=== ", obj_name, " ===\\n"); obj = get(obj_name); cat("Class:", paste(class(obj), collapse=", "), "\\n"); if (is.data.frame(obj)) cat("Dim:", nrow(obj), "x", ncol(obj), "\\n"); str(obj, max.level={params.str_max_level}); }}'''
    
    result = tkoiagent.run_r_command(["-e", r_code, "--slave"], timeout=params.timeout_sec)
    if result["ok"]:
        result["data"]["objects_inspected"] = params.objects or "all"
    return json.dumps(result, indent=2)


@mcp.tool(name="ggplot_style_check", annotations={"title": "Check ggplot2 Code Style", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def ggplot_style_check(params: GgplotStyleCheckInput) -> str:
    """Analyze ggplot2 code and suggest publication-quality style improvements."""
    optimizations = []
    optimized_code = params.code
    
    if "<-" in params.code:
        optimizations.append("Replace '<-' with '='")
        optimized_code = optimized_code.replace("<-", "=")
    if "theme_gray()" in params.code or "theme_grey()" in params.code:
        optimizations.append("Replace theme_gray() with theme_minimal(base_size=14)")
        optimized_code = optimized_code.replace("theme_gray()", "theme_minimal(base_size=14)").replace("theme_grey()", "theme_minimal(base_size=14)")
    if "ggsave(" in params.code and "dpi=" not in params.code:
        optimizations.append("Add dpi=800 to ggsave()")
    if "geom_point(" in params.code and "size=" not in params.code:
        optimizations.append("Set size=2.5 in geom_point()")
    
    return json.dumps({"ok": True, "data": {"original_code": params.code, "optimized_code": optimized_code, "optimizations": optimizations}}, indent=2)


@mcp.tool(name="which_R", annotations={"title": "Find R Executable", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def which_R() -> str:
    """Find R/Rscript executable in the system PATH."""
    exe = tkoiagent.find_r_executable()
    if exe:
        return json.dumps({"ok": True, "data": {"executable": exe}}, indent=2)
    return json.dumps({"ok": False, "error": {"code": "R_NOT_FOUND", "message": "R not found in PATH"}}, indent=2)


@mcp.tool(name="list_R_files", annotations={"title": "List R Script Files", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def list_R_files() -> str:
    """List all R script files in the working directory."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    r_files = sorted(set(item.name for pattern in ["*.R", "*.r"] for item in tkoiagent.workdir.glob(pattern) if item.is_file()))
    return json.dumps({"ok": True, "data": {"files": r_files, "primary_file": tkoiagent.primary_file}}, indent=2)


@mcp.tool(name="set_primary_file", annotations={"title": "Set Primary R Script", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def set_primary_file(params: SetPrimaryFileInput) -> str:
    """Set the primary R script file used by default for operations."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filename = params.filename if params.filename.endswith(('.R', '.r')) else params.filename + '.R'
    if not (tkoiagent.workdir / filename).exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {filename} does not exist"}}, indent=2)
    
    tkoiagent.primary_file = filename
    state = tkoiagent.load_state()
    state["primary_file"] = filename
    state["updated_at"] = datetime.now().isoformat()
    tkoiagent.save_state(state)
    
    return json.dumps({"ok": True, "data": {"primary_file": filename}}, indent=2)


# =============================================================================
# Knowledge Graph Toolchain Tools
# =============================================================================

@mcp.tool(name="get_knowledge_graph_schema", annotations={"title": "Get SPOKE Knowledge Graph Schema", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def get_knowledge_graph_schema(params: GetKnowledgeGraphSchemaInput) -> str:
    """Retrieve the schema of the SPOKE biomedical knowledge graph.
    
    Lists all node types (Gene, Disease, Pathway, etc.), relationship types, and properties.
    Essential for understanding available data before querying.
    """
    try:
        labels_result = tkoiagent.execute_cypher("CALL db.labels() YIELD label RETURN label ORDER BY label", limit=200)
        if not labels_result["ok"]:
            return json.dumps(labels_result, indent=2)
        node_labels = [r["label"] for r in labels_result["data"]["records"]]
        
        rel_result = tkoiagent.execute_cypher("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType", limit=500)
        if not rel_result["ok"]:
            return json.dumps(rel_result, indent=2)
        rel_types = [r["relationshipType"] for r in rel_result["data"]["records"]]
        
        schema = {"node_labels": node_labels, "relationship_types": rel_types, "node_count": len(node_labels), "relationship_type_count": len(rel_types)}
        
        if params.include_properties:
            props_result = tkoiagent.execute_cypher("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey", limit=500)
            if props_result["ok"]:
                schema["property_keys"] = [r["propertyKey"] for r in props_result["data"]["records"]]
        
        if params.response_format == ResponseFormat.MARKDOWN:
            md = f"# SPOKE Knowledge Graph Schema\n\n## Node Types ({len(node_labels)})\n"
            md += "\n".join(f"- `{l}`" for l in node_labels[:50])
            if len(node_labels) > 50:
                md += f"\n- ... and {len(node_labels) - 50} more"
            md += f"\n\n## Relationship Types ({len(rel_types)})\n"
            md += "\n".join(f"- `{r}`" for r in rel_types[:50])
            if len(rel_types) > 50:
                md += f"\n- ... and {len(rel_types) - 50} more"
            return md
        
        return json.dumps({"ok": True, "data": schema}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "SCHEMA_ERROR", "message": str(e)}}, indent=2)


@mcp.tool(name="query_knowledge_graph", annotations={"title": "Execute Cypher Query on SPOKE", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def query_knowledge_graph(params: QueryKnowledgeGraphInput) -> str:
    """Execute a READ-ONLY Cypher query on the SPOKE biomedical knowledge graph.
    
    Use for custom queries to explore drug-disease associations, protein interactions, pathways.
    Only READ operations (MATCH, RETURN) are allowed.
    
    Example: MATCH (g:Gene)-[:PARTICIPATES_GpPW]->(p:Pathway) WHERE p.name CONTAINS 'apoptosis' RETURN g.name LIMIT 50
    """
    result = tkoiagent.execute_cypher(params.query, params.parameters, params.limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if params.response_format == ResponseFormat.MARKDOWN:
        records = result["data"]["records"]
        if not records:
            return "No results found."
        
        headers = list(records[0].keys())
        md = f"## Query Results ({len(records)} records)\n\n| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) + " |\n"
        
        for r in records[:50]:
            values = []
            for h in headers:
                v = r.get(h, "")
                if isinstance(v, dict) and v.get("_type") == "node":
                    v = f"{v.get('labels', ['?'])[0]}: {v.get('properties', {}).get('name', '?')}"
                values.append(str(v)[:50].replace("|", "\\|"))
            md += "| " + " | ".join(values) + " |\n"
        
        return md
    
    return json.dumps(result, indent=2)


@mcp.tool(name="search_nodes", annotations={"title": "Search Nodes in Knowledge Graph", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def search_nodes(params: SearchNodesInput) -> str:
    """Search for nodes in the SPOKE knowledge graph by name or identifier."""
    if params.node_types:
        labels = ":".join(params.node_types)
        query = f"MATCH (n:{labels}) WHERE toLower(n.name) CONTAINS toLower($search_term) OR toLower(n.identifier) CONTAINS toLower($search_term) RETURN labels(n) as labels, n.identifier as identifier, n.name as name LIMIT $limit"
    else:
        query = "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($search_term) OR toLower(n.identifier) CONTAINS toLower($search_term) RETURN labels(n) as labels, n.identifier as identifier, n.name as name LIMIT $limit"
    
    result = tkoiagent.execute_cypher(query, {"search_term": params.search_term, "limit": params.limit}, params.limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if params.response_format == ResponseFormat.MARKDOWN:
        records = result["data"]["records"]
        if not records:
            return f"No nodes found matching '{params.search_term}'"
        
        md = f"## Search Results for '{params.search_term}' ({len(records)} found)\n\n"
        for r in records:
            md += f"- **{r.get('name', 'N/A')}** ({', '.join(r.get('labels', []))}) - `{r.get('identifier', 'N/A')}`\n"
        return md
    
    return json.dumps(result, indent=2)


@mcp.tool(name="get_node_neighbors", annotations={"title": "Get Node Neighbors", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def get_node_neighbors(params: GetNodeNeighborsInput) -> str:
    """Get neighbors of a node in the knowledge graph."""
    if params.direction == "outgoing":
        pattern = "(source)-[r]->(neighbor)"
    elif params.direction == "incoming":
        pattern = "(source)<-[r]-(neighbor)"
    else:
        pattern = "(source)-[r]-(neighbor)"
    
    source_match = f"(source:{params.node_type} {{identifier: $node_id}})" if params.node_type else "(source {identifier: $node_id})"
    
    if params.relationship_types:
        rel_filter = ":" + "|".join(params.relationship_types)
        pattern = pattern.replace("[r]", f"[r{rel_filter}]")
    
    query = f"MATCH {source_match} MATCH {pattern} RETURN type(r) as relationship_type, labels(neighbor) as neighbor_labels, neighbor.identifier as neighbor_id, neighbor.name as neighbor_name LIMIT $limit"
    
    result = tkoiagent.execute_cypher(query, {"node_id": params.node_id, "limit": params.limit}, params.limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if params.response_format == ResponseFormat.MARKDOWN:
        records = result["data"]["records"]
        if not records:
            return f"No neighbors found for '{params.node_id}'"
        
        by_rel = {}
        for r in records:
            rel = r.get("relationship_type", "UNKNOWN")
            by_rel.setdefault(rel, []).append(r)
        
        md = f"## Neighbors of '{params.node_id}' ({len(records)} connections)\n\n"
        for rel_type, neighbors in by_rel.items():
            md += f"### {rel_type} ({len(neighbors)})\n"
            for n in neighbors[:20]:
                md += f"- **{n.get('neighbor_name', 'N/A')}** ({', '.join(n.get('neighbor_labels', []))}) - `{n.get('neighbor_id', 'N/A')}`\n"
            if len(neighbors) > 20:
                md += f"- ... and {len(neighbors) - 20} more\n"
        return md
    
    return json.dumps(result, indent=2)


@mcp.tool(name="get_path_between_nodes", annotations={"title": "Find Paths Between Nodes", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def get_path_between_nodes(params: GetPathBetweenNodesInput) -> str:
    """Find shortest paths between two nodes in the knowledge graph."""
    source_match = f":{params.source_type}" if params.source_type else ""
    target_match = f":{params.target_type}" if params.target_type else ""
    
    query = f"MATCH (source{source_match} {{identifier: $source_id}}), (target{target_match} {{identifier: $target_id}}), path = shortestPath((source)-[*1..{params.max_hops}]-(target)) RETURN length(path) as path_length, [n IN nodes(path) | n.name] as node_names, [r IN relationships(path) | type(r)] as relationship_types LIMIT $limit"
    
    result = tkoiagent.execute_cypher(query, {"source_id": params.source_id, "target_id": params.target_id, "limit": params.limit}, params.limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if params.response_format == ResponseFormat.MARKDOWN:
        records = result["data"]["records"]
        if not records:
            return f"No paths found between '{params.source_id}' and '{params.target_id}'"
        
        md = f"## Paths from '{params.source_id}' to '{params.target_id}' ({len(records)} found)\n\n"
        for i, r in enumerate(records, 1):
            node_names = r.get("node_names", [])
            rel_types = r.get("relationship_types", [])
            path_str = " → ".join(f"**{name}**" + (f" --[{rel_types[j]}]-->" if j < len(rel_types) else "") for j, name in enumerate(node_names))
            md += f"### Path {i} (length: {r.get('path_length', '?')})\n{path_str}\n\n"
        return md
    
    return json.dumps(result, indent=2)


@mcp.tool(name="get_gene_pathways", annotations={"title": "Get Pathways for Genes", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def get_gene_pathways(params: GetGenePathwaysInput) -> str:
    """Retrieve pathways associated with a list of genes.
    
    Essential for understanding biological processes affected by differentially expressed genes.
    """
    query = "UNWIND $gene_ids AS gene_id MATCH (g:Gene {identifier: gene_id})-[:PARTICIPATES_GpPW]->(p:Pathway) RETURN gene_id, g.name as gene_name, collect(DISTINCT {pathway_id: p.identifier, pathway_name: p.name})[0..$limit] as pathways"
    
    result = tkoiagent.execute_cypher(query, {"gene_ids": params.gene_ids, "limit": params.limit}, len(params.gene_ids) * params.limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if params.include_shared:
        shared_query = "MATCH (g:Gene)-[:PARTICIPATES_GpPW]->(p:Pathway) WHERE g.identifier IN $gene_ids WITH p, collect(DISTINCT g.identifier) as genes WHERE size(genes) > 1 RETURN p.name as pathway_name, genes as shared_by, size(genes) as gene_count ORDER BY gene_count DESC LIMIT 50"
        shared_result = tkoiagent.execute_cypher(shared_query, {"gene_ids": params.gene_ids}, 50)
        if shared_result["ok"]:
            result["data"]["shared_pathways"] = shared_result["data"]["records"]
    
    if params.response_format == ResponseFormat.MARKDOWN:
        records = result["data"]["records"]
        if not records:
            return "No pathway associations found."
        
        md = "## Gene-Pathway Associations\n\n"
        for r in records:
            md += f"### {r.get('gene_name', '?')} (`{r.get('gene_id', 'N/A')}`)\n"
            for p in r.get("pathways", [])[:20]:
                md += f"- {p.get('pathway_name', 'N/A')}\n"
        
        if params.include_shared and "shared_pathways" in result["data"]:
            md += "\n## Shared Pathways\n"
            for p in result["data"]["shared_pathways"][:20]:
                md += f"- **{p.get('pathway_name', 'N/A')}** - shared by {p.get('gene_count', 0)} genes\n"
        return md
    
    return json.dumps(result, indent=2)


@mcp.tool(name="get_gene_disease_associations", annotations={"title": "Get Disease Associations for Genes", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def get_gene_disease_associations(params: GetGeneDiseaseAssociationsInput) -> str:
    """Retrieve disease associations for a list of genes.
    
    Use to connect differentially expressed genes to relevant diseases for biological interpretation.
    """
    query = "UNWIND $gene_ids AS gene_id MATCH (g:Gene {identifier: gene_id})-[r:ASSOCIATES_DaG]-(d:Disease) RETURN gene_id, g.name as gene_name, collect(DISTINCT {disease_id: d.identifier, disease_name: d.name})[0..$limit] as diseases"
    
    result = tkoiagent.execute_cypher(query, {"gene_ids": params.gene_ids, "limit": params.limit}, len(params.gene_ids) * params.limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if params.response_format == ResponseFormat.MARKDOWN:
        records = result["data"]["records"]
        if not records:
            return "No disease associations found."
        
        md = "## Gene-Disease Associations\n\n"
        for r in records:
            md += f"### {r.get('gene_name', '?')} (`{r.get('gene_id', 'N/A')}`)\n"
            diseases = r.get("diseases", [])
            if diseases:
                for d in diseases[:20]:
                    md += f"- {d.get('disease_name', 'N/A')} (`{d.get('disease_id', 'N/A')}`)\n"
            else:
                md += "- No disease associations found\n"
        return md
    
    return json.dumps(result, indent=2)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    mcp.run()
