#!/usr/bin/env Rscript

# Install tKOI package from GitHub

# Read arguments from environment variable
args_file <- Sys.getenv("TKOI_ARGS_FILE")
if (args_file != "" && file.exists(args_file)) {
  args <- jsonlite::fromJSON(args_file)
  repo <- args$repo
} else {
  repo <- "default/tkoi"  # Placeholder - update with actual repo
}

# Install devtools if needed
if (!require("devtools", quietly = TRUE)) {
  install.packages("devtools", repos = "https://cloud.r-project.org")
}

# Install jsonlite if needed
if (!require("jsonlite", quietly = TRUE)) {
  install.packages("jsonlite", repos = "https://cloud.r-project.org")
}

# Install tKOI
tryCatch({
  devtools::install_github(repo, dependencies = TRUE)

  result <- list(
    success = TRUE,
    message = paste("tkoi installed successfully from", repo),
    version = as.character(packageVersion("tkoi"))
  )
  cat(jsonlite::toJSON(result, auto_unbox = TRUE))

}, error = function(e) {
  result <- list(
    success = FALSE,
    message = paste("Installation failed:", e$message)
  )
  cat(jsonlite::toJSON(result, auto_unbox = TRUE))
})
