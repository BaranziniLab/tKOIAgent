"""Exercise the real MCP stdio transport and R worker on a custom enrichment graph."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    fixture = Path(sys.argv[1]).resolve()
    expected = json.loads((fixture / 'expected.json').read_text())
    server = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / 'skills/tkoi-knowledge-graph/scripts/server.py'
    params = StdioServerParameters(command=sys.executable, args=[str(server)], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            assert len((await client.list_tools()).tools) == 6
            async def call(name, error=False, **kwargs):
                result = await client.call_tool(name, kwargs)
                assert bool(result.isError) == error, result
                if error:
                    return
                return result.structuredContent or json.loads(result.content[0].text)
            connection = await call('connect_analysis', path=str(fixture / 'run/analysis.rds'))
            identity = connection['analysis_id']
            assert connection['vertices'] == expected['vertices']
            schema = await call('get_graph_schema', analysis_id=identity)
            assert schema['edges'] == expected['edges']
            assert set(schema['edge_types']) == {'FIXTURE_LAYER_A', 'FIXTURE_LAYER_B'}
            assert 'Gene' in schema['node_types'], schema['node_types']
            nodes = expected['nodes']
            found = await call('search_nodes', analysis_id=identity, query=nodes[0], node_type='Gene')
            assert found['total_matches'] == 1
            neighbors = await call('get_node_neighbors', analysis_id=identity, node_id=nodes[0], hops=2)
            assert len(neighbors['nodes']) == 5
            assert all(e['attr_edge_type'].startswith('FIXTURE_') for e in neighbors['edges'])
            path = await call('get_path_between_nodes', analysis_id=identity, source_id=nodes[0], target_id=nodes[2])
            assert path['found'] and path['path_length'] == 2
            limited = await call('get_node_neighbors', analysis_id=identity, node_id=nodes[0], hops=2, limit=2)
            assert limited['nodes_truncated'] and len(limited['nodes']) == 2
            await call('get_enrichment_results', analysis_id=identity, node_type='Gene')
            await call('get_graph_schema', analysis_id='wrong-analysis', error=True)
            await call('get_node_neighbors', analysis_id=identity, node_id='NOT_IN_THIS_GRAPH', error=True)
            await call('connect_analysis', path=str(fixture / 'legacy.rds'), error=True)
            await call('get_graph_schema', analysis_id=identity, error=True)
            mutable = fixture / 'mutable.rds'
            shutil.copyfile(fixture / 'run/analysis.rds', mutable)
            reconnected = await call('connect_analysis', path=str(mutable))
            with mutable.open('ab') as stream:
                stream.write(b'changed')
            await call('get_graph_schema', analysis_id=reconnected['analysis_id'], error=True)
    print('MCP smoke test passed: six tools, exact graph edges, bounded traversal, identity and legacy guards.')

asyncio.run(main())
