# Normalize a human differential-expression table without re-estimating statistics.
script = sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1])
source(file.path(dirname(normalizePath(script)), "common.R"))
require_tkoi()
args = commandArgs(TRUE)
if (length(args) < 2) stop("Usage: Rscript prepare.R input.csv prepared.csv [--option value]")
input = normalizePath(args[1], mustWork = TRUE)
output = args[2]
report_path = paste0(output, ".report.json")
if (file.exists(output) || file.exists(report_path)) stop("Output already exists; choose a new output path.")
opts = parse_options(args[-c(1, 2)], list(
  "gene-column" = "gene_name", "logfc-column" = "logfc", "pvalue-column" = "pvalue",
  "id-type" = "ensembl", "duplicates" = "error", "invalid" = "error", "sheet" = "1"
))
if (!opts[["id-type"]] %in% c("ensembl", "symbol", "entrez")) stop("id-type must be ensembl, symbol, or entrez.")
if (!opts$duplicates %in% c("error", "max-abs-logfc", "first")) stop("Invalid duplicates policy.")
if (!opts$invalid %in% c("error", "drop")) stop("invalid must be error or drop.")
extension = tolower(tools::file_ext(input))
data = switch(extension,
  csv = read.csv(input, check.names = FALSE, colClasses = "character"),
  tsv = read.delim(input, check.names = FALSE, colClasses = "character"),
  txt = read.delim(input, check.names = FALSE, colClasses = "character"),
  xlsx = {
    if (!requireNamespace("readxl", quietly = TRUE)) stop("Install readxl to read Excel files.")
    sheet = opts$sheet
    if (grepl("^[0-9]+$", sheet)) sheet = as.integer(sheet)
    as.data.frame(readxl::read_excel(input, sheet = sheet, col_types = "text"))
  },
  stop("Use CSV, TSV, tab-delimited TXT, or XLSX.")
)
columns = unlist(opts[c("gene-column", "logfc-column", "pvalue-column")], use.names = FALSE)
if (anyDuplicated(names(data)) || !all(columns %in% names(data)) || anyDuplicated(columns)) {
  stop("Select three distinct, unambiguous gene/logFC/p-value columns that exist in the input.")
}
ids = trimws(as.character(data[[columns[1]]]))
logfc = suppressWarnings(as.numeric(data[[columns[2]]]))
pvalue = suppressWarnings(as.numeric(data[[columns[3]]]))
bad = is.na(ids) | !nzchar(ids) | !is.finite(logfc) | !is.finite(pvalue) | pvalue < 0 | pvalue > 1
if (any(bad) && opts$invalid == "error") {
  stop(sum(bad), " invalid rows. Inspect missing IDs, nonnumeric/nonfinite values or p-values outside [0,1]. ",
       "Use --invalid drop only after reviewing them.")
}
versioned = if (opts[["id-type"]] == "ensembl") grepl("^ENSG[0-9]+\\.[0-9]+$", ids) else rep(FALSE, length(ids))
versioned[is.na(versioned)] = FALSE
ids[versioned] = sub("\\.[0-9]+$", "", ids[versioned])
genes = as.data.frame(tkoi::genes)
map_column = switch(opts[["id-type"]], ensembl = "ensembl", symbol = "name", entrez = "identifier")
mapping = unique(data.frame(key = as.character(genes[[map_column]]), ensembl = genes$ensembl))
mapping = mapping[!is.na(mapping$key) & !is.na(mapping$ensembl) & nzchar(mapping$ensembl), ]
ambiguous = unique(mapping$key[duplicated(mapping$key) | duplicated(mapping$key, fromLast = TRUE)])
if (any(ids[!bad] %in% ambiguous)) stop("Ambiguous gene mapping; resolve these IDs explicitly: ",
                                        paste(head(intersect(ids[!bad], ambiguous), 10), collapse = ", "))
mapped = mapping$ensembl[match(ids, mapping$key)]
unmapped = !bad & is.na(mapped)
keep = !bad & !unmapped
prepared = data.frame(gene_name = mapped[keep], logfc = logfc[keep], pvalue = pvalue[keep])
duplicate_rows = sum(duplicated(prepared$gene_name))
if (duplicate_rows && opts$duplicates == "error") {
  stop(duplicate_rows, " duplicate mapped gene rows. Resolve them or choose --duplicates first/max-abs-logfc.")
}
if (opts$duplicates == "max-abs-logfc") {
  prepared = prepared[order(-abs(prepared$logfc), seq_len(nrow(prepared))), ]
}
prepared = prepared[!duplicated(prepared$gene_name), ]
if (!nrow(prepared)) stop("No mapped, valid genes remain.")
dir.create(dirname(output), recursive = TRUE, showWarnings = FALSE)
write.csv(prepared, output, row.names = FALSE, na = "")
write_json(list(
  input = input, input_md5 = unname(tools::md5sum(input)), options = opts,
  input_rows = nrow(data), output_rows = nrow(prepared), invalid_rows = sum(bad),
  stripped_ensembl_versions = sum(versioned), unmapped_rows = sum(unmapped),
  unmapped_ids = unique(ids[unmapped]), duplicate_rows = duplicate_rows,
  tkoi_version = as.character(utils::packageVersion("tkoi")),
  note = "logFC and p-values were supplied by the input analysis; no statistical model or log transform was applied."
), report_path)
cat("Prepared", nrow(prepared), "genes;", sum(unmapped), "unmapped rows omitted. Audit:", report_path, "\n")
