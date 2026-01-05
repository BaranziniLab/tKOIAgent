#!/usr/bin/env Rscript

# Generate tKOI visualizations using the visualize_topn function
# Following ggplot style guide and tKOI official documentation

library(ggplot2)
library(jsonlite)
library(tkoi)

# Read parameters
args_file = Sys.getenv("TKOI_ARGS_FILE")
if (args_file == "" || !file.exists(args_file)) {
  stop("Arguments file not found")
}

params = fromJSON(args_file)

tryCatch({
  # Load tKOI results from RDA file
  cat("Loading tKOI results...\n", file = stderr())
  load(params$results_file)

  # Verify tkoi_result object exists
  if (!exists("tkoi_result")) {
    stop("tkoi_result object not found in RDA file")
  }

  # Create output directory
  output_dir = params$output_dir
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  # Create plots subdirectory
  plots_dir = file.path(output_dir, "plots")
  dir.create(plots_dir, recursive = TRUE, showWarnings = FALSE)

  cat(sprintf("Generating plots in: %s\n", plots_dir), file = stderr())

  # Define modalities to visualize
  modalities = c(
    "Anatomy",
    "CellType",
    "Complex",
    "Pathway",
    "Disease",
    "BiologicalProcess",
    "CellularComponent",
    "MolecularFunction",
    "Gene"
  )

  # Color scheme: high enrichment (red) to low enrichment (dark blue)
  high_color = "#FF5733"  # Strong enrichment (red-orange)
  low_color = "#154360"   # Moderate enrichment (dark blue)

  plot_files = c()
  successful_plots = 0

  # Generate top N visualizations for each modality
  for (modality in modalities) {
    tryCatch({
      cat(sprintf("Generating plot for: %s\n", modality), file = stderr())

      # Generate visualization using tKOI's visualize_topn function
      plt = visualize_topn(
        tkoi_list = tkoi_result,
        category = modality,
        top_n = 20,
        high_color = high_color,
        low_color = low_color
      )

      # Apply ggplot style guide optimizations
      plt = plt +
        theme_minimal(base_size = 14) +
        theme(
          plot.margin = margin(10, 10, 10, 10),
          axis.text.y = element_text(size = 12),
          axis.text.x = element_text(size = 12),
          plot.title = element_text(size = 16, face = "bold"),
          legend.position = "right"
        )

      # Save plot with optimized settings
      plot_filename = sprintf("top20_%s.png", tolower(modality))
      plot_file = file.path(plots_dir, plot_filename)

      ggsave(
        filename = plot_file,
        plot = plt,
        width = 5,
        height = 4,
        dpi = 800,
        units = "in",
        device = "png"
      )

      cat(sprintf("  Saved: %s\n", plot_filename), file = stderr())
      plot_files = c(plot_files, plot_file)
      successful_plots = successful_plots + 1

    }, error = function(e) {
      cat(sprintf("  Warning: Could not generate plot for %s: %s\n", modality, e$message), file = stderr())
    })
  }

  cat(sprintf("Successfully generated %d/%d plots\n", successful_plots, length(modalities)), file = stderr())

  # Output results as JSON
  output = list(
    success = TRUE,
    message = sprintf("Generated %d plots for tKOI results", successful_plots),
    plot_files = plot_files,
    plots_directory = plots_dir,
    modalities_plotted = successful_plots
  )

  cat(toJSON(output, auto_unbox = TRUE))

}, error = function(e) {
  # Report error
  output = list(
    success = FALSE,
    error = paste("Plot generation failed:", e$message),
    traceback = paste(capture.output(traceback()), collapse = "\n")
  )
  cat(toJSON(output, auto_unbox = TRUE))
  quit(status = 1)
})
