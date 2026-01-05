"""
R script execution manager for tKOIAgent.

Manages R subprocess execution with JSON communication for data exchange.
Uses subprocess instead of rpy2 for better process isolation and error handling.
"""

import subprocess
import tempfile
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class RExecutionError(Exception):
    """Custom exception for R execution failures"""

    def __init__(self, message: str, stdout: str = "", stderr: str = "", returncode: int = -1):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class RExecutor:
    """Manages R script execution via subprocess with JSON communication"""

    def __init__(self, r_scripts_dir: Path):
        """
        Initialize R executor.

        Args:
            r_scripts_dir: Directory containing R scripts
        """
        self.r_scripts_dir = Path(r_scripts_dir)
        self.r_command = self._find_r_executable()

    def _find_r_executable(self) -> str:
        """
        Locate R executable on system.

        Returns:
            Path to R executable

        Raises:
            RuntimeError: If R is not found
        """
        # Try common locations
        candidates = ["R", "/usr/local/bin/R", "/usr/bin/R", "/opt/homebrew/bin/R"]

        for cmd in candidates:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"Found R executable: {cmd}")
                    return cmd
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        raise RuntimeError(
            "R executable not found. Please install R from https://cran.r-project.org/"
        )

    def execute_script(
        self,
        script_name: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Execute R script with arguments.

        Args:
            script_name: Name of R script in r_scripts/ directory
            args: Dictionary of arguments to pass to R script
            timeout: Maximum execution time in seconds (default: 5 minutes)

        Returns:
            Dictionary containing execution results

        Raises:
            FileNotFoundError: If script not found
            RExecutionError: If R execution fails
        """
        script_path = self.r_scripts_dir / script_name

        if not script_path.exists():
            raise FileNotFoundError(f"R script not found: {script_path}")

        logger.info(f"Executing R script: {script_name}")

        # Create temporary file for arguments (JSON format)
        args_file_path = None
        if args:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False
            ) as args_file:
                json.dump(args, args_file, indent=2)
                args_file_path = args_file.name

        try:
            # Build R command
            cmd = [
                self.r_command,
                "--vanilla",  # Don't load .RData or .Rprofile
                "--slave",    # Minimal output
                "--no-save",  # Don't save workspace
                "-f",
                str(script_path)
            ]

            # Pass args file path as environment variable
            env = os.environ.copy()
            if args_file_path:
                env['TKOI_ARGS_FILE'] = args_file_path

            # Execute R script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

            # Parse output (expecting JSON on last line of stdout)
            output = self._parse_r_output(result.stdout, result.stderr)

            if result.returncode != 0:
                logger.error(f"R script failed with return code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                raise RExecutionError(
                    f"R script failed: {script_name}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    returncode=result.returncode
                )

            logger.info(f"R script completed successfully: {script_name}")
            return output

        except subprocess.TimeoutExpired:
            logger.error(f"R script timed out after {timeout}s: {script_name}")
            raise RExecutionError(
                f"R script timed out after {timeout}s: {script_name}",
                stdout="",
                stderr="Timeout",
                returncode=-1
            )
        finally:
            # Clean up temporary args file
            if args_file_path and os.path.exists(args_file_path):
                os.unlink(args_file_path)

    def _parse_r_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Parse R script output (expects JSON on last line).

        Args:
            stdout: Standard output from R
            stderr: Standard error from R

        Returns:
            Parsed output dictionary
        """
        if not stdout.strip():
            return {
                "success": True,
                "message": "No output from R script",
                "warnings": stderr if stderr else None
            }

        lines = stdout.strip().split('\n')

        # Try to parse last line as JSON
        try:
            result = json.loads(lines[-1])
            return result
        except json.JSONDecodeError:
            # If not JSON, return as plain text
            logger.warning("R output is not valid JSON, returning as plain text")
            return {
                "success": True,
                "output": stdout,
                "warnings": stderr if stderr else None
            }

    def check_package_installed(self, package_name: str) -> bool:
        """
        Check if R package is installed.

        Args:
            package_name: Name of R package

        Returns:
            True if package is installed, False otherwise
        """
        try:
            result = subprocess.run(
                [
                    self.r_command,
                    "--vanilla",
                    "--slave",
                    "-e",
                    f"cat(as.character('{package_name}' %in% installed.packages()[,'Package']))"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() == "TRUE"
        except Exception as e:
            logger.error(f"Error checking R package {package_name}: {e}")
            return False

    def get_r_version(self) -> str:
        """
        Get R version string.

        Returns:
            R version string
        """
        try:
            result = subprocess.run(
                [self.r_command, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Extract first line
                return result.stdout.split('\n')[0]
            return "Unknown"
        except Exception as e:
            logger.error(f"Error getting R version: {e}")
            return "Unknown"
