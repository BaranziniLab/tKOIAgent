#!/usr/bin/env Rscript

# Check if tKOI package is installed

check_tkoi <- function() {
  packages_installed <- installed.packages()[, "Package"]

  tkoi_installed <- "tkoi" %in% packages_installed

  result <- list(
    installed = tkoi_installed,
    message = if (tkoi_installed) {
      version <- as.character(packageVersion("tkoi"))
      paste("tkoi version", version, "is installed")
    } else {
      "tkoi package is not installed"
    }
  )

  return(result)
}

# Main execution
tryCatch({
  result <- check_tkoi()
  cat(jsonlite::toJSON(result, auto_unbox = TRUE))
}, error = function(e) {
  result <- list(
    installed = FALSE,
    message = paste("Error checking tkoi:", e$message)
  )
  cat(jsonlite::toJSON(result, auto_unbox = TRUE))
})
