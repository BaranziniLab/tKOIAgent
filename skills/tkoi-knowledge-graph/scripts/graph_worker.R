# Private JSON-lines worker. MCP protocol is handled by the official Python SDK.
options(warn = 1)
if (!requireNamespace("tkoi", quietly = TRUE) || utils::packageVersion("tkoi") < "1.3.0") {
  stop("Install tkoi >= 1.3.0 using the tkoi-analysis setup skill.")
}
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Install jsonlite using the setup skill.")
state = new.env(parent = emptyenv())
state$analysis = NULL

bounded = function(x, maximum, name, minimum = 1) {
  if (!is.numeric(x) || length(x) != 1 || !is.finite(x) || x < minimum ||
      x > maximum || x != floor(x)) stop(name, " must be an integer in [", minimum, ", ", maximum, "].")
  as.integer(x)
}
node_index = function(node_id) {
  if (!is.character(node_id) || length(node_id) != 1) stop("Supply one exact node_id from search_nodes.")
  index = match(node_id, state$nodes$node_id)
  if (is.na(index)) stop("Node is not in the connected analysis graph: ", node_id)
  index
}
connection = function(id) {
  if (is.null(state$analysis)) stop("Call connect_analysis with the saved analysis.rds first.")
  if (!identical(id, state$id)) stop("Analysis ID does not match the current connection. Reconnect the requested analysis.")
  if (!file.exists(state$path) || !identical(unname(tools::md5sum(state$path)), state$id)) {
    stop("Saved analysis changed after connection. Reconnect it before querying.")
  }
}
node_rows = function(index) state$nodes[index, , drop = FALSE]
edge_rows = function(graph, ids) {
  if (!length(ids)) return(data.frame(from = character(), to = character()))
  ends = igraph::ends(graph, ids, names = TRUE)
  out = data.frame(from = ends[, 1], to = ends[, 2], stringsAsFactors = FALSE)
  for (name in igraph::edge_attr_names(graph)) {
    out[[paste0("attr_", name)]] = igraph::edge_attr(graph, name, index = ids)
  }
  out
}
connect_analysis = function(path) {
  state$analysis = NULL
  if (!is.character(path) || length(path) != 1 || !grepl("^(/|[A-Za-z]:[/\\\\])", path)) {
    stop("Supply an absolute path to analysis.rds.")
  }
  path = normalizePath(path, mustWork = TRUE)
  id = unname(tools::md5sum(path))
  result = readRDS(path)
  graph = tkoi::get_analysis_graph(result)
  if (!identical(unname(tools::md5sum(path)), id)) stop("Analysis changed while it was loading; reconnect.")
  attrs = igraph::vertex_attr_names(graph)
  names = as.character(igraph::V(graph)$name)
  identifiers = if ("identifier" %in% attrs) as.character(igraph::V(graph)$identifier) else names
  type_attr = intersect(c("labels", "label"), attrs)
  types = if (length(type_attr)) as.character(igraph::vertex_attr(graph, type_attr[1])) else rep("Unknown", length(names))
  for (character in c("[", "]", "'", '"', " ")) types = gsub(character, "", types, fixed = TRUE)
  nodes = data.frame(node_id = names, identifier = identifiers, node_type = types,
                     display_name = identifiers, ensembl = NA_character_, stringsAsFactors = FALSE)
  for (table in result@network_summary_statistics) {
    if (!nrow(table)) next
    idx = match(table$node_id, nodes$node_id)
    label = intersect(c("name", "description", "gene_name"), names(table))
    if (length(label)) {
      values = as.character(table[[label[1]]])
      good = !is.na(idx) & !is.na(values) & nzchar(values)
      nodes$display_name[idx[good]] = values[good]
    }
    if ("ensembl" %in% names(table)) nodes$ensembl[idx[!is.na(idx)]] = as.character(table$ensembl[!is.na(idx)])
  }
  state$path = path
  state$id = id
  state$nodes = nodes
  state$graph = graph
  state$analysis = result
  list(analysis_id = id, path = path, vertices = igraph::vcount(graph), edges = igraph::ecount(graph),
       directed = igraph::is_directed(graph), traversal_mode = "all (undirected, matching tKOI enrichment)",
       fingerprint = "MD5 of the saved analysis file; an identity check, not an authentication signature")
}
dispatch = function(method, p) {
  if (method == "connect_analysis") return(connect_analysis(p$path))
  connection(p$analysis_id)
  graph = state$graph
  answer = switch(method,
    get_graph_schema = list(
      vertices = igraph::vcount(graph), edges = igraph::ecount(graph), directed = igraph::is_directed(graph),
      node_types = as.list(table(state$nodes$node_type)), vertex_attributes = igraph::vertex_attr_names(graph),
      edge_attributes = igraph::edge_attr_names(graph),
      edge_types = if ("edge_type" %in% igraph::edge_attr_names(graph)) as.list(table(igraph::E(graph)$edge_type)) else list(),
      enrichment_categories = names(state$analysis@network_summary_statistics), traversal_mode = "all",
      note = "Only stored graph attributes describe edges. An unweighted shortest path is not causal or signed evidence."
    ),
    search_nodes = {
      limit = bounded(p$limit, 1000, "limit")
      if (!is.character(p$query) || length(p$query) != 1) stop("query must be a string.")
      nodes = state$nodes
      hit = rep(FALSE, nrow(nodes))
      for (field in c("node_id", "identifier", "display_name", "ensembl")) {
        hit = hit | (!is.na(nodes[[field]]) & grepl(tolower(p$query), tolower(nodes[[field]]), fixed = TRUE))
      }
      if (!is.null(p$node_type)) hit = hit & nodes$node_type == p$node_type
      indices = which(hit)
      list(nodes = node_rows(head(indices, limit)), total_matches = length(indices), truncated = length(indices) > limit)
    },
    get_node_neighbors = {
      hops = bounded(p$hops, 3, "hops")
      limit = bounded(p$limit, 1000, "limit")
      visited = node_index(p$node_id)
      distances = 0L
      frontier = visited
      truncated = FALSE
      for (hop in seq_len(hops)) {
        next_frontier = integer()
        for (vertex in frontier) {
          candidates = setdiff(as.integer(igraph::neighbors(graph, vertex, mode = "all")), visited)
          room = limit - length(visited)
          if (length(candidates) > room) truncated = TRUE
          candidates = head(candidates, max(0L, room))
          visited = c(visited, candidates)
          distances = c(distances, rep(hop, length(candidates)))
          next_frontier = c(next_frontier, candidates)
          if (truncated) break
        }
        if (truncated || !length(next_frontier)) break
        frontier = next_frontier
      }
      nodes = node_rows(visited)
      nodes$hops_from_source = distances
      subgraph = igraph::induced_subgraph(graph, visited)
      edge_count = igraph::ecount(subgraph)
      list(nodes = nodes, edges = edge_rows(subgraph, head(seq_len(edge_count), 1000)),
           requested_hops = hops, nodes_truncated = truncated, edges_truncated = edge_count > 1000,
           note = "Includes the source. Truncation means this is a partial neighborhood, not evidence of absent connections.")
    },
    get_path_between_nodes = {
      hops = bounded(p$max_hops, 6, "max_hops")
      source = node_index(p$source_id)
      target = node_index(p$target_id)
      path = suppressWarnings(igraph::shortest_paths(graph, from = source, to = target,
                                                    mode = "all", weights = NA, output = "both"))
      vertices = as.integer(path$vpath[[1]])
      edges = as.integer(path$epath[[1]])
      found = length(vertices) > 0 && length(edges) <= hops
      list(found = found, max_hops = hops,
           nodes = node_rows(if (found) vertices else integer()),
           edges = edge_rows(graph, if (found) edges else integer()),
           path_length = if (found) length(edges) else NULL,
           note = "One unweighted shortest path, ignoring edge direction as in tKOI enrichment. Other paths may exist.")
    },
    get_enrichment_results = {
      limit = bounded(p$limit, 1000, "limit")
      tables = state$analysis@network_summary_statistics
      if (!is.character(p$node_type) || length(p$node_type) != 1 || !p$node_type %in% names(tables)) {
        stop("Choose an enrichment category returned by get_graph_schema.")
      }
      table = tables[[p$node_type]]
      list(node_type = p$node_type, rows = head(table, limit), total_rows = nrow(table), truncated = nrow(table) > limit)
    },
    stop("Unknown graph operation.")
  )
  c(list(analysis_id = state$id, source_file = state$path), answer)
}
input = file("stdin", open = "r")
repeat {
  line = readLines(input, n = 1, warn = FALSE)
  if (!length(line)) break
  response = tryCatch({
    request = jsonlite::fromJSON(line, simplifyVector = FALSE)
    list(ok = TRUE, data = dispatch(request$method, request$params))
  }, error = function(error) list(ok = FALSE, error = conditionMessage(error)))
  cat(jsonlite::toJSON(response, auto_unbox = TRUE, dataframe = "rows", null = "null", na = "null", digits = NA), "\n", sep = "")
  flush(stdout())
}
