"""
Environment setup tools for tKOIAgent.

Provides tools to check and setup R, tKOI, and Homebrew.
"""

import subprocess
from pathlib import Path
from utils.r_executor import RExecutor, RExecutionError
from utils.logger import get_logger

logger = get_logger(__name__)


def check_r_installation() -> dict:
    """
    Check if R is installed and available.

    Returns:
        Dictionary with R installation status and version
    """
    try:
        # Try to find R executable
        for cmd in ["R", "/usr/local/bin/R", "/usr/bin/R", "/opt/homebrew/bin/R"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    path_result = subprocess.run(
                        ["which", cmd],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    r_path = path_result.stdout.strip() if path_result.returncode == 0 else cmd

                    logger.info(f"R is installed: {version_line}")
                    return {
                        "installed": True,
                        "version": version_line,
                        "path": r_path
                    }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return {
            "installed": False,
            "message": "R not found in common locations",
            "instructions": {
                "macos": "Install via Homebrew: brew install r",
                "linux": "Install via apt: sudo apt-get install r-base",
                "windows": "Download from https://cran.r-project.org/bin/windows/base/"
            }
        }

    except Exception as e:
        logger.error(f"Error checking R installation: {e}")
        return {
            "installed": False,
            "error": str(e)
        }


def check_tkoi_installation() -> dict:
    """
    Check if tKOI R package is installed.

    Returns:
        Dictionary with tKOI installation status
    """
    try:
        # First check if R is available
        r_check = check_r_installation()
        if not r_check.get("installed"):
            return {
                "installed": False,
                "message": "R is not installed. Please install R first.",
                "r_status": r_check
            }

        # Execute R script to check tKOI
        executor = RExecutor(Path(__file__).parent.parent / "scripts")
        result = executor.execute_script("check_tkoi.R", timeout=30)

        logger.info(f"tKOI check: {result.get('message', 'Complete')}")
        return result

    except RExecutionError as e:
        logger.error(f"Error checking tKOI: {e}")
        return {
            "installed": False,
            "error": str(e),
            "stderr": e.stderr
        }
    except Exception as e:
        logger.error(f"Unexpected error checking tKOI: {e}")
        return {
            "installed": False,
            "error": str(e)
        }


def install_tkoi_package(github_repo: str = "default/tkoi") -> dict:
    """
    Install tKOI R package from GitHub.

    Args:
        github_repo: GitHub repository path (user/repo)

    Returns:
        Installation result dictionary
    """
    logger.info(f"Installing tKOI from {github_repo}...")

    try:
        # Check R installation first
        r_check = check_r_installation()
        if not r_check.get("installed"):
            return {
                "success": False,
                "message": "R is not installed. Please install R first.",
                "r_status": r_check
            }

        # Execute R script to install tKOI
        executor = RExecutor(Path(__file__).parent.parent / "scripts")
        result = executor.execute_script(
            "install_tkoi.R",
            args={"repo": github_repo},
            timeout=600  # 10 minutes for installation
        )

        if result.get('success'):
            logger.info("tKOI installed successfully")
        else:
            logger.warning(f"Installation issues: {result.get('message')}")

        return result

    except RExecutionError as e:
        logger.error(f"Error installing tKOI: {e}")
        return {
            "success": False,
            "error": str(e),
            "stderr": e.stderr
        }
    except Exception as e:
        logger.error(f"Unexpected error installing tKOI: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def check_homebrew() -> dict:
    """
    Check if Homebrew is installed (macOS/Linux).

    Returns:
        Homebrew installation status
    """
    try:
        result = subprocess.run(
            ["brew", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            logger.info(f"Homebrew is installed: {version}")
            return {
                "installed": True,
                "version": version
            }
        else:
            return {
                "installed": False,
                "message": "Homebrew command failed"
            }

    except FileNotFoundError:
        logger.info("Homebrew not found")
        return {
            "installed": False,
            "message": "Homebrew not found",
            "instructions": "Install from https://brew.sh"
        }
    except Exception as e:
        logger.error(f"Error checking Homebrew: {e}")
        return {
            "installed": False,
            "error": str(e)
        }
