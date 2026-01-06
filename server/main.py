#!/usr/bin/env python3
"""
tKOIAgent: Transcriptomics Knowledge Graph-Driven Omics Integration Agent
MCP Server for R-based transcriptomics analysis and Neo4j biological knowledge graph querying
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import base64
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv

def load_environment():
    """Load environment variables from .env file."""
    for env_path in [Path.cwd() / ".env", Path(__file__).parent.resolve() / ".env", Path(__file__).parent.parent.resolve() / ".env"]:
        if env_path.exists():
            load_dotenv(env_path)
            return str(env_path)
    load_dotenv()
    return None

_env_file_loaded = load_environment()

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError, CypherSyntaxError

logging.basicConfig(level=os.environ.get("TKOIAGENT_LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

if _env_file_loaded:
    logger.info(f"Loaded environment from: {_env_file_loaded}")

KNOWLEDGE_GRAPH_URI = os.environ.get("KNOWLEDGE_GRAPH_URI", "bolt://spokedev.cgl.ucsf.edu:7687")
KNOWLEDGE_GRAPH_USERNAME = os.environ.get("KNOWLEDGE_GRAPH_USERNAME", "neo4j")
KNOWLEDGE_GRAPH_PASSWORD = os.environ.get("KNOWLEDGE_GRAPH_PASSWORD", "")
KNOWLEDGE_GRAPH_DATABASE = os.environ.get("KNOWLEDGE_GRAPH_DATABASE", "spoke")

def print_ascii_banner():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kg_configured = "✓" if KNOWLEDGE_GRAPH_PASSWORD else "✗"
    logger.info(f"""
╔════════════════════════════════════════════════════════════════════╗
    tKOIAgent - Transcriptomics Knowledge Graph Omics Integration
    Author: Wanjun Gu (wanjun.gu@ucsf.edu)
    Started: {current_time}
    KG URI: {KNOWLEDGE_GRAPH_URI} | DB: {KNOWLEDGE_GRAPH_DATABASE} | Auth: {kg_configured}
╚════════════════════════════════════════════════════════════════════╝
""")

class TKOIAgentServer:
    def __init__(self):
        self.state_dir: Optional[Path] = None
        self.state_file: Optional[Path] = None
        self.workdir: Optional[Path] = None
        self.primary_file: str = "agent.R"
        self._neo4j_driver = None
    
    def load_state(self) -> Dict[str, Any]:
        if not self.state_file or not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_state(self, state: Dict[str, Any]) -> None:
        if not self.state_file:
            return
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def ensure_workdir_set(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not self.workdir:
            return False, {"code": "NO_WORKDIR", "message": "Working directory not set. Use set_workdir first."}
        if not self.workdir.exists():
            return False, {"code": "WORKDIR_MISSING", "message": f"Working directory {self.workdir} no longer exists"}
        return True, None
    
    def is_safe_path(self, path: Path) -> bool:
        if not self.workdir:
            return False
        try:
            return path.resolve().is_relative_to(self.workdir)
        except:
            return False
    
    def find_r_executable(self) -> Optional[str]:
        return shutil.which("Rscript") or shutil.which("R")
    
    def run_r_command(self, args: List[str], timeout: int = 120) -> Dict[str, Any]:
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
        if self._neo4j_driver is None:
            if not KNOWLEDGE_GRAPH_PASSWORD:
                raise ValueError("KNOWLEDGE_GRAPH_PASSWORD environment variable is required")
            self._neo4j_driver = GraphDatabase.driver(KNOWLEDGE_GRAPH_URI, auth=(KNOWLEDGE_GRAPH_USERNAME, KNOWLEDGE_GRAPH_PASSWORD))
        return self._neo4j_driver
    
    def close_neo4j_driver(self):
        if self._neo4j_driver:
            self._neo4j_driver.close()
            self._neo4j_driver = None
    
    def execute_cypher(self, query: str, parameters: Optional[Dict] = None, limit: int = 100) -> Dict[str, Any]:
        try:
            driver = self.get_neo4j_driver()
            with driver.session(database=KNOWLEDGE_GRAPH_DATABASE) as session:
                result = session.run(query, parameters or {})
                records = []
                for i, record in enumerate(result):
                    if i >= limit:
                        break
                    records.append({key: self._convert_neo4j_value(record[key]) for key in record.keys()})
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

tkoiagent = TKOIAgentServer()

@asynccontextmanager
async def app_lifespan(app):
    print_ascii_banner()
    logger.info("tKOIAgent MCP server starting...")
    yield {"server": tkoiagent}
    tkoiagent.close_neo4j_driver()
    logger.info("tKOIAgent MCP server stopped.")

mcp = FastMCP("tkoiagent_mcp", lifespan=app_lifespan)

# =============================================================================
# R Toolchain Tools
# =============================================================================

@mcp.tool(name="set_workdir")
async def set_workdir(path: str, create: bool = True) -> str:
    """Set the working directory for all R operations and file management.
    
    Args:
        path: Absolute path to the working directory (e.g., '/Users/username/Desktop/project')
        create: Create the directory if it doesn't exist (default: True)
    """
    try:
        workdir = Path(path).expanduser().resolve()
        if not workdir.exists():
            if create:
                workdir.mkdir(parents=True, exist_ok=True)
            else:
                return json.dumps({"ok": False, "error": {"code": "DIR_NOT_FOUND", "message": f"Directory {path} does not exist"}}, indent=2)
        elif not workdir.is_dir():
            return json.dumps({"ok": False, "error": {"code": "NOT_A_DIR", "message": f"Path {path} is not a directory"}}, indent=2)
        
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

@mcp.tool(name="get_state")
async def get_state() -> str:
    """Get current tKOIAgent state including workdir, R availability, and Neo4j configuration."""
    state = tkoiagent.load_state() if tkoiagent.state_file else {}
    state.update({"workdir": str(tkoiagent.workdir) if tkoiagent.workdir else None, "primary_file": tkoiagent.primary_file, "r_available": tkoiagent.find_r_executable() is not None, "neo4j_configured": bool(KNOWLEDGE_GRAPH_PASSWORD)})
    return json.dumps({"ok": True, "data": state}, indent=2)

@mcp.tool(name="create_R_file")
async def create_R_file(filename: str, overwrite: bool = False, scaffold: bool = False) -> str:
    """Create a new R script file in the working directory.
    
    Args:
        filename: Name of the R script file to create (e.g., 'clean_data.R')
        overwrite: Overwrite if exists (default: False)
        scaffold: Include basic template (default: False)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    if not filename.endswith(('.R', '.r')):
        filename += '.R'
    filepath = tkoiagent.workdir / filename
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if filepath.exists() and not overwrite:
        return json.dumps({"ok": False, "error": {"code": "FILE_EXISTS", "message": f"File {filename} already exists"}}, indent=2)
    
    try:
        content = f"# tKOIAgent R Script\n# Generated: {datetime.now().isoformat()}\n\n" if scaffold else ""
        filepath.write_text(content)
        state = tkoiagent.load_state()
        state.setdefault("files", [])
        if filename not in state["files"]:
            state["files"].append(filename)
        tkoiagent.save_state(state)
        return json.dumps({"ok": True, "data": {"filename": filename, "filepath": str(filepath)}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "CREATE_ERROR", "message": str(e)}}, indent=2)

@mcp.tool(name="write_R_code")
async def write_R_code(code: str, filename: Optional[str] = None, overwrite: bool = False) -> str:
    """Write R code to a script file (replaces existing content).
    
    Args:
        code: The R code to write
        filename: Target filename (uses primary file if not specified)
        overwrite: Allow overwriting (default: False)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    target_file = filename or tkoiagent.primary_file
    if not target_file.endswith(('.R', '.r')):
        target_file += '.R'
    filepath = tkoiagent.workdir / target_file
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if filepath.exists() and not overwrite:
        return json.dumps({"ok": False, "error": {"code": "FILE_EXISTS", "message": f"File {target_file} exists. Set overwrite=true"}}, indent=2)
    
    try:
        content = code if code.endswith('\n') else code + '\n'
        filepath.write_text(content)
        state = tkoiagent.load_state()
        state.setdefault("files", [])
        if target_file not in state["files"]:
            state["files"].append(target_file)
        tkoiagent.save_state(state)
        return json.dumps({"ok": True, "data": {"filename": target_file, "lines_written": len(content.splitlines())}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "WRITE_ERROR", "message": str(e)}}, indent=2)

@mcp.tool(name="append_R_code")
async def append_R_code(code: str, filename: Optional[str] = None) -> str:
    """Append R code to an existing script file.
    
    Args:
        code: The R code to append
        filename: Target filename (uses primary file if not specified)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    target_file = filename or tkoiagent.primary_file
    if not target_file.endswith(('.R', '.r')):
        target_file += '.R'
    filepath = tkoiagent.workdir / target_file
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {target_file} does not exist"}}, indent=2)
    
    try:
        existing = filepath.read_text()
        new_code = code if code.endswith('\n') else code + '\n'
        if existing and not existing.endswith('\n'):
            existing += '\n'
        filepath.write_text(existing + new_code)
        return json.dumps({"ok": True, "data": {"filename": target_file, "lines_appended": len(code.splitlines())}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "APPEND_ERROR", "message": str(e)}}, indent=2)

@mcp.tool(name="run_R_script")
async def run_R_script(filename: Optional[str] = None, args: Optional[List[str]] = None, timeout_sec: int = 3600, save_rdata: bool = True) -> str:
    """Execute an R script file. IMPORTANT: tKOI analysis can take 30-60 minutes.
    
    Args:
        filename: R script to execute (uses primary file if not specified)
        args: Command-line arguments
        timeout_sec: Max execution time (default: 3600 = 1 hour)
        save_rdata: Save workspace after execution (default: True)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    target_file = filename or tkoiagent.primary_file
    if not target_file.endswith(('.R', '.r')):
        target_file += '.R'
    filepath = tkoiagent.workdir / target_file
    
    if not tkoiagent.is_safe_path(filepath):
        return json.dumps({"ok": False, "error": {"code": "UNSAFE_PATH", "message": "Path outside working directory"}}, indent=2)
    if not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"Script {target_file} does not exist"}}, indent=2)
    
    cmd_args = ["--save" if save_rdata else "--no-save", str(filepath)]
    if args:
        cmd_args.extend(args)
    
    result = tkoiagent.run_r_command(cmd_args, timeout=timeout_sec)
    if result["ok"]:
        result["data"]["filename"] = target_file
    return json.dumps(result, indent=2)

@mcp.tool(name="run_R_expression")
async def run_R_expression(expr: str, timeout_sec: int = 120) -> str:
    """Execute a single R expression for quick checks.
    
    Args:
        expr: R expression to execute
        timeout_sec: Max execution time (default: 120)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    result = tkoiagent.run_r_command(["-e", expr, "--slave"], timeout=timeout_sec)
    if result["ok"]:
        result["data"]["expression"] = expr[:100] + "..." if len(expr) > 100 else expr
    return json.dumps(result, indent=2)

@mcp.tool(name="list_exports")
async def list_exports(glob: str = "*", sort_by: str = "mtime", descending: bool = True, limit: int = 100) -> str:
    """List files in the working directory with filtering and sorting.
    
    Args:
        glob: Glob pattern (e.g., '*.csv', 'tkoi_*')
        sort_by: Sort by 'mtime', 'size', or 'name'
        descending: Sort descending (default: True)
        limit: Max files to return (default: 100)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    try:
        files = []
        for item in tkoiagent.workdir.glob(glob):
            if item.is_file():
                stat = item.stat()
                files.append({"name": item.name, "size": stat.st_size, "mtime": stat.st_mtime, "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"), "extension": item.suffix})
        
        if sort_by == "mtime":
            files.sort(key=lambda x: x["mtime"], reverse=descending)
        elif sort_by == "size":
            files.sort(key=lambda x: x["size"], reverse=descending)
        else:
            files.sort(key=lambda x: x["name"], reverse=not descending)
        
        return json.dumps({"ok": True, "data": {"files": files[:limit], "count": len(files[:limit])}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "LIST_ERROR", "message": str(e)}}, indent=2)

@mcp.tool(name="read_export")
async def read_export(name: str, max_bytes: int = 100000, as_text: bool = True, encoding: str = "utf-8") -> str:
    """Read content of a file from the working directory.
    
    Args:
        name: Filename to read
        max_bytes: Max file size (default: 100000)
        as_text: Read as text or base64 (default: True)
        encoding: Text encoding (default: 'utf-8')
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filepath = tkoiagent.workdir / name
    if not tkoiagent.is_safe_path(filepath) or not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {name} not found"}}, indent=2)
    
    try:
        file_size = filepath.stat().st_size
        if file_size > max_bytes:
            return json.dumps({"ok": False, "error": {"code": "FILE_TOO_LARGE", "message": f"File size ({file_size}) exceeds max ({max_bytes})"}}, indent=2)
        
        if as_text:
            content = filepath.read_text(encoding=encoding)
            return json.dumps({"ok": True, "data": {"content": content, "filename": name, "size": file_size, "lines": len(content.splitlines())}}, indent=2)
        else:
            content_b64 = base64.b64encode(filepath.read_bytes()).decode('ascii')
            return json.dumps({"ok": True, "data": {"content_base64": content_b64, "filename": name, "size": file_size}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "READ_ERROR", "message": str(e)}}, indent=2)

@mcp.tool(name="preview_table")
async def preview_table(name: str, delimiter: str = ",", max_rows: int = 50) -> str:
    """Preview a CSV/TSV file as structured tabular data.
    
    Args:
        name: CSV/TSV filename
        delimiter: Column delimiter (',' or 'tab' or 'auto')
        max_rows: Max rows to preview (default: 50)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    filepath = tkoiagent.workdir / name
    if not tkoiagent.is_safe_path(filepath) or not filepath.exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {name} not found"}}, indent=2)
    
    try:
        rows = []
        delim = "\t" if delimiter in ["\\t", "tab"] else delimiter
        
        with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
            if delim == "auto":
                sample = csvfile.read(1024)
                csvfile.seek(0)
                delim = csv.Sniffer().sniff(sample).delimiter
            
            reader = csv.reader(csvfile, delimiter=delim)
            header = next(reader, None)
            if not header:
                return json.dumps({"ok": False, "error": {"code": "EMPTY_FILE", "message": "File is empty"}}, indent=2)
            
            total_rows = 0
            for row in reader:
                total_rows += 1
                if len(rows) < max_rows:
                    rows.append(row)
        
        return json.dumps({"ok": True, "data": {"header": header, "rows": rows, "total_rows": total_rows, "displayed_rows": len(rows), "truncated": total_rows > max_rows}}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": {"code": "PREVIEW_ERROR", "message": str(e)}}, indent=2)

@mcp.tool(name="inspect_R_objects")
async def inspect_R_objects(objects: Optional[List[str]] = None, str_max_level: int = 2, timeout_sec: int = 120) -> str:
    """Inspect R objects from the saved .RData workspace.
    
    Args:
        objects: Object names to inspect (all if not provided)
        str_max_level: Max nesting level (default: 2)
        timeout_sec: Max execution time (default: 120)
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    rdata_file = tkoiagent.workdir / ".RData"
    if not rdata_file.exists():
        return json.dumps({"ok": False, "error": {"code": "NO_RDATA", "message": "No .RData file found"}}, indent=2)
    
    r_code = 'load(".RData"); all_objects = ls(); '
    if objects:
        obj_list = ', '.join([f'"{o}"' for o in objects])
        r_code += f'objects_to_inspect = intersect(c({obj_list}), all_objects); '
    else:
        r_code += 'objects_to_inspect = all_objects; '
    
    r_code += f'for (obj_name in objects_to_inspect) {{ cat("\\n=== ", obj_name, " ===\\n"); obj = get(obj_name); cat("Class:", paste(class(obj), collapse=", "), "\\n"); if (is.data.frame(obj)) cat("Dim:", nrow(obj), "x", ncol(obj), "\\n"); str(obj, max.level={str_max_level}); }}'
    
    result = tkoiagent.run_r_command(["-e", r_code, "--slave"], timeout=timeout_sec)
    if result["ok"]:
        result["data"]["objects_inspected"] = objects or "all"
    return json.dumps(result, indent=2)

@mcp.tool(name="ggplot_style_check")
async def ggplot_style_check(code: str) -> str:
    """Analyze ggplot2 code and suggest publication-quality style improvements.
    
    Args:
        code: R/ggplot2 code to analyze
    """
    optimizations = []
    optimized_code = code
    
    if "<-" in code:
        optimizations.append("Replace '<-' with '='")
        optimized_code = optimized_code.replace("<-", "=")
    if "theme_gray()" in code or "theme_grey()" in code:
        optimizations.append("Replace theme_gray() with theme_minimal(base_size=14)")
        optimized_code = optimized_code.replace("theme_gray()", "theme_minimal(base_size=14)").replace("theme_grey()", "theme_minimal(base_size=14)")
    if "ggsave(" in code and "dpi=" not in code:
        optimizations.append("Add dpi=800 to ggsave()")
    if "geom_point(" in code and "size=" not in code:
        optimizations.append("Set size=2.5 in geom_point()")
    
    return json.dumps({"ok": True, "data": {"original_code": code, "optimized_code": optimized_code, "optimizations": optimizations}}, indent=2)

@mcp.tool(name="which_R")
async def which_R() -> str:
    """Find R/Rscript executable in the system PATH."""
    exe = tkoiagent.find_r_executable()
    if exe:
        return json.dumps({"ok": True, "data": {"executable": exe}}, indent=2)
    return json.dumps({"ok": False, "error": {"code": "R_NOT_FOUND", "message": "R not found in PATH"}}, indent=2)

@mcp.tool(name="list_R_files")
async def list_R_files() -> str:
    """List all R script files in the working directory."""
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    r_files = sorted(set(item.name for pattern in ["*.R", "*.r"] for item in tkoiagent.workdir.glob(pattern) if item.is_file()))
    return json.dumps({"ok": True, "data": {"files": r_files, "primary_file": tkoiagent.primary_file}}, indent=2)

@mcp.tool(name="set_primary_file")
async def set_primary_file(filename: str) -> str:
    """Set the primary R script file used by default.
    
    Args:
        filename: Filename to set as primary
    """
    ok, error = tkoiagent.ensure_workdir_set()
    if not ok:
        return json.dumps({"ok": False, "error": error}, indent=2)
    
    target_file = filename if filename.endswith(('.R', '.r')) else filename + '.R'
    if not (tkoiagent.workdir / target_file).exists():
        return json.dumps({"ok": False, "error": {"code": "FILE_NOT_FOUND", "message": f"File {target_file} does not exist"}}, indent=2)
    
    tkoiagent.primary_file = target_file
    state = tkoiagent.load_state()
    state["primary_file"] = target_file
    tkoiagent.save_state(state)
    return json.dumps({"ok": True, "data": {"primary_file": target_file}}, indent=2)

# =============================================================================
# Knowledge Graph Toolchain Tools
# =============================================================================

def validate_read_only_query(query: str) -> Optional[str]:
    """Validate that a Cypher query is read-only."""
    write_keywords = ['CREATE', 'DELETE', 'SET', 'MERGE', 'REMOVE', 'DROP', 'DETACH']
    query_upper = query.upper()
    for keyword in write_keywords:
        if keyword in query_upper:
            return f"Write operations ({keyword}) are not allowed."
    return None

@mcp.tool(name="get_knowledge_graph_schema")
async def get_knowledge_graph_schema(include_properties: bool = True, include_counts: bool = False, response_format: str = "markdown") -> str:
    """Retrieve the schema of the SPOKE biomedical knowledge graph.
    
    Args:
        include_properties: Include properties (default: True)
        include_counts: Include node counts (default: False)
        response_format: 'markdown' or 'json' (default: 'markdown')
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
        
        if include_properties:
            props_result = tkoiagent.execute_cypher("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey ORDER BY propertyKey", limit=500)
            if props_result["ok"]:
                schema["property_keys"] = [r["propertyKey"] for r in props_result["data"]["records"]]
        
        if response_format == "markdown":
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

@mcp.tool(name="query_knowledge_graph")
async def query_knowledge_graph(query: str, parameters: Optional[Dict[str, Any]] = None, limit: int = 100, response_format: str = "json") -> str:
    """Execute a READ-ONLY Cypher query on the SPOKE knowledge graph.
    
    Args:
        query: Cypher query (READ-ONLY only)
        parameters: Query parameters
        limit: Max results (default: 100)
        response_format: 'markdown' or 'json' (default: 'json')
    """
    validation_error = validate_read_only_query(query)
    if validation_error:
        return json.dumps({"ok": False, "error": {"code": "WRITE_NOT_ALLOWED", "message": validation_error}}, indent=2)
    
    result = tkoiagent.execute_cypher(query, parameters, limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if response_format == "markdown":
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

@mcp.tool(name="search_nodes")
async def search_nodes(search_term: str, node_types: Optional[List[str]] = None, limit: int = 25, response_format: str = "markdown") -> str:
    """Search for nodes in the SPOKE knowledge graph by name or identifier.
    
    Args:
        search_term: Term to search for
        node_types: Limit to specific types (e.g., ['Gene', 'Disease'])
        limit: Max results (default: 25)
        response_format: 'markdown' or 'json' (default: 'markdown')
    """
    if node_types:
        labels = ":".join(node_types)
        query = f"MATCH (n:{labels}) WHERE toLower(n.name) CONTAINS toLower($search_term) OR toLower(n.identifier) CONTAINS toLower($search_term) RETURN labels(n) as labels, n.identifier as identifier, n.name as name LIMIT $limit"
    else:
        query = "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($search_term) OR toLower(n.identifier) CONTAINS toLower($search_term) RETURN labels(n) as labels, n.identifier as identifier, n.name as name LIMIT $limit"
    
    result = tkoiagent.execute_cypher(query, {"search_term": search_term, "limit": limit}, limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if response_format == "markdown":
        records = result["data"]["records"]
        if not records:
            return f"No nodes found matching '{search_term}'"
        md = f"## Search Results for '{search_term}' ({len(records)} found)\n\n"
        for r in records:
            md += f"- **{r.get('name', 'N/A')}** ({', '.join(r.get('labels', []))}) - `{r.get('identifier', 'N/A')}`\n"
        return md
    
    return json.dumps(result, indent=2)

@mcp.tool(name="get_node_neighbors")
async def get_node_neighbors(node_id: str, node_type: Optional[str] = None, relationship_types: Optional[List[str]] = None, direction: str = "both", limit: int = 50, response_format: str = "markdown") -> str:
    """Get neighbors of a node in the knowledge graph.
    
    Args:
        node_id: Node identifier (e.g., 'ENSG00000141510')
        node_type: Node type (e.g., 'Gene')
        relationship_types: Filter by relationship types
        direction: 'outgoing', 'incoming', or 'both' (default: 'both')
        limit: Max neighbors (default: 50)
        response_format: 'markdown' or 'json' (default: 'markdown')
    """
    if direction == "outgoing":
        pattern = "(source)-[r]->(neighbor)"
    elif direction == "incoming":
        pattern = "(source)<-[r]-(neighbor)"
    else:
        pattern = "(source)-[r]-(neighbor)"
    
    source_match = f"(source:{node_type} {{identifier: $node_id}})" if node_type else "(source {identifier: $node_id})"
    
    if relationship_types:
        rel_filter = ":" + "|".join(relationship_types)
        pattern = pattern.replace("[r]", f"[r{rel_filter}]")
    
    query = f"MATCH {source_match} MATCH {pattern} RETURN type(r) as relationship_type, labels(neighbor) as neighbor_labels, neighbor.identifier as neighbor_id, neighbor.name as neighbor_name LIMIT $limit"
    
    result = tkoiagent.execute_cypher(query, {"node_id": node_id, "limit": limit}, limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if response_format == "markdown":
        records = result["data"]["records"]
        if not records:
            return f"No neighbors found for '{node_id}'"
        
        by_rel = {}
        for r in records:
            rel = r.get("relationship_type", "UNKNOWN")
            by_rel.setdefault(rel, []).append(r)
        
        md = f"## Neighbors of '{node_id}' ({len(records)} connections)\n\n"
        for rel_type, neighbors in by_rel.items():
            md += f"### {rel_type} ({len(neighbors)})\n"
            for n in neighbors[:20]:
                md += f"- **{n.get('neighbor_name', 'N/A')}** ({', '.join(n.get('neighbor_labels', []))}) - `{n.get('neighbor_id', 'N/A')}`\n"
            if len(neighbors) > 20:
                md += f"- ... and {len(neighbors) - 20} more\n"
        return md
    
    return json.dumps(result, indent=2)

@mcp.tool(name="get_path_between_nodes")
async def get_path_between_nodes(source_id: str, target_id: str, source_type: Optional[str] = None, target_type: Optional[str] = None, max_hops: int = 3, limit: int = 10, response_format: str = "markdown") -> str:
    """Find shortest paths between two nodes in the knowledge graph.
    
    Args:
        source_id: Source node identifier
        target_id: Target node identifier
        source_type: Source node type (e.g., 'Gene')
        target_type: Target node type (e.g., 'Disease')
        max_hops: Max path length (default: 3)
        limit: Max paths (default: 10)
        response_format: 'markdown' or 'json' (default: 'markdown')
    """
    source_match = f":{source_type}" if source_type else ""
    target_match = f":{target_type}" if target_type else ""
    
    query = f"MATCH (source{source_match} {{identifier: $source_id}}), (target{target_match} {{identifier: $target_id}}), path = shortestPath((source)-[*1..{max_hops}]-(target)) RETURN length(path) as path_length, [n IN nodes(path) | n.name] as node_names, [r IN relationships(path) | type(r)] as relationship_types LIMIT $limit"
    
    result = tkoiagent.execute_cypher(query, {"source_id": source_id, "target_id": target_id, "limit": limit}, limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if response_format == "markdown":
        records = result["data"]["records"]
        if not records:
            return f"No paths found between '{source_id}' and '{target_id}'"
        
        md = f"## Paths from '{source_id}' to '{target_id}' ({len(records)} found)\n\n"
        for i, r in enumerate(records, 1):
            node_names = r.get("node_names", [])
            rel_types = r.get("relationship_types", [])
            path_parts = []
            for j, name in enumerate(node_names):
                path_parts.append(f"**{name}**")
                if j < len(rel_types):
                    path_parts.append(f" --[{rel_types[j]}]--> ")
            md += f"### Path {i} (length: {r.get('path_length', '?')})\n{''.join(path_parts)}\n\n"
        return md
    
    return json.dumps(result, indent=2)

@mcp.tool(name="get_gene_pathways")
async def get_gene_pathways(gene_ids: List[str], include_shared: bool = True, limit: int = 50, response_format: str = "markdown") -> str:
    """Retrieve pathways associated with a list of genes.
    
    Args:
        gene_ids: List of gene identifiers (Ensembl IDs recommended)
        include_shared: Include pathways shared by multiple genes (default: True)
        limit: Max pathways per gene (default: 50)
        response_format: 'markdown' or 'json' (default: 'markdown')
    """
    query = "UNWIND $gene_ids AS gene_id MATCH (g:Gene {identifier: gene_id})-[:PARTICIPATES_GpPW]->(p:Pathway) RETURN gene_id, g.name as gene_name, collect(DISTINCT {pathway_id: p.identifier, pathway_name: p.name})[0..$limit] as pathways"
    
    result = tkoiagent.execute_cypher(query, {"gene_ids": gene_ids, "limit": limit}, len(gene_ids) * limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if include_shared:
        shared_query = "MATCH (g:Gene)-[:PARTICIPATES_GpPW]->(p:Pathway) WHERE g.identifier IN $gene_ids WITH p, collect(DISTINCT g.identifier) as genes WHERE size(genes) > 1 RETURN p.name as pathway_name, genes as shared_by, size(genes) as gene_count ORDER BY gene_count DESC LIMIT 50"
        shared_result = tkoiagent.execute_cypher(shared_query, {"gene_ids": gene_ids}, 50)
        if shared_result["ok"]:
            result["data"]["shared_pathways"] = shared_result["data"]["records"]
    
    if response_format == "markdown":
        records = result["data"]["records"]
        if not records:
            return "No pathway associations found."
        
        md = "## Gene-Pathway Associations\n\n"
        for r in records:
            md += f"### {r.get('gene_name', '?')} (`{r.get('gene_id', 'N/A')}`)\n"
            for p in r.get("pathways", [])[:20]:
                md += f"- {p.get('pathway_name', 'N/A')}\n"
        
        if include_shared and "shared_pathways" in result["data"]:
            md += "\n## Shared Pathways\n"
            for p in result["data"]["shared_pathways"][:20]:
                md += f"- **{p.get('pathway_name', 'N/A')}** - shared by {p.get('gene_count', 0)} genes\n"
        return md
    
    return json.dumps(result, indent=2)

@mcp.tool(name="get_gene_disease_associations")
async def get_gene_disease_associations(gene_ids: List[str], limit: int = 50, response_format: str = "markdown") -> str:
    """Retrieve disease associations for a list of genes.
    
    Args:
        gene_ids: List of gene identifiers (Ensembl IDs recommended)
        limit: Max associations per gene (default: 50)
        response_format: 'markdown' or 'json' (default: 'markdown')
    """
    query = "UNWIND $gene_ids AS gene_id MATCH (g:Gene {identifier: gene_id})-[r:ASSOCIATES_DaG]-(d:Disease) RETURN gene_id, g.name as gene_name, collect(DISTINCT {disease_id: d.identifier, disease_name: d.name})[0..$limit] as diseases"
    
    result = tkoiagent.execute_cypher(query, {"gene_ids": gene_ids, "limit": limit}, len(gene_ids) * limit)
    
    if not result["ok"]:
        return json.dumps(result, indent=2)
    
    if response_format == "markdown":
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

