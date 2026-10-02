# Input preparation and audit

## Identify the input stage

tKOI consumes **human gene-level differential-expression statistics**, not an
expression matrix. Establish the biological comparison, species, sample units,
gene identifier namespace, and log-fold-change scale before transforming data.
Save the original input and the script used for every transformation.

### Already computed differential expression

Recognize and explicitly map the supplied columns, for example:

| Source | Gene ID | Log2 fold change | P-value |
|---|---|---|---|
| DESeq2 | row names or exported ID column | `log2FoldChange` | `pvalue` |
| limma/edgeR | row names or exported ID column | `logFC` | `P.Value` / `PValue` |
| Seurat result | row names or exported gene column | `avg_log2FC` | `p_val` |

Do not assume an `avg_logFC` column uses log2. Consult the generating method.
Prefer the supplied raw p-value column for the input threshold. If only adjusted
p-values are available, state that limitation, explicitly select that column,
and record that the seed threshold uses adjusted values. Do not back-calculate
raw p-values or fabricate a p-value for a list of genes. tKOI's reported FDR is
a separate adjustment of its network permutation tests.

Example conversion:

```sh
Rscript /absolute/plugin/skills/tkoi-analysis/scripts/prepare.R de.csv prepared.csv \
  --gene-column ensembl_id --logfc-column log2FoldChange \
  --pvalue-column pvalue --id-type ensembl
```

The helper accepts `.csv`, `.tsv`, tab-delimited `.txt`, and `.xlsx`. For Excel,
select a sheet by number or exact name with `--sheet`. Convert row names to a
real column before CSV export. Keep gene identifiers as text; Excel can alter
gene symbols or long identifiers, and those changes must be corrected from the
original source, not guessed.

### Bulk RNA-seq counts

Obtain an integer, nonnegative raw count matrix (genes x samples) plus sample
metadata with condition, biological replicate, and relevant batch/pairing
variables. Align sample names exactly. Do not feed TPM, FPKM, VST, log-normalized
values, or already normalized counts to a raw-count model. Ask for the original
counts or a valid differential-expression table if those are all that is available.

For an ordinary two-condition design with independent biological replicates,
DESeq2 is one supported preparation route. This example assumes the user has
confirmed `control` and `treated`, the `~ condition` design, and the low-count
filter. Adapt the design to the actual experiment; do not silently omit known
batch or pairing variables.

```r
BiocManager::install("DESeq2", ask = FALSE, update = FALSE) # if missing
counts = as.matrix(read.csv("counts.csv", row.names = 1, check.names = FALSE))
samples = read.csv("samples.csv", row.names = 1, check.names = FALSE)
stopifnot(!anyDuplicated(colnames(counts)),
          setequal(colnames(counts), rownames(samples)))
samples = samples[colnames(counts), , drop = FALSE]
stopifnot(!anyNA(counts), all(is.finite(counts)), all(counts >= 0),
          all(counts == round(counts)), !anyDuplicated(rownames(counts)))
samples$condition = relevel(factor(samples$condition), ref = "control")
design = model.matrix(~ condition, samples)
stopifnot(qr(design)$rank == ncol(design))
dds = DESeq2::DESeqDataSetFromMatrix(counts, samples, design = ~ condition)
# Example filter; choose and record a filter appropriate to replicate depth.
dds = dds[rowSums(DESeq2::counts(dds) >= 10) >= 2, ]
dds = DESeq2::DESeq(dds)
de = as.data.frame(DESeq2::results(dds, contrast = c("condition", "treated", "control")))
de$gene_name = rownames(de)
write.csv(de, "de.csv", row.names = FALSE)
```

The exported `gene_name` column still contains the count matrix's original row
IDs. Pass `--gene-column gene_name --logfc-column log2FoldChange
--pvalue-column pvalue` to `prepare.R` and choose `--id-type` for those IDs. Use
`ensembl` only when the row IDs are human Ensembl gene identifiers; a column name
alone does not change their namespace.

Record sample counts, exclusions, design, contrast and normalization method.
For paired samples, use a supported design such as `~ donor + condition` only
when donor/condition are identifiable; for batches use an appropriate batch
term. Replication and design cannot be inferred from counts alone. Review
library sizes, low-count exclusions, sample distances/PCA and model diagnostics
before enrichment. Handle non-estimable/NA statistics explicitly using the
invalid-value policy below. Positive `logfc` in the example means higher in
treated relative to control.

### Single-cell data

For condition comparisons across donors, prepare donor-level pseudobulk counts
within the chosen cell type, then fit a replicate-aware model such as DESeq2 or
edgeR. Cells from one donor are not independent biological replicates. Sum raw
counts, not normalized or log-transformed values. After selecting the cell type
and aligning metadata with count columns, a sparse aggregation pattern is:

```r
# cell_counts: sparse genes x cells raw counts, metadata aligned to its columns
stopifnot(identical(colnames(cell_counts), rownames(cell_metadata)))
groups = factor(cell_metadata$sample_id)
membership = Matrix::sparse.model.matrix(~ 0 + groups)
pseudobulk = cell_counts %*% membership
colnames(pseudobulk) = levels(groups)
```

Use one metadata row per biological sample, verify one condition per sample,
record minimum cell/count thresholds and cell-type exclusions, and fit the
actual donor/batch design. Existing marker tables can be normalized by the
helper, but describe them as marker enrichment rather than claiming a
replicate-aware disease/condition test unless the original model supports that.

## Gene identifiers and species

The bundled network is human. `gene_name` means an **Ensembl gene identifier**,
not a display symbol or an igraph vertex name. `--id-type ensembl` trims outer
whitespace and removes numeric version suffixes from IDs such as
`ENSG00000141510.18`. `--id-type symbol` matches exact symbols against
`tkoi::genes$name`; `--id-type entrez` matches `tkoi::genes$identifier`. All routes
produce `tkoi::genes$ensembl`. The helper rejects one-to-many mappings, reports
unmapped input IDs, and drops those unmapped rows only with an explicit audit
report. Review the report before running; a high unmapped fraction warrants
investigation of species, namespace, annotation version or corrupted input.

Do not case-fold symbols, translate aliases by guessing, mix transcript IDs
with gene IDs, or silently map nonhuman genes to human. If an explicit ortholog
analysis is requested, document the mapping resource/version, ambiguity policy,
coverage, and altered interpretation before using a human network.

The helper's supported policies are:

- `--invalid error` (default): stop on blank IDs, missing/nonnumeric/nonfinite
  logFC/p-values, or p-values outside [0,1]. `--invalid drop` is available after
  reviewing why those rows are invalid. Do not replace missing values with zero.
- `--duplicates error` (default): stop if multiple input rows map to one Ensembl
  gene, including collisions created by stripping version suffixes.
- `--duplicates first`: retain the first row, when the input ordering has a
  justified meaning. `--duplicates max-abs-logfc`: retain the largest absolute
  logFC, breaking ties by input order. Both are explicit selection policies,
  not substitutes for transcript-to-gene statistical aggregation.

No logarithm, p-value estimation, batch correction, normalization, or automatic
significance filtering occurs in `prepare.R`. If a verified fold-change ratio
must be converted, apply `log2(ratio)` only to positive ratios and preserve that
transformation in the preparation script. Keep the full valid DE table; the
analysis helper applies the chosen p-value and absolute-logFC seed thresholds.

`prepared.csv.report.json` records source checksum, selected columns and policies,
input/output counts, version stripping, unmapped IDs and duplicate counts.
Review it. `analyze.R` also records genes outside the selected graph, and saves
the analyzed expression table and session information. The permutation universe
is tKOI's annotated genes present in the chosen graph; it is not automatically
restricted to every gene measured in the DE experiment.

## Scientific sources

- [DESeq2 workflow and design guidance](https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html)
- [edgeR package and user guide](https://bioconductor.org/packages/edgeR/)
- [tKOI package documentation](https://baranzinilab.github.io/tkoi/)
