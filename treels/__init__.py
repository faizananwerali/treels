"""TreeLS - Enhanced Directory Tree Tool with Git Integration"""

__version__ = "1.1.1"
__author__ = "Faizan Ali"
__description__ = (
    "Enhanced directory tree printer with Git integration and ls-like features"
)

from .main import main, DirectoryTreePrinter, GitRepository

__all__ = ["main", "DirectoryTreePrinter", "GitRepository"]
