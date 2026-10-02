# Run with Rscript after installing R and its compiler toolchain.
if (getRversion() < "4.1.0") stop("tkoi requires R >= 4.1.0; install a current R release.")
options(repos = c(CRAN = "https://cloud.r-project.org"))
cran = c("remotes", "BiocManager", "jsonlite", "readxl")
missing = cran[!vapply(cran, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) install.packages(missing)
bioc = c("clusterProfiler", "org.Hs.eg.db")
missing = bioc[!vapply(bioc, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) BiocManager::install(missing, ask = FALSE, update = FALSE)
if (!requireNamespace("tkoi", quietly = TRUE) || utils::packageVersion("tkoi") < "1.3.0") {
  remotes::install_github("BaranziniLab/tkoi@v1.3.0", dependencies = NA, upgrade = "never")
}
stopifnot(utils::packageVersion("tkoi") >= "1.3.0")
cat("Ready: R", as.character(getRversion()), "and tkoi", as.character(utils::packageVersion("tkoi")), "\n")
