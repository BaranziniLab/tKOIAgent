#!/usr/bin/env Rscript

# Main tKOI analysis script
# Runs tKOI network propagation analysis on gene expression data

library(jsonlite)
library(data.table)
library(openxlsx)

# Read parameters from JSON file
args_file <- Sys.getenv("TKOI_ARGS_FILE")
if (args_file == "" || !file.exists(args_file)) {
  stop("Arguments file not found")
}

params <- fromJSON(args_file)

# Setup logging to file in working directory
log_file <- file.path(params$output_dir, "run_tkoi.log")
log_con <- file(log_file, open = "wt")

# Function to log messages to both stderr and log file
log_message <- function(msg) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  full_msg <- sprintf("[%s] %s\n", timestamp, msg)
  cat(full_msg, file = stderr())
  cat(full_msg, file = log_con)
  flush(log_con)  # Force write to disk immediately
}

tryCatch({
  log_message("Starting tKOI analysis...")
  log_message(sprintf("Log file: %s", log_file))

  # Load required packages
  log_message("Checking for tkoi package...")
  if (!require("tkoi", quietly = TRUE)) {
    stop("tkoi package is not installed. Please install it first using: devtools::install_github('yourusername/tkoi')")
  }
  log_message("tkoi package loaded successfully")

  # Read the gene expression data file
  log_message(sprintf("Reading data file: %s", params$data_file))
  expression_data <- fread(params$data_file)
  log_message(sprintf("Loaded expression data: %d genes, %d columns", nrow(expression_data), ncol(expression_data)))

  # Set random seed for reproducibility
  set.seed(params$seed)
  log_message(sprintf("Random seed set to: %d", params$seed))

  # Calculate p-value threshold based on FDR correction
  log_message("Calculating dynamic p-value threshold from FDR correction...")
  # Find the largest p-value that is still significant after FDR correction (FDR <= 0.05)
  # Assuming expression_data has a 'pvalue' or 'PValue' column
  pvalue_col <- NULL
  if ("pvalue" %in% colnames(expression_data)) {
    pvalue_col <- "pvalue"
  } else if ("PValue" %in% colnames(expression_data)) {
    pvalue_col <- "PValue"
  } else if ("p.value" %in% colnames(expression_data)) {
    pvalue_col <- "p.value"
  } else if ("p_value" %in% colnames(expression_data)) {
    pvalue_col <- "p_value"
  } else {
    stop("Could not find p-value column in expression data. Expected column names: 'pvalue', 'PValue', 'p.value', or 'p_value'")
  }
  log_message(sprintf("Using p-value column: %s", pvalue_col))

  # Calculate FDR (Benjamini-Hochberg correction)
  expression_data$fdr <- p.adjust(expression_data[[pvalue_col]], method = "BH")
  log_message("FDR correction (Benjamini-Hochberg) completed")

  # Find the largest p-value where FDR <= 0.05
  significant_genes <- expression_data[expression_data$fdr <= 0.05, ]
  if (nrow(significant_genes) > 0) {
    pvalue_threshold <- max(significant_genes[[pvalue_col]])
    log_message(sprintf("Calculated p-value threshold: %.6f", pvalue_threshold))
    log_message(sprintf("Significant genes (FDR <= 0.05): %d out of %d (%.1f%%)",
                       nrow(significant_genes), nrow(expression_data),
                       100 * nrow(significant_genes) / nrow(expression_data)))
  } else {
    # No significant genes, use a very stringent threshold
    pvalue_threshold <- 0.001
    log_message(sprintf("WARNING: No genes with FDR <= 0.05. Using stringent threshold: %.6f", pvalue_threshold))
  }

  # Run tKOI analysis with user-configurable parameters
  log_message("Starting tKOI network propagation analysis...")
  log_message(sprintf("Parameters: alpha=%.2f, max_iter=%d, n_permutation=%d",
                     params$alpha, params$max_iterations, params$n_permutation))
  tkoi_result <- tkoi::run_tkoi(
    expression_data = expression_data,
    subnetwork = tkoi::tkoi_net,              # Predefined igraph network included with tkoi package
    pvalue_threshold = pvalue_threshold,       # p-value filter for differential expression
    logfc_threshold = params$logfc_threshold,  # Minimum log fold change (from config)
    indirect_link_threshold = params$indirect_link_threshold,  # Required indirect connectivity
    topology_similarity = params$topology_similarity,          # Similarity for permutations
    n_permutation = params$n_permutation,      # Number of random permutations
    damping_factor = params$alpha,             # PageRank damping factor (alpha)
    maximum_iteration = params$max_iterations  # Max iterations for convergence
  )

  log_message("tKOI network propagation completed successfully")

  # Create output directory
  output_dir <- params$output_dir
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  # 1. Save tkoi_result as RDA file
  log_message("Saving results...")
  rda_file <- file.path(output_dir, "tkoi_result.rda")
  save(tkoi_result, file = rda_file)
  log_message(sprintf("Saved RDA file: %s", rda_file))

  # 2. Extract and save network_summary_statistics (all results)
  log_message("Extracting network summary statistics...")
  network_summary <- tkoi_result@network_summary_statistics

  if (is.null(network_summary) || length(network_summary) == 0) {
    log_message("WARNING: No network summary statistics found in tkoi_result")
  } else {
    log_message(sprintf("Found %d modalities in network summary", length(network_summary)))

    # Save all summary statistics to tkoi_summary.xlsx
    log_message("Creating Excel workbook with all results...")
    summary_file <- file.path(output_dir, "tkoi_summary.xlsx")
    wb_all <- createWorkbook()

    for (modality_name in names(network_summary)) {
      df <- network_summary[[modality_name]]
      if (!is.null(df) && nrow(df) > 0) {
        # Sanitize sheet name (Excel has 31 char limit and special char restrictions)
        sheet_name <- substr(gsub("[:\\\\/?*\\[\\]]", "_", modality_name), 1, 31)
        addWorksheet(wb_all, sheet_name)
        writeData(wb_all, sheet_name, df)
        log_message(sprintf("  Added sheet '%s' (%d rows)", sheet_name, nrow(df)))
      }
    }

    saveWorkbook(wb_all, summary_file, overwrite = TRUE)
    log_message(sprintf("Saved complete summary: %s", summary_file))

    # 3. Filter by FDR <= 0.05 and save significant results
    log_message("Creating Excel workbook with significant results (FDR <= 0.05)...")
    significant_file <- file.path(output_dir, "tkoi_summary_significant.xlsx")
    wb_sig <- createWorkbook()
    sig_sheet_count <- 0

    for (modality_name in names(network_summary)) {
      df <- network_summary[[modality_name]]

      if (!is.null(df) && nrow(df) > 0 && "fdr" %in% colnames(df)) {
        # Filter by FDR <= 0.05
        df_sig <- df[df$fdr <= 0.05, ]

        if (nrow(df_sig) > 0) {
          # Sanitize sheet name
          sheet_name <- substr(gsub("[:\\\\/?*\\[\\]]", "_", modality_name), 1, 31)
          addWorksheet(wb_sig, sheet_name)
          writeData(wb_sig, sheet_name, df_sig)
          log_message(sprintf("  Added significant sheet '%s' (%d/%d rows with FDR <= 0.05)",
                             sheet_name, nrow(df_sig), nrow(df)))
          sig_sheet_count <- sig_sheet_count + 1
        }
      }
    }

    saveWorkbook(wb_sig, significant_file, overwrite = TRUE)
    log_message(sprintf("Saved significant results: %s (%d modalities with significant hits)",
                       significant_file, sig_sheet_count))
  }

  # 4. Prepare JSON output for Python
  log_message("Preparing final output...")
  output_files <- c(rda_file)
  if (file.exists(file.path(output_dir, "tkoi_summary.xlsx"))) {
    output_files <- c(output_files, file.path(output_dir, "tkoi_summary.xlsx"))
  }
  if (file.exists(file.path(output_dir, "tkoi_summary_significant.xlsx"))) {
    output_files <- c(output_files, file.path(output_dir, "tkoi_summary_significant.xlsx"))
  }

  # Count significant results by modality
  sig_counts <- list()
  if (!is.null(network_summary)) {
    for (modality_name in names(network_summary)) {
      df <- network_summary[[modality_name]]
      if (!is.null(df) && "fdr" %in% colnames(df)) {
        sig_counts[[modality_name]] <- sum(df$fdr <= 0.05)
      }
    }
  }

  output <- list(
    success = TRUE,
    message = "tKOI analysis completed successfully",
    output_files = output_files,
    statistics = list(
      total_genes = nrow(expression_data),
      modalities_analyzed = if (!is.null(network_summary)) length(network_summary) else 0,
      significant_results_by_modality = sig_counts
    )
  )

  log_message("Analysis completed successfully!")
  log_message(sprintf("Total output files: %d", length(output_files)))
  log_message("=== END OF ANALYSIS ===")

  # Close log file
  close(log_con)

  cat(toJSON(output, auto_unbox = TRUE))

}, error = function(e) {
  # Log error before reporting
  if (exists("log_message")) {
    log_message(sprintf("ERROR: %s", e$message))
    log_message("=== ANALYSIS FAILED ===")
  }

  # Close log file if open
  if (exists("log_con") && isOpen(log_con)) {
    close(log_con)
  }

  # Report actual error without generating mock results
  output <- list(
    success = FALSE,
    error = paste("tKOI analysis failed:", e$message),
    traceback = paste(capture.output(traceback()), collapse = "\n")
  )
  cat(toJSON(output, auto_unbox = TRUE))
  quit(status = 1)
})
