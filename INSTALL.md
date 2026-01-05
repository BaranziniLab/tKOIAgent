# tKOIAgent Installation Guide

Quick installation guide for getting tKOIAgent MCP server running with Claude Desktop.

## Installation Method

You can install tKOIAgent using either:
- **Option A: uv (Recommended)** - Fast, modern Python package manager
- **Option B: pip** - Traditional Python package manager

## Option A: Install with uv (Recommended)

### 1. Install uv
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install System Dependencies

#### macOS
```bash
# Install R
brew install r
```

#### Linux (Ubuntu/Debian)
```bash
# Install Python 3.10+ and R
sudo apt-get update
sudo apt-get install python3.10 python3-pip r-base
```

### 3. Setup Project with uv
```bash
cd /Users/wgu/Desktop/tKOIAgent

# Install dependencies (creates virtual environment automatically)
uv sync

# Install R packages
Rscript -e 'install.packages(c("jsonlite", "devtools", "ggplot2", "tidyverse"), repos="https://cloud.r-project.org")'
```

### 4. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tKOIAgent": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/wgu/Desktop/tKOIAgent",
        "run",
        "tKOIAgent"
      ]
    }
  }
}
```

**Note**:
- When using the .mcpb bundle, configuration parameters can be customized through Claude Desktop's Settings → Extensions → tKOIAgent UI.
- For manual installations, you can add environment variables to the `"env"` section. See README.md for all configuration options.

### 5. Restart Claude Desktop and test!

---

## Option B: Install with pip

## Step 1: Install System Dependencies

### macOS
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install R
brew install r

# Install Python 3.9+
brew install python@3.9
```

### Linux (Ubuntu/Debian)
```bash
# Install R
sudo apt-get update
sudo apt-get install r-base

# Install Python 3.9+
sudo apt-get install python3.9 python3-pip python3-venv
```

### Windows
1. Install R from https://cran.r-project.org/bin/windows/base/
2. Install Python 3.9+ from https://www.python.org/downloads/

## Step 2: Setup Python Environment

```bash
cd /Users/wgu/Desktop/tKOIAgent

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install Python dependencies
pip install -r requirements.txt
```

## Step 3: Install R Packages

Open R console and run:

```r
# Install required R packages
install.packages(c("jsonlite", "devtools", "ggplot2", "reshape2", "tidyverse"),
                repos = "https://cloud.r-project.org")

# Install tKOI package (update with actual repository when available)
# devtools::install_github("user/tkoi")
```

## Step 4: Configure Claude Desktop

### macOS

1. Open Claude Desktop config file:
   ```bash
   code ~/Library/Application\ Support/Claude/claude_desktop_config.json
   # OR
   open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. Add tKOIAgent configuration:
   ```json
   {
     "mcpServers": {
       "tKOIAgent": {
         "command": "python3",
         "args": [
           "/Users/wgu/Desktop/tKOIAgent/server.py"
         ],
         "env": {
           "PYTHONPATH": "/Users/wgu/Desktop/tKOIAgent"
         }
       }
     }
   }
   ```

   **Optional**: Add custom parameters to the `"env"` section:
   ```json
   "env": {
     "PYTHONPATH": "/Users/wgu/Desktop/tKOIAgent",
     "TKOI_DEFAULT_WORKDIR": "~/Desktop",
     "TKOI_LOGFC_THRESHOLD": "1.5",
     "TKOI_DAMPING_FACTOR": "0.9"
   }
   ```

### Windows

1. Open Claude Desktop config file:
   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. Add configuration with Windows paths:
   ```json
   {
     "mcpServers": {
       "tKOIAgent": {
         "command": "python",
         "args": [
           "C:\\path\\to\\tKOIAgent\\server.py"
         ],
         "env": {
           "PYTHONPATH": "C:\\path\\to\\tKOIAgent"
         }
       }
     }
   }
   ```

   **Optional**: Add custom parameters to the `"env"` section (see macOS example above).

## Step 5: Test Installation

### Test Server Standalone

```bash
cd /Users/wgu/Desktop/tKOIAgent
source venv/bin/activate

# Test STDIO protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python3 server.py

# Should output JSON-RPC response listing all tools
```

### Test with Claude Desktop

1. **Completely quit Claude Desktop** (not just close window)
   - macOS: Cmd+Q or right-click dock icon → Quit
   - Windows: File → Exit

2. **Restart Claude Desktop**

3. **Verify MCP server loaded**
   - Look for hammer icon (🔨) in Claude input box
   - Type: "List all available tKOI tools"
   - Should see 11 tools listed

## Step 6: Verify Tools Work

Try these test commands in Claude Desktop:

```
Check if R is installed
```

```
Check if tKOI is installed
```

If successful, you should see status reports!

## Troubleshooting

### Server Not Loading

**Check Claude Desktop logs (macOS):**
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Common issues:**
1. Python virtual environment not activated
2. Wrong path in config file
3. Missing dependencies
4. Permissions issue with server.py

**Fix permissions:**
```bash
chmod +x /Users/wgu/Desktop/tKOIAgent/server.py
```

### R Not Found

**Verify R installation:**
```bash
which R
R --version
```

**Fix PATH:**
```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
```

### Import Errors

**Ensure virtual environment is activated and dependencies installed:**
```bash
cd /Users/wgu/Desktop/tKOIAgent
source venv/bin/activate
pip list  # Should show all required packages
pip install -r requirements.txt  # Reinstall if needed
```

### SPOKE Connection Failed

This is expected if SPOKE dev instance is down or network issues exist.
The server will continue to work without SPOKE integration.

## Next Steps

Once installed:

1. **Prepare sample data** - Gene expression file (CSV/Excel)
2. **Test validation** - "Validate my data file at /path/to/file.csv"
3. **Convert gene IDs** - "Convert gene IDs to human Ensembl format"
4. **Run analysis** - "Run tKOI analysis on my data"
5. **Generate plots** - "Create volcano plot from analysis results"

## Getting Help

- See [README.md](README.md) for detailed documentation
- Check tool descriptions in Claude Desktop
- Review error messages in logs

---

**Installation complete!** 🎉

You can now use tKOIAgent for transcriptomics analysis through Claude Desktop.
