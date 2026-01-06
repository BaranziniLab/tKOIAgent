#!/usr/bin/env python3
"""
PilotR: MCP-compliant R code execution and management agent
Purpose: Generate, execute, and manage R scripts within a user-specified directory
Requirements: Python 3.12+, MCP SDK, R runtime (Rscript in PATH)
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import base64
import csv
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Configure logging to stderr for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ASCII Art for PilotR
def print_ascii_banner():
    """Print ASCII art banner with current date/time"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    banner = f"""
╔════════════════════════════════════════════════╗

    PilotR
    MCP Server for R Script Management
    Author: Wanjun Gu (wanjun.gu@ucsf.edu)
    Started: {current_time}

╚════════════════════════════════════════════════╝
"""
    logger.info(banner)

# Minimal R script scaffold template
R_SCAFFOLD = """
"""

# ggplot Style Guide for reference
GGPLOT_STYLE_GUIDE = """
# ggplot Style Guide - One-Time Code Optimization

## Core Principles:
1. **Assignment**: Always use = instead of <- 
2. **Theme**: Use theme_minimal() or theme_classic() with base_size=14
3. **Colors**: Muted palettes (Set2 for categorical, viridis for continuous)
4. **Dimensions**: Optimize for 5x4 inches (width x height)
5. **Typography**: Base size ≥ 14pt for readability
6. **Visibility**: Points ≥ 2.5, lines ≥ 0.8 width
7. **Export**: Always save with dpi=800

## Color Palette Guidelines:
### Categorical Data:
- Set2, Set3, Pastel1, Pastel2, Dark2 (RColorBrewer)
- Avoid default ggplot2 colors

### Continuous Data:
- viridis, magma, plasma, inferno, cividis
- Colorblind-friendly by default

### Diverging Data:
- RdBu, RdYlBu, Spectral, PuOr, BrBG
- Center at meaningful value

## Code Optimization Example:
```r
# Good practice - optimized code
library(ggplot2)

# Use = for assignments
data = read.csv("data.csv")

# Build plot with optimal settings
p = ggplot(data, aes(x=x_var, y=y_var, color=group)) +
  geom_point(size=2.5, alpha=0.8) +
  geom_line(linewidth=0.8) +
  scale_color_brewer(palette="Set2") +  # Muted categorical colors
  theme_minimal(base_size=14) +
  labs(x="Clear X Label",
       y="Clear Y Label", 
       title="Concise Title") +
  theme(plot.margin=margin(10,10,10,10))

# Save with optimal dimensions and quality
ggsave("plot.png", p, width=5, height=4, dpi=800)
```

## Automatic Optimizations:
- Replace theme_gray() → theme_minimal(base_size=14)
- Convert <- to = throughout
- Add color scales if missing (no defaults)
- Optimize dimensions to 5x4 inches
- Ensure dpi=800 for all exports
- Humanize variable names in labels
"""

class PilotRServer:
    def __init__(self):
        self.state_dir = None
        self.state_file = None
        self.workdir = None
        self.primary_file = "agent.R"  # Using uppercase .R extension
        
    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file"""
        if not self.state_file or not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return {}
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state to JSON file with atomic write"""
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
        """Check if workdir is set and valid"""
        if not self.workdir:
            return False, {"code": "NO_WORKDIR", "message": "Working directory not set. Use set_workdir first.", "hints": ["Call set_workdir with a directory path"]}
        if not self.workdir.exists():
            return False, {"code": "WORKDIR_MISSING", "message": f"Working directory {self.workdir} no longer exists", "hints": ["Recreate or set a new working directory"]}
        return True, None
    
    def is_safe_path(self, path: Path) -> bool:
        """Check if path is within workdir"""
        if not self.workdir:
            return False
        try:
            resolved = path.resolve()
            # For Python 3.12 compatibility (is_relative_to is available)
            return resolved.is_relative_to(self.workdir)
        except (ValueError, RuntimeError):
            return False
    
    def find_r_executable(self) -> Optional[str]:
        """Find R executable, preferring Rscript"""
        rscript = shutil.which("Rscript")
        if rscript:
            return rscript
        r_exe = shutil.which("R")
        if r_exe:
            return r_exe
        return None
    
    def run_r_command(self, args: List[str], timeout: int = 120) -> Dict[str, Any]:
        """Execute R command and capture output"""
        r_exe = self.find_r_executable()
        if not r_exe:
            return {
                "ok": False,
                "error": {
                    "code": "R_NOT_FOUND",
                    "message": "Rscript not found in PATH. Please install R or add Rscript to PATH.",
                    "hints": ["Install R from https://www.r-project.org/", "Ensure Rscript is in your system PATH"]
                }
            }
        
        try:
            # Change to workdir for execution
            original_cwd = os.getcwd()
            if self.workdir:
                os.chdir(self.workdir)
            
            # Execute the R command
            result = subprocess.run(
                [r_exe] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            # Restore original working directory
            os.chdir(original_cwd)
            
            # Process output
            stdout_lines = result.stdout.strip().split('\n') if result.stdout else []
            stderr_lines = result.stderr.strip().split('\n') if result.stderr else []
            
            # Clean up R output (remove empty lines and warnings about no visible binding)
            stdout_lines = [line for line in stdout_lines if line and not line.startswith("Loading required package:")]
            stderr_lines = [line for line in stderr_lines if line and "no visible binding" not in line]
            
            if result.returncode != 0:
                return {
                    "ok": False,
                    "error": {
                        "code": "R_EXECUTION_ERROR",
                        "message": f"R execution failed with code {result.returncode}",
                        "details": {
                            "stdout": stdout_lines,
                            "stderr": stderr_lines,
                            "returncode": result.returncode
                        }
                    }
                }
            
            return {
                "ok": True,
                "data": {
                    "stdout": stdout_lines,
                    "stderr": stderr_lines,
                    "returncode": result.returncode
                }
            }
            
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": {
                    "code": "TIMEOUT",
                    "message": f"R execution timed out after {timeout} seconds",
                    "hints": ["Consider increasing timeout_sec parameter", "Check for infinite loops or long-running operations"]
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": f"Failed to execute R: {str(e)}"
                }
            }
    
    async def handle_set_workdir(self, path: str, create: bool = True) -> Dict[str, Any]:
        """Set working directory"""
        try:
            workdir = Path(path).expanduser().resolve()
            
            if not workdir.exists():
                if create:
                    workdir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {workdir}")
                else:
                    return {
                        "ok": False,
                        "error": {
                            "code": "DIR_NOT_FOUND",
                            "message": f"Directory {path} does not exist",
                            "hints": ["Set create=true to create the directory", "Check the path is correct"]
                        }
                    }
            elif not workdir.is_dir():
                return {
                    "ok": False,
                    "error": {
                        "code": "NOT_A_DIR",
                        "message": f"Path {path} exists but is not a directory"
                    }
                }
            
            # Set workdir and state paths
            self.workdir = workdir
            self.state_dir = workdir / ".pilotr"
            self.state_dir.mkdir(exist_ok=True)
            self.state_file = self.state_dir / "state.json"
            
            # Save state
            state = self.load_state()
            state.update({
                "workdir": str(self.workdir),
                "primary_file": self.primary_file,
                "updated_at": datetime.now().isoformat()
            })
            self.save_state(state)
            
            logger.info(f"Working directory set to: {self.workdir}")
            return {
                "ok": True,
                "data": {
                    "workdir": str(self.workdir),
                    "state_dir": str(self.state_dir),
                    "primary_file": self.primary_file
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "SET_DIR_ERROR",
                    "message": f"Failed to set working directory: {str(e)}"
                }
            }
    
    async def handle_get_state(self) -> Dict[str, Any]:
        """Get current state"""
        state = self.load_state() if self.state_file else {}
        
        # Add current runtime state
        state.update({
            "workdir": str(self.workdir) if self.workdir else None,
            "primary_file": self.primary_file,
            "r_available": self.find_r_executable() is not None
        })
        
        return {
            "ok": True,
            "data": state
        }
    
    async def handle_create_R_file(self, filename: str, overwrite: bool = False, scaffold: bool = True) -> Dict[str, Any]:
        """Create a new R script file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename += '.R'
        
        filepath = self.workdir / filename
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if filepath.exists() and not overwrite:
            return {
                "ok": False,
                "error": {
                    "code": "FILE_EXISTS",
                    "message": f"File {filename} already exists",
                    "hints": ["Set overwrite=true to replace the file", "Choose a different filename"]
                }
            }
        
        try:
            # Create file with scaffold or empty
            content = R_SCAFFOLD if scaffold else ""
            filepath.write_text(content)
            
            # Update state
            state = self.load_state()
            if "files" not in state:
                state["files"] = []
            if filename not in state["files"]:
                state["files"].append(filename)
            state["updated_at"] = datetime.now().isoformat()
            self.save_state(state)
            
            logger.info(f"Created R file: {filepath}")
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "filepath": str(filepath),
                    "scaffold_used": scaffold
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "CREATE_ERROR",
                    "message": f"Failed to create file: {str(e)}"
                }
            }
    
    async def handle_rename_R_file(self, old_name: str, new_name: str, overwrite: bool = False) -> Dict[str, Any]:
        """Rename an R script file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Ensure .R extension
        if not old_name.endswith(('.R', '.r')):
            old_name += '.R'
        if not new_name.endswith(('.R', '.r')):
            new_name += '.R'
        
        old_path = self.workdir / old_name
        new_path = self.workdir / new_name
        
        if not self.is_safe_path(old_path) or not self.is_safe_path(new_path):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": "File path is outside working directory"
                }
            }
        
        if not old_path.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {old_name} does not exist"
                }
            }
        
        if new_path.exists() and not overwrite:
            return {
                "ok": False,
                "error": {
                    "code": "FILE_EXISTS",
                    "message": f"File {new_name} already exists",
                    "hints": ["Set overwrite=true to replace the file", "Choose a different name"]
                }
            }
        
        try:
            # Rename the file
            if new_path.exists() and overwrite:
                new_path.unlink()
            old_path.rename(new_path)
            
            # Update state
            state = self.load_state()
            if "files" in state and old_name in state["files"]:
                state["files"].remove(old_name)
                state["files"].append(new_name)
            if state.get("primary_file") == old_name:
                state["primary_file"] = new_name
                self.primary_file = new_name
            state["updated_at"] = datetime.now().isoformat()
            self.save_state(state)
            
            logger.info(f"Renamed {old_name} to {new_name}")
            return {
                "ok": True,
                "data": {
                    "old_name": old_name,
                    "new_name": new_name
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "RENAME_ERROR",
                    "message": f"Failed to rename file: {str(e)}"
                }
            }
    
    async def handle_set_primary_file(self, filename: str) -> Dict[str, Any]:
        """Set the primary R script file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename += '.R'
        
        filepath = self.workdir / filename
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        # Check if file exists
        if not filepath.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {filename} does not exist",
                    "hints": ["Create the file first with create_R_file", "Check the filename is correct"]
                }
            }
        
        # Update primary file
        self.primary_file = filename
        
        # Save state
        state = self.load_state()
        state["primary_file"] = filename
        state["updated_at"] = datetime.now().isoformat()
        self.save_state(state)
        
        logger.info(f"Set primary file to: {filename}")
        return {
            "ok": True,
            "data": {
                "primary_file": filename
            }
        }
    
    async def handle_append_R_code(self, code: str, filename: Optional[str] = None, ensure_trailing_newline: bool = True) -> Dict[str, Any]:
        """Append R code to an existing script file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Use primary file if not specified
        if not filename:
            filename = self.primary_file
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename += '.R'
        
        filepath = self.workdir / filename
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if not filepath.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {filename} does not exist",
                    "hints": ["Create the file first with create_R_file", "Check the filename is correct"]
                }
            }
        
        try:
            # Read existing content
            existing_content = filepath.read_text()
            
            # Prepare code to append
            code_to_append = code
            if ensure_trailing_newline and not code.endswith('\n'):
                code_to_append += '\n'
            
            # Ensure existing content ends with newline before appending
            if existing_content and not existing_content.endswith('\n'):
                existing_content += '\n'
            
            # Append code
            new_content = existing_content + code_to_append
            filepath.write_text(new_content)
            
            logger.info(f"Appended {len(code.splitlines())} lines to {filename}")
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "lines_appended": len(code.splitlines()),
                    "total_lines": len(new_content.splitlines())
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "APPEND_ERROR",
                    "message": f"Failed to append code: {str(e)}"
                }
            }
    
    async def handle_write_R_code(self, code: str, filename: Optional[str] = None, overwrite: bool = False, use_scaffold_header: bool = True) -> Dict[str, Any]:
        """Write R code to a script file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Use primary file if not specified
        if not filename:
            filename = self.primary_file
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename += '.R'
        
        filepath = self.workdir / filename
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if filepath.exists() and not overwrite:
            return {
                "ok": False,
                "error": {
                    "code": "FILE_EXISTS",
                    "message": f"File {filename} already exists",
                    "hints": ["Set overwrite=true to replace the file", "Use append_R_code to add to existing file"]
                }
            }
        
        try:
            # Prepare content
            if use_scaffold_header and R_SCAFFOLD:
                content = R_SCAFFOLD + code
            else:
                content = code
            
            # Ensure trailing newline
            if content and not content.endswith('\n'):
                content += '\n'
            
            # Write file
            filepath.write_text(content)
            
            # Update state
            state = self.load_state()
            if "files" not in state:
                state["files"] = []
            if filename not in state["files"]:
                state["files"].append(filename)
            state["updated_at"] = datetime.now().isoformat()
            self.save_state(state)
            
            logger.info(f"Wrote {len(content.splitlines())} lines to {filename}")
            return {
                "ok": True,
                "data": {
                    "filename": filename,
                    "lines_written": len(content.splitlines()),
                    "scaffold_used": use_scaffold_header
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "WRITE_ERROR",
                    "message": f"Failed to write code: {str(e)}"
                }
            }
    
    async def handle_run_R_script(self, filename: Optional[str] = None, args: Optional[List[str]] = None, 
                                  timeout_sec: int = 120, save_rdata: bool = True) -> Dict[str, Any]:
        """Execute an R script file"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Use primary file if not specified
        if not filename:
            filename = self.primary_file
        
        # Ensure .R extension
        if not filename.endswith(('.R', '.r')):
            filename += '.R'
        
        filepath = self.workdir / filename
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {filename} is outside working directory"
                }
            }
        
        if not filepath.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"Script file {filename} does not exist",
                    "hints": ["Create and write the script first", "Check the filename is correct"]
                }
            }
        
        # Build command args
        cmd_args = []
        
        # Add save workspace option
        if save_rdata:
            cmd_args.extend(["--save"])
        else:
            cmd_args.extend(["--no-save"])
        
        # Add the script file
        cmd_args.append(str(filepath))
        
        # Add any additional arguments
        if args:
            cmd_args.extend(args)
        
        # Execute the script
        result = self.run_r_command(cmd_args, timeout=timeout_sec)
        
        if result["ok"]:
            logger.info(f"Successfully executed {filename}")
            result["data"]["filename"] = filename
            result["data"]["save_rdata"] = save_rdata
        else:
            logger.error(f"Failed to execute {filename}: {result['error']['message']}")
        
        return result
    
    async def handle_run_R_expression(self, expr: str, timeout_sec: int = 60) -> Dict[str, Any]:
        """Execute a single R expression"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Execute the expression using -e flag
        result = self.run_r_command(["-e", expr, "--slave"], timeout=timeout_sec)
        
        if result["ok"]:
            logger.info(f"Successfully executed expression: {expr[:50]}...")
            result["data"]["expression"] = expr
        else:
            logger.error(f"Failed to execute expression: {result['error']['message']}")
        
        return result
    
    async def handle_list_exports(self, glob: str = "*", sort_by: str = "mtime", 
                                  descending: bool = True, limit: int = 200) -> Dict[str, Any]:
        """List files in the working directory"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        try:
            # Get matching files
            files = []
            for item in self.workdir.glob(glob):
                if item.is_file():
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "mtime_str": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "extension": item.suffix
                    })
            
            # Sort files
            if sort_by == "mtime":
                files.sort(key=lambda x: x["mtime"], reverse=descending)
            elif sort_by == "size":
                files.sort(key=lambda x: x["size"], reverse=descending)
            elif sort_by == "name":
                files.sort(key=lambda x: x["name"], reverse=not descending)
            
            # Limit results
            files = files[:limit]
            
            return {
                "ok": True,
                "data": {
                    "files": files,
                    "count": len(files),
                    "workdir": str(self.workdir)
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "LIST_ERROR",
                    "message": f"Failed to list files: {str(e)}"
                }
            }
    
    async def handle_read_export(self, name: str, max_bytes: int = 50000, 
                                 as_text: bool = True, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read a file from the working directory"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        filepath = self.workdir / name
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {name} is outside working directory"
                }
            }
        
        if not filepath.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {name} does not exist"
                }
            }
        
        if not filepath.is_file():
            return {
                "ok": False,
                "error": {
                    "code": "NOT_A_FILE",
                    "message": f"{name} is not a file"
                }
            }
        
        try:
            file_size = filepath.stat().st_size
            
            if file_size > max_bytes:
                return {
                    "ok": False,
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": f"File size ({file_size} bytes) exceeds maximum ({max_bytes} bytes)",
                        "hints": [f"Increase max_bytes parameter (current: {max_bytes})", "Use preview_table for CSV files"]
                    }
                }
            
            if as_text:
                content = filepath.read_text(encoding=encoding)
                return {
                    "ok": True,
                    "data": {
                        "content": content,
                        "filename": name,
                        "size": file_size,
                        "lines": len(content.splitlines())
                    }
                }
            else:
                content = filepath.read_bytes()
                # Encode as base64 for transport
                content_b64 = base64.b64encode(content).decode('ascii')
                return {
                    "ok": True,
                    "data": {
                        "content_base64": content_b64,
                        "filename": name,
                        "size": file_size
                    }
                }
        except UnicodeDecodeError as e:
            return {
                "ok": False,
                "error": {
                    "code": "DECODE_ERROR",
                    "message": f"Failed to decode file as {encoding}: {str(e)}",
                    "hints": ["Try as_text=false for binary files", f"Try a different encoding (current: {encoding})"]
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "READ_ERROR",
                    "message": f"Failed to read file: {str(e)}"
                }
            }
    
    async def handle_preview_table(self, name: str, delimiter: str = ",", max_rows: int = 50) -> Dict[str, Any]:
        """Preview a CSV/TSV file as a table"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        filepath = self.workdir / name
        
        if not self.is_safe_path(filepath):
            return {
                "ok": False,
                "error": {
                    "code": "UNSAFE_PATH",
                    "message": f"File path {name} is outside working directory"
                }
            }
        
        if not filepath.exists():
            return {
                "ok": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {name} does not exist"
                }
            }
        
        try:
            rows = []
            total_rows = 0
            
            # Auto-detect delimiter if tab is specified
            if delimiter == "\\t" or delimiter == "tab":
                delimiter = "\t"
            
            with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
                # Try to detect the delimiter if not sure
                if delimiter == "auto":
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    sniffer = csv.Sniffer()
                    delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.reader(csvfile, delimiter=delimiter)
                
                # Read header
                header = next(reader, None)
                if not header:
                    return {
                        "ok": False,
                        "error": {
                            "code": "EMPTY_FILE",
                            "message": "CSV file is empty"
                        }
                    }
                
                # Read data rows
                for row in reader:
                    total_rows += 1
                    if len(rows) < max_rows:
                        rows.append(row)
            
            return {
                "ok": True,
                "data": {
                    "header": header,
                    "rows": rows,
                    "total_rows": total_rows,
                    "displayed_rows": len(rows),
                    "delimiter": delimiter,
                    "truncated": total_rows > max_rows
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "PREVIEW_ERROR",
                    "message": f"Failed to preview table: {str(e)}",
                    "hints": ["Check the file format", f"Try a different delimiter (current: {delimiter})"]
                }
            }
    
    async def handle_ggplot_style_check(self, code: str) -> Dict[str, Any]:
        """Analyze and optimize ggplot code for publication-quality styling"""
        try:
            optimizations = []
            optimized_code = code
            
            # Check for assignment operator
            if "<-" in code:
                optimizations.append("Replace '<-' with '=' for consistency")
                optimized_code = optimized_code.replace("<-", "=")
            
            # Check for theme
            if "theme_gray()" in code or "theme_grey()" in code:
                optimizations.append("Replace theme_gray() with theme_minimal(base_size=14)")
                optimized_code = optimized_code.replace("theme_gray()", "theme_minimal(base_size=14)")
                optimized_code = optimized_code.replace("theme_grey()", "theme_minimal(base_size=14)")
            elif "theme(" not in code and "ggplot(" in code:
                optimizations.append("Add theme_minimal(base_size=14) for better aesthetics")
            
            # Check for ggsave
            if "ggsave(" in code:
                if "dpi=" not in code:
                    optimizations.append("Add dpi=800 to ggsave() for publication quality")
                if "width=" not in code or "height=" not in code:
                    optimizations.append("Specify width=5, height=4 in ggsave() for optimal dimensions")
            elif "ggplot(" in code:
                optimizations.append("Add ggsave() with width=5, height=4, dpi=800")
            
            # Check for color scales
            if "ggplot(" in code and "color=" in code and "scale_color" not in code and "scale_colour" not in code:
                optimizations.append("Add scale_color_brewer(palette='Set2') for better categorical colors")
            
            # Check for continuous color scales
            if "ggplot(" in code and "fill=" in code and "scale_fill" not in code:
                if "continuous" in code.lower() or "numeric" in code.lower():
                    optimizations.append("Consider scale_fill_viridis_c() for continuous data")
                else:
                    optimizations.append("Add scale_fill_brewer(palette='Set2') for categorical data")
            
            # Check for point size
            if "geom_point(" in code and "size=" not in code:
                optimizations.append("Set size=2.5 in geom_point() for better visibility")
            
            # Check for line width
            if "geom_line(" in code:
                if "linewidth=" not in code and "size=" not in code:
                    optimizations.append("Set linewidth=0.8 in geom_line() for better visibility")
            
            # Provide style guide reference
            style_notes = [
                "Following publication-ready ggplot2 best practices:",
                "- Muted color palettes (Set2, viridis)",
                "- Clear typography (base_size ≥ 14pt)",
                "- Optimal export dimensions (5x4 inches)",
                "- High resolution (dpi=800)"
            ]
            
            return {
                "ok": True,
                "data": {
                    "original_code": code,
                    "optimized_code": optimized_code if optimizations else code,
                    "optimizations": optimizations,
                    "style_notes": style_notes,
                    "improvements_found": len(optimizations)
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "ANALYSIS_ERROR",
                    "message": f"Failed to analyze code: {str(e)}"
                }
            }
    
    async def handle_inspect_R_objects(self, objects: Optional[List[str]] = None, 
                                       str_max_level: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        """Inspect R objects from the last saved session"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        # Check if .RData exists
        rdata_file = self.workdir / ".RData"
        if not rdata_file.exists():
            return {
                "ok": False,
                "error": {
                    "code": "NO_RDATA",
                    "message": "No .RData file found in working directory",
                    "hints": ["Run an R script with save_rdata=true first", "Check if R session was saved"]
                }
            }
        
        # Build R code to inspect objects
        r_code = f"""
        # Load saved workspace
        load(".RData")
        
        # Get all objects if none specified
        all_objects <- ls()
        """
        
        if objects:
            # Inspect specific objects
            r_code += f"""
            requested_objects <- c({', '.join([f'"{obj}"' for obj in objects])})
            missing <- setdiff(requested_objects, all_objects)
            if (length(missing) > 0) {{
                cat("Warning: Objects not found:", paste(missing, collapse=", "), "\\n")
            }}
            objects_to_inspect <- intersect(requested_objects, all_objects)
            """
        else:
            r_code += """
            objects_to_inspect <- all_objects
            """
        
        r_code += f"""
        # Inspect each object
        for (obj_name in objects_to_inspect) {{
            cat("\\n=== Object:", obj_name, "===\\n")
            obj <- get(obj_name)
            
            # Basic info
            cat("Class:", paste(class(obj), collapse=", "), "\\n")
            cat("Type:", typeof(obj), "\\n")
            
            # Size info
            if (is.data.frame(obj) || is.matrix(obj)) {{
                cat("Dimensions:", nrow(obj), "x", ncol(obj), "\\n")
            }} else if (is.list(obj)) {{
                cat("Length:", length(obj), "\\n")
            }} else if (is.vector(obj)) {{
                cat("Length:", length(obj), "\\n")
            }}
            
            # Structure
            cat("\\nStructure:\\n")
            str(obj, max.level={str_max_level})
            
            # Summary for data frames
            if (is.data.frame(obj)) {{
                cat("\\nSummary:\\n")
                print(summary(obj))
            }}
            
            # First few elements for vectors
            if (is.vector(obj) && !is.list(obj) && length(obj) > 0) {{
                cat("\\nFirst elements:\\n")
                print(head(obj, 10))
            }}
        }}
        """
        
        # Execute the inspection code
        result = self.run_r_command(["-e", r_code, "--slave"], timeout=timeout_sec)
        
        if result["ok"]:
            logger.info(f"Inspected {len(objects) if objects else 'all'} objects")
            result["data"]["objects_inspected"] = objects if objects else "all"
        
        return result
    
    async def handle_which_R(self) -> Dict[str, Any]:
        """Find R executable in PATH"""
        executable = None
        alternatives = []
        
        # Check for Rscript first (preferred)
        rscript = shutil.which("Rscript")
        if rscript:
            executable = rscript
            alternatives.append(rscript)
        
        r_exe = shutil.which("R")
        if r_exe:
            if not executable:
                executable = r_exe
            alternatives.append(r_exe)
        
        if executable:
            return {
                "ok": True,
                "data": {
                    "executable": executable,
                    "alternatives": alternatives
                }
            }
        else:
            return {
                "ok": False,
                "error": {
                    "code": "R_NOT_FOUND",
                    "message": "R not found in PATH",
                    "hints": ["Install R from https://www.r-project.org/", "Add Rscript or R to your system PATH"]
                }
            }
    
    async def handle_list_R_files(self) -> Dict[str, Any]:
        """List all R files in working directory"""
        ok, error = self.ensure_workdir_set()
        if not ok:
            return {"ok": False, "error": error}
        
        try:
            r_files = []
            # Look for both .R and .r extensions
            for pattern in ["*.R", "*.r"]:
                for item in self.workdir.glob(pattern):
                    if item.is_file() and item.name not in r_files:
                        r_files.append(item.name)
            
            r_files.sort()
            
            return {
                "ok": True,
                "data": {
                    "files": r_files,
                    "primary_file": self.primary_file
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "LIST_ERROR",
                    "message": f"Failed to list R files: {str(e)}"
                }
            }

async def main():
    """Main entry point"""
    # Print ASCII banner
    print_ascii_banner()
    logger.info("Starting PilotR MCP server...")
    
    # Create server instance
    server = Server("PilotR")
    pilotr = PilotRServer()
    
    # Register list_tools handler
    @server.list_tools()
    async def list_tools():
        logger.debug("Listing tools...")
        return [
            Tool(name="set_workdir", description="Set the working directory for all R operations", 
                 inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "create": {"type": "boolean", "default": True}}, "required": ["path"]}),
            Tool(name="get_state", description="Get current PilotR state and configuration", 
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="create_R_file", description="Create a new R script file", 
                 inputSchema={"type": "object", "properties": {"filename": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}, "scaffold": {"type": "boolean", "default": True}}, "required": ["filename"]}),
            Tool(name="rename_R_file", description="Rename an R script file", 
                 inputSchema={"type": "object", "properties": {"old_name": {"type": "string"}, "new_name": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, "required": ["old_name", "new_name"]}),
            Tool(name="set_primary_file", description="Set the primary R script file", 
                 inputSchema={"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}),
            Tool(name="append_R_code", description="Append R code to an existing script file", 
                 inputSchema={"type": "object", "properties": {"code": {"type": "string"}, "filename": {"type": "string"}, "ensure_trailing_newline": {"type": "boolean", "default": True}}, "required": ["code"]}),
            Tool(name="write_R_code", description="Write R code to a script file", 
                 inputSchema={"type": "object", "properties": {"code": {"type": "string"}, "filename": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}, "use_scaffold_header": {"type": "boolean", "default": True}}, "required": ["code"]}),
            Tool(name="run_R_script", description="Execute an R script file", 
                 inputSchema={"type": "object", "properties": {"filename": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "timeout_sec": {"type": "integer", "default": 120}, "save_rdata": {"type": "boolean", "default": True}}}),
            Tool(name="run_R_expression", description="Execute a single R expression", 
                 inputSchema={"type": "object", "properties": {"expr": {"type": "string"}, "timeout_sec": {"type": "integer", "default": 60}}, "required": ["expr"]}),
            Tool(name="list_exports", description="List files in the working directory", 
                 inputSchema={"type": "object", "properties": {"glob": {"type": "string", "default": "*"}, "sort_by": {"type": "string", "default": "mtime"}, "descending": {"type": "boolean", "default": True}, "limit": {"type": "integer", "default": 200}}}),
            Tool(name="read_export", description="Read a file from the working directory", 
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "max_bytes": {"type": "integer", "default": 50000}, "as_text": {"type": "boolean", "default": True}, "encoding": {"type": "string", "default": "utf-8"}}, "required": ["name"]}),
            Tool(name="preview_table", description="Preview a CSV/TSV file as a table", 
                 inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "delimiter": {"type": "string", "default": ","}, "max_rows": {"type": "integer", "default": 50}}, "required": ["name"]}),
            Tool(name="ggplot_style_check", description="Analyze and optimize ggplot code for publication-quality styling", 
                 inputSchema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}),
            Tool(name="inspect_R_objects", description="Inspect R objects from the last saved session", 
                 inputSchema={"type": "object", "properties": {"objects": {"type": "array", "items": {"type": "string"}}, "str_max_level": {"type": "integer", "default": 1}, "timeout_sec": {"type": "integer", "default": 60}}}),
            Tool(name="which_R", description="Find R executable in PATH", 
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="list_R_files", description="List all R script files in the working directory", 
                 inputSchema={"type": "object", "properties": {}})
        ]
    
    # Register call_tool handler
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        logger.debug(f"Calling tool: {name} with arguments: {arguments}")
        try:
            if name == "set_workdir":
                result = await pilotr.handle_set_workdir(**arguments)
            elif name == "get_state":
                result = await pilotr.handle_get_state()
            elif name == "create_R_file":
                result = await pilotr.handle_create_R_file(**arguments)
            elif name == "rename_R_file":
                result = await pilotr.handle_rename_R_file(**arguments)
            elif name == "set_primary_file":
                result = await pilotr.handle_set_primary_file(**arguments)
            elif name == "append_R_code":
                result = await pilotr.handle_append_R_code(**arguments)
            elif name == "write_R_code":
                result = await pilotr.handle_write_R_code(**arguments)
            elif name == "run_R_script":
                result = await pilotr.handle_run_R_script(**arguments)
            elif name == "run_R_expression":
                result = await pilotr.handle_run_R_expression(**arguments)
            elif name == "list_exports":
                result = await pilotr.handle_list_exports(**arguments)
            elif name == "read_export":
                result = await pilotr.handle_read_export(**arguments)
            elif name == "preview_table":
                result = await pilotr.handle_preview_table(**arguments)
            elif name == "ggplot_style_check":
                result = await pilotr.handle_ggplot_style_check(**arguments)
            elif name == "inspect_R_objects":
                result = await pilotr.handle_inspect_R_objects(**arguments)
            elif name == "which_R":
                result = await pilotr.handle_which_R()
            elif name == "list_R_files":
                result = await pilotr.handle_list_R_files()
            else:
                result = {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {name}"}}
            
            logger.debug(f"Tool {name} result: {result}")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            logger.error(f"Error in tool {name}: {str(e)}")
            logger.error(traceback.format_exc())
            error_result = {
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Internal error: {str(e)}"
                }
            }
            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    # Run server with initialization_options parameter
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server running...")
            initialization_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, initialization_options)
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

