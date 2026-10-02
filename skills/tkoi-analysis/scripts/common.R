require_tkoi = function() {
  if (!requireNamespace("tkoi", quietly = TRUE) || utils::packageVersion("tkoi") < "1.3.0") {
    stop("Install tkoi >= 1.3.0 with this skill's setup.R first.", call. = FALSE)
  }
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Install jsonlite with setup.R first.")
}

parse_options = function(args, defaults) {
  if (length(args) %% 2) stop("Options must be --name value pairs.")
  if (!length(args)) return(defaults)
  for (i in seq(1, length(args), by = 2)) {
    key = sub("^--", "", args[i])
    if (!startsWith(args[i], "--") || !key %in% names(defaults)) stop("Unknown option: ", args[i])
    defaults[[key]] = args[i + 1]
  }
  defaults
}

write_json = function(value, path) {
  jsonlite::write_json(value, path, auto_unbox = TRUE, pretty = TRUE, na = "null", null = "null")
}

whole_number = function(value, name, minimum = 1) {
  number = suppressWarnings(as.numeric(value))
  if (length(number) != 1 || !is.finite(number) || number < minimum ||
      number != floor(number) || number > .Machine$integer.max) stop("Invalid ", name)
  as.integer(number)
}
