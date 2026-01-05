# Intelligent tKOIAgent Workflow Enhancement

## Overview
Transform tKOIAgent from a rigid analysis tool into an intelligent, context-aware system that uses Claude (LLM) to interpret results, identify interesting findings, and generate meaningful reports.

## Workflow Changes

### Current Workflow
```
1. Validate data
2. Clean data → cleaned.csv
3. Convert gene IDs (if needed)
4. Run tKOI analysis → Excel files + RDA
5. Generate visualizations → PNG plots
6. Generate report → templated markdown
```

### New Intelligent Workflow
```
1. Validate data
2. Clean data → cleaned.csv + significant_genes.csv (FDR < 0.05)
3. Convert gene IDs (if needed)
4. Run tKOI analysis → Excel files + RDA
5. Extract top 10 nodes from each modality
6. **[NEW]** Use Claude to interpret top nodes and identify interesting ones
7. **[NEW]** Network traversal: Find genes related to interesting nodes (2 hops)
8. Generate visualizations → PNG plots
9. **[NEW]** LLM-generated report with contextualization
```

## Implementation Tasks

### Task 1: Save FDR-Significant Genes
**File**: `tools/data_processing.py`

**Function**: `clean_data_file()`

**Changes**:
- After cleaning, filter for FDR-significant genes (FDR <= 0.05)
- Save as `{basename}_significant.csv`
- Return path in response

**Implementation**:
```python
# After cleaning
if 'fdr' in df_clean.columns or 'FDR' in df_clean.columns:
    fdr_col = 'fdr' if 'fdr' in df_clean.columns else 'FDR'
    df_sig = df_clean[df_clean[fdr_col] <= 0.05]

    sig_file = working_dir / f"{output_path_obj.stem}_significant.csv"
    df_sig.to_csv(sig_file, index=True)

    report['significant_genes_file'] = str(sig_file)
    report['significant_count'] = len(df_sig)
```

### Task 2: Extract Top Nodes
**File**: `tools/analysis.py`

**New Function**: `extract_top_nodes()`

```python
def extract_top_nodes(working_dir: Path, top_n: int = 10) -> dict:
    """
    Extract top N nodes from each modality in tKOI results.

    Returns:
        {
            'Anatomy': [{'name': 'Brain', 'fdr': 0.001, ...}, ...],
            'Pathway': [...],
            ...
        }
    """
    summary_file = working_dir / "tkoi_summary.xlsx"

    modalities = [
        "Anatomy", "CellType", "Complex", "Pathway", "Disease",
        "BiologicalProcess", "CellularComponent", "MolecularFunction", "Gene"
    ]

    top_nodes = {}

    for modality in modalities:
        try:
            df = pd.read_excel(summary_file, sheet_name=modality)
            # Sort by FDR (ascending)
            df_sorted = df.sort_values('fdr').head(top_n)
            top_nodes[modality] = df_sorted.to_dict('records')
        except:
            continue

    return top_nodes
```

### Task 3: Intelligent Node Interpretation
**File**: `tools/analysis.py`

**New Function**: `interpret_top_nodes()`

```python
def interpret_top_nodes(top_nodes: dict, study_context: dict) -> dict:
    """
    Use Claude to interpret top nodes and identify interesting ones.

    This function presents the top nodes to Claude and asks:
    1. Which nodes are most interesting/unexpected?
    2. What biological processes might they represent?
    3. Which nodes warrant network traversal?

    Returns:
        {
            'interesting_nodes': [
                {'modality': 'Pathway', 'name': 'Oxidative Phosphorylation', 'reason': '...'},
                ...
            ],
            'interpretation': "..."
        }
    """
    # Format top nodes as context
    context = format_top_nodes_for_llm(top_nodes, study_context)

    # This will be handled by the MCP server itself
    # The tool will return the formatted context to Claude
    # Claude (in the conversation) will then interpret

    return {
        'nodes_context': context,
        'top_nodes': top_nodes
    }
```

### Task 4: Network Traversal
**File**: `tools/knowledge_graph.py`

**New Function**: `traverse_for_interesting_nodes()`

```python
def traverse_for_interesting_nodes(
    interesting_nodes: list,
    significant_genes_file: str,
    max_hops: int = 2
) -> dict:
    """
    Perform network traversal to understand why nodes are ranked highly.

    For each interesting node:
    1. Find genes from significant_genes.csv that are related
    2. Traverse up to max_hops in SPOKE
    3. Identify connecting paths and intermediate nodes

    Returns:
        {
            'node_name': {
                'related_genes': [...],
                'paths': [...],
                'intermediate_nodes': [...],
                'explanation': "..."
            }
        }
    """
```

### Task 5: LLM-Based Report Generation
**File**: `tools/reporting.py`

**Complete Rewrite**: `generate_analysis_report()`

**Old Approach**:
- Template-based markdown
- Rigid structure
- Programmatic output only

**New Approach**:
```python
def generate_analysis_report(
    working_dir: str,
    analysis_params: dict,
    top_nodes: dict,
    interesting_nodes: list,
    traversal_results: dict
) -> dict:
    """
    Generate LLM-based analysis report.

    Instead of rigid template, provide Claude with:
    1. Top 10 FDR-significant genes (raw input)
    2. Top nodes from each modality
    3. Interesting nodes identified
    4. Network traversal results
    5. Analysis parameters

    Let Claude generate:
    - Study summary
    - Methods description
    - Results interpretation
    - Biological contextualization
    - Key findings
    """

    # Read significant genes
    sig_genes_file = Path(working_dir) / "*_significant.csv"
    sig_genes_df = pd.read_csv(sig_genes_file)
    top_sig_genes = sig_genes_df.head(10).to_dict('records')

    # Prepare context for LLM
    context = {
        'analysis_params': analysis_params,
        'top_significant_genes': top_sig_genes,
        'top_nodes_by_modality': top_nodes,
        'interesting_nodes': interesting_nodes,
        'network_traversal': traversal_results,
        'output_files': list_output_files(working_dir)
    }

    # Return context for Claude to generate report
    return {
        'success': True,
        'report_context': context,
        'note': "Use this context to generate a comprehensive analysis report"
    }
```

### Task 6: Update Workflow Orchestration
**File**: `server.py` (tool descriptions)

**Update Tool Descriptions**:

1. `tkoi_run_analysis`:
   - Add note: "After analysis, use extract_top_nodes to get results"

2. Add new tool: `tkoi_extract_top_nodes`
   - Extract top N nodes from analysis results
   - Returns formatted context for Claude

3. Add new tool: `tkoi_traverse_interesting_nodes`
   - Perform network traversal for interesting nodes
   - Requires significant genes file

4. Update: `tkoi_generate_analysis_report`
   - Now returns context for LLM-based report generation
   - Claude will write the actual report

## Expected User Interaction

```
User: "Run tKOI analysis on my data"

Claude:
1. Validates data
2. Cleans data (saves cleaned + significant genes)
3. Runs tKOI analysis
4. Extracts top 10 nodes from each modality
5. [Shows top nodes to user]
6. "I found these top-ranked nodes. Let me identify the most interesting ones..."
7. [Interprets nodes, identifies interesting ones]
8. "I'll now perform network traversal to understand why these nodes are significant..."
9. [Runs traversal]
10. "Based on the analysis, here's what I found..." [LLM-generated summary]
11. "Shall I generate a full report?"
12. [Generates comprehensive LLM-based report]
```

## Benefits

1. **Intelligent Interpretation**: Claude identifies truly interesting findings
2. **Contextualized Results**: Network traversal explains why nodes are important
3. **Natural Language Reports**: No more rigid templates
4. **Interactive Analysis**: User can guide interpretation
5. **Biological Insights**: LLM provides context that templates cannot

## Files to Modify

1. `tools/data_processing.py` - Save significant genes
2. `tools/analysis.py` - Extract top nodes, interpretation logic
3. `tools/knowledge_graph.py` - Network traversal for nodes
4. `tools/reporting.py` - Complete rewrite for LLM-based reports
5. `server.py` - New tool registrations and descriptions
6. `manifest.json` - New tool definitions

## Implementation Order

1. ✅ Save FDR-significant genes in `clean_data_file()`
2. ✅ Create `extract_top_nodes()` function
3. ✅ Add context extraction after analysis
4. ✅ Create `traverse_interesting_nodes()` function
5. ✅ Rewrite `generate_analysis_report()` for LLM
6. ✅ Register new tools in `server.py`
7. ✅ Update tool descriptions
8. ✅ Test workflow
9. ✅ Rebuild bundle
