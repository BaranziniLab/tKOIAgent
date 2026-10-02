script = sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1])
source(file.path(dirname(normalizePath(script)), "common.R"))
require_tkoi()
main = function() {
  args = commandArgs(TRUE)
  if (length(args) < 2) stop("Usage: Rscript analyze.R prepared.csv run-directory [--option value]")
  input = normalizePath(args[1], mustWork = TRUE)
  outdir = args[2]
  if (dir.exists(outdir) && length(list.files(outdir, all.files = TRUE, no.. = TRUE))) {
    stop("Run directory is not empty; choose a new directory.")
  }
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
  lock = file.path(outdir, ".tkoi-running")
  if (!dir.create(lock, showWarnings = FALSE)) stop("Run directory is already claimed by another process.")
  on.exit(unlink(lock, recursive = TRUE), add = TRUE)
  if (length(setdiff(list.files(outdir, all.files = TRUE, no.. = TRUE), ".tkoi-running"))) {
    stop("Run directory acquired output while waiting; choose a new directory.")
  }
  opts = parse_options(args[-c(1, 2)], list(
    "graph" = "", "permutations" = "1000", "cores" = "2", "seed" = "42",
    "pvalue" = "0.05", "logfc" = "0.25"
  ))
  permutations = whole_number(opts$permutations, "permutations", 2)
  cores = whole_number(opts$cores, "cores")
  seed = whole_number(opts$seed, "seed", 0)
  expression = read.csv(input, check.names = FALSE)
  if (!all(c("gene_name", "logfc", "pvalue") %in% names(expression))) stop("Run prepare.R first.")
  if (anyDuplicated(expression$gene_name) || anyNA(expression[, c("gene_name", "logfc", "pvalue")]) ||
      !is.numeric(expression$logfc) || !is.numeric(expression$pvalue) ||
      any(!is.finite(expression$logfc)) || any(!is.finite(expression$pvalue)) ||
      any(expression$pvalue < 0 | expression$pvalue > 1)) stop("Invalid prepared table; run prepare.R first.")
  graph = if (nzchar(opts$graph)) readRDS(normalizePath(opts$graph, mustWork = TRUE)) else tkoi::tkoi_net
  if (!igraph::is_igraph(graph)) stop("--graph must contain an igraph saved with saveRDS().")
  gene_ids = tkoi::genes$id[match(expression$gene_name, tkoi::genes$ensembl)]
  in_graph = !is.na(gene_ids) & gene_ids %in% igraph::V(graph)$name
  if (!any(in_graph)) stop("No input genes map to this graph.")
  set.seed(seed)
  result = tkoi::run_tkoi(
    expression[in_graph, , drop = FALSE], subnetwork = graph,
    n_permutation = permutations, n_cores = cores, keep_permutations = FALSE,
    pvalue_threshold = as.numeric(opts$pvalue), logfc_threshold = as.numeric(opts$logfc)
  )
  stopifnot(identical(tkoi::get_analysis_graph(result), graph))
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
  saveRDS(result, file.path(outdir, "analysis.rds"))
  write.csv(expression[in_graph, ], file.path(outdir, "expression.csv"), row.names = FALSE)
  for (category in names(result@network_summary_statistics)) {
    safe = gsub("[^A-Za-z0-9_-]", "_", category)
    write.csv(result@network_summary_statistics[[category]], file.path(outdir, paste0(safe, ".csv")), row.names = FALSE)
  }
  write_json(list(
    schema_version = 1, tkoi_version = as.character(utils::packageVersion("tkoi")),
    input = input, input_md5 = unname(tools::md5sum(input)), seed = seed, options = opts,
    input_rows = nrow(expression), analyzed_rows = sum(in_graph),
    genes_outside_graph = as.character(expression$gene_name[!in_graph]),
    graph_source = if (nzchar(opts$graph)) normalizePath(opts$graph) else "tkoi::tkoi_net",
    graph_vertices = igraph::vcount(graph), graph_edges = igraph::ecount(graph),
    graph_directed = igraph::is_directed(graph), analysis_edge_mode = "undirected",
    analysis_md5 = unname(tools::md5sum(file.path(outdir, "analysis.rds")))
  ), file.path(outdir, "provenance.json"))
  capture.output(sessionInfo(), file = file.path(outdir, "sessionInfo.txt"))
  report = paste0(input, ".report.json")
  if (file.exists(report)) file.copy(report, file.path(outdir, "preprocessing.json"))
  cat("Saved analysis and exact graph:", normalizePath(file.path(outdir, "analysis.rds")), "\n")
}
main()
