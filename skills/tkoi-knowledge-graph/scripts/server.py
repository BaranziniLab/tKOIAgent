# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.12,<2"]
# ///
"""Read-only MCP tools over the igraph retained in a saved tKOI analysis."""
import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


class GraphWorker:
    def __init__(self):
        self.process = None
        self.responses = None
        self.lock = threading.Lock()

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.responses = queue.Queue()
        self.process = subprocess.Popen(
            [os.environ.get("TKOI_RSCRIPT", "Rscript"), "--vanilla",
             str(Path(__file__).with_name("graph_worker.R"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            encoding="utf-8", bufsize=1,
        )
        process, responses = self.process, self.responses

        def read_output():
            for line in process.stdout:
                responses.put(line)
            responses.put(None)

        threading.Thread(target=read_output, daemon=True).start()

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None

    def call(self, method: str, **params) -> dict[str, Any]:
        with self.lock:
            self.start()
            try:
                self.process.stdin.write(json.dumps({"method": method, "params": params}) + "\n")
                self.process.stdin.flush()
                line = self.responses.get(timeout=120)
                if line is None:
                    raise RuntimeError("R worker stopped. Check R, tkoi >= 1.3.0 and jsonlite; then reconnect.")
                response = json.loads(line)
            except (queue.Empty, BrokenPipeError, json.JSONDecodeError) as error:
                self.close()
                raise RuntimeError("R worker failed or timed out; reconnect the analysis.") from error
            if not response["ok"]:
                raise ValueError(response["error"])
            return response["data"]


worker = GraphWorker()
atexit.register(worker.close)
mcp = FastMCP("tkoi-graph", instructions=(
    "Connect a tkoi >= 1.3.0 saved analysis.rds. Pass its analysis_id to every query. "
    "All graph evidence comes from the igraph stored in that result; no remote graph is queried."
))
readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=readonly)
def connect_analysis(path: str) -> dict[str, Any]:
    """Connect an absolute analysis.rds path. Return its identity and stored graph counts.

    Replaces this server's previous connection. Results lacking their original graph are refused.
    """
    return worker.call("connect_analysis", path=path)


@mcp.tool(annotations=readonly)
def get_graph_schema(analysis_id: str) -> dict[str, Any]:
    """Inspect actual node/edge attributes, relation types, counts and enrichment categories."""
    return worker.call("get_graph_schema", analysis_id=analysis_id)


@mcp.tool(annotations=readonly)
def search_nodes(analysis_id: str, query: str, node_type: str | None = None,
                 limit: int = 25) -> dict[str, Any]:
    """Find exact graph node IDs by identifier or saved annotation; at most 1000 matches."""
    return worker.call("search_nodes", analysis_id=analysis_id, query=query, node_type=node_type, limit=limit)


@mcp.tool(annotations=readonly)
def get_node_neighbors(analysis_id: str, node_id: str, hops: int = 1,
                       limit: int = 100) -> dict[str, Any]:
    """Traverse 1-3 layers of the analysis graph, returning nodes, hop counts and real edge attributes.

    Includes the source; limit is 1-1000 nodes. Edge output is capped at 1000 with explicit truncation.
    """
    return worker.call("get_node_neighbors", analysis_id=analysis_id, node_id=node_id, hops=hops, limit=limit)


@mcp.tool(annotations=readonly)
def get_path_between_nodes(analysis_id: str, source_id: str, target_id: str,
                           max_hops: int = 3) -> dict[str, Any]:
    """Return one unweighted shortest path of at most 1-6 hops, using this analysis's edges only."""
    return worker.call("get_path_between_nodes", analysis_id=analysis_id,
                       source_id=source_id, target_id=target_id, max_hops=max_hops)


@mcp.tool(annotations=readonly)
def get_enrichment_results(analysis_id: str, node_type: str, limit: int = 25) -> dict[str, Any]:
    """Read a saved enrichment category, preserving tKOI ranking and reporting truncated rows."""
    return worker.call("get_enrichment_results", analysis_id=analysis_id, node_type=node_type, limit=limit)


if __name__ == "__main__":
    mcp.run(transport="stdio")
