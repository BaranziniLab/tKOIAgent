# tKOIAgent Naming Conventions

This document explains the different naming conventions used throughout the tKOIAgent project.

## Naming Standards

### 1. **tKOIAgent** (CamelCase with lowercase 't')
**Usage**: MCP server name, project references in documentation

**Examples**:
- MCP server name: `FastMCP("tKOIAgent")`
- Documentation titles: "tKOIAgent - MCP Server for Transcriptomics Analysis"
- General references: "tKOIAgent provides 11 specialized tools..."
- Git repository: `tKOIAgent` (folder name)

**Locations**:
- [server.py](server.py:41) - FastMCP server initialization
- [README.md](README.md:1) - Title and throughout documentation
- All documentation files (INSTALL.md, PROJECT_SUMMARY.md)
- Tool descriptions and user-facing text

### 2. **tKOI** (CamelCase with lowercase 't')
**Usage**: R package name and its full expansion

**Full Name**: Transcriptomics Knowledge graph-driven Omics Integration

**Examples**:
- "the tKOI R package"
- "tKOI network propagation"
- "tKOI analysis"
- "tKOI: Transcriptomics Knowledge graph-driven Omics Integration"

**Locations**:
- Documentation explaining the R package
- Citations and references
- Technical descriptions

### 3. **tkoi-agent** (lowercase with hyphen)
**Usage**: Python package name and CLI script name

**Examples**:
- Package name in `pyproject.toml`: `name = "tkoi-agent"`
- Script entry point: `tkoi-agent = "server:main"`
- CLI command: `uv run tkoi-agent`
- Claude Desktop config: `"command": "uv", "args": ["run", "tkoi-agent"]`

**Locations**:
- [pyproject.toml](pyproject.toml:2) - Package name
- [pyproject.toml](pyproject.toml:19) - Script entry point
- Claude Desktop JSON configs
- Command-line usage

**Rationale**: Python package naming convention (PEP 423) recommends lowercase with hyphens

### 4. **tkoi_** prefix (lowercase with underscore)
**Usage**: Python function and tool names

**Examples**:
- Tool names: `tkoi_check_r_installation`, `tkoi_validate_data_file`
- Function names follow Python naming conventions (snake_case)

**Locations**:
- All MCP tool functions in [server.py](server.py)
- Tool implementations in `tools/` directory

**Rationale**: Python naming convention (PEP 8) for functions

## Quick Reference Table

| Context | Naming | Example | File |
|---------|--------|---------|------|
| MCP Server Name | **tKOIAgent** | `FastMCP("tKOIAgent")` | server.py |
| Documentation | **tKOIAgent** | "tKOIAgent provides..." | README.md |
| R Package | **tKOI** | "tKOI R package" | All docs |
| Python Package | **tkoi-agent** | `name = "tkoi-agent"` | pyproject.toml |
| CLI Script | **tkoi-agent** | `uv run tkoi-agent` | Terminal |
| JSON Config Key | **tkoi-agent** | `"tkoi-agent": {...}` | claude_desktop_config.json |
| Tool Names | **tkoi_*** | `tkoi_check_r_installation` | server.py |

## Common Mistakes to Avoid

❌ **Incorrect**:
- "TKOI Agent" (all caps TKOI)
- "tkoi agent" (lowercase, separated)
- "TKOIAgent" (capital T)
- "tkoiAgent" (different capitalization)
- "tkoi_agent" (underscore in package name for pip/uv)

✅ **Correct**:
- "tKOIAgent" (for the MCP server)
- "tKOI" (for the R package)
- "tkoi-agent" (for Python package/CLI)
- "tkoi_*" (for function names)

## Verification

Run this command to verify naming conventions:
```bash
cd /Users/wgu/Desktop/tKOIAgent
grep -r "TKOI Agent\|tkoi agent" . --include="*.md" --include="*.py" --exclude-dir=.venv
```

Should return no results (except in this file as examples).

## Why These Conventions?

1. **tKOIAgent (CamelCase)**: Professional, consistent with MCP server naming
2. **tKOI (CamelCase)**: Matches the R package naming convention
3. **tkoi-agent (kebab-case)**: Follows Python package naming standards (PEP 423)
4. **tkoi_* (snake_case)**: Follows Python function naming standards (PEP 8)

---

**Last Updated**: December 28, 2025
**Maintained By**: tKOIAgent Development Team
