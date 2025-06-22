#!/usr/bin/env python3
"""Enhanced Directory Tree Printer with Git integration"""

import os
import sys
import subprocess
import fnmatch
from pathlib import Path
from typing import Set, Optional, Dict, List
from rich.tree import Tree
from rich import print
from rich.console import Console
from rich.text import Text
from importlib.metadata import version, PackageNotFoundError
import argparse


def get_version():
    try:
        return version("treels-cli")  # Your package name on PyPI
    except PackageNotFoundError:
        return "unknown"


class GitRepository:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.is_git_repo = self._is_git_repository()
        self.git_status = self._get_git_status() if self.is_git_repo else {}
        self.git_status_codes = self._get_git_status_codes() if self.is_git_repo else {}
        self.gitignore_patterns = (
            self._load_gitignore_patterns() if self.is_git_repo else []
        )

    def _is_git_repository(self) -> bool:
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _load_gitignore_patterns(self) -> List[str]:
        """Load patterns from .gitignore file"""
        patterns = []
        gitignore_path = self.repo_path / ".gitignore"

        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except (IOError, UnicodeDecodeError):
                pass

        return patterns

    def _is_ignored(self, file_path: str) -> bool:
        """Check if file matches any .gitignore pattern"""
        if not self.gitignore_patterns:
            return False

        try:
            rel_path = os.path.relpath(file_path, self.repo_path)
            file_name = os.path.basename(rel_path)

            for pattern in self.gitignore_patterns:
                # Handle directory patterns
                if pattern.endswith("/"):
                    if fnmatch.fnmatch(rel_path + "/", pattern) or fnmatch.fnmatch(
                        file_name + "/", pattern
                    ):
                        return True
                else:
                    # Match against relative path and filename
                    if (
                        fnmatch.fnmatch(rel_path, pattern)
                        or fnmatch.fnmatch(file_name, pattern)
                        or fnmatch.fnmatch("/" + rel_path, "/" + pattern)
                    ):
                        return True

            return False
        except ValueError:
            return False

    def _get_git_status_codes(self) -> Dict[str, str]:
        """Get raw Git status codes for each file"""
        if not self.is_git_repo:
            return {}

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            status_codes = {}
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                status_code = line[:2]
                file_path = line[3:]
                status_codes[file_path] = status_code

            return status_codes
        except subprocess.CalledProcessError:
            return {}

    def _get_git_status(self) -> Dict[str, str]:
        if not self.is_git_repo:
            return {}

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            status_map = {}
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                status_code = line[:2]
                file_path = line[3:]

                # Parse git status codes more precisely
                if status_code == "??":
                    status_map[file_path] = "untracked"  # Red (not in VCS)
                elif status_code[0] == "A":
                    status_map[file_path] = "staged"  # Green (staged for commit)
                elif status_code[0] == "M":
                    status_map[file_path] = "staged"  # Green (staged modifications)
                elif status_code[1] == "M":
                    status_map[file_path] = (
                        "modified"  # Yellow (modified but not staged)
                    )
                elif status_code[0] == "D":
                    status_map[file_path] = "deleted"  # Dark grey (deleted and staged)
                elif status_code[1] == "D":
                    status_map[file_path] = (
                        "deleted"  # Dark grey (deleted but not staged)
                    )
                elif status_code == " D":
                    status_map[file_path] = "deleted"  # Dark grey (deleted)
                elif status_code == "D ":
                    status_map[file_path] = "deleted"  # Dark grey (deleted)
                else:
                    status_map[file_path] = "unknown"

            return status_map
        except subprocess.CalledProcessError:
            return {}

    def get_file_status(self, file_path: str) -> Optional[str]:
        if not self.is_git_repo:
            return None

        try:
            rel_path = os.path.relpath(file_path, self.repo_path)
            return self.git_status.get(rel_path)
        except ValueError:
            return None

    def get_file_status_code(self, file_path: str) -> Optional[str]:
        """Get the raw Git status code for a file"""
        if not self.is_git_repo:
            return None

        try:
            rel_path = os.path.relpath(file_path, self.repo_path)
            return self.git_status_codes.get(rel_path, "  ")  # Default to spaces
        except ValueError:
            return "  "


class DirectoryTreePrinter:
    def __init__(self, args):
        self.args = args
        self.console = Console()
        self.visited = set()
        self.git_repo = None

        self.ignore_dirs = set()
        if args.ignore:
            self.ignore_dirs = set(args.ignore.split(","))

        if not args.all:
            self.ignore_dirs.update(
                {".git", "__pycache__", ".DS_Store", "node_modules"}
            )

    def _should_show_hidden(self, name: str) -> bool:
        """Check if hidden files should be shown"""
        if not name.startswith("."):
            return True

        # Always hide .git folder unless explicitly requested
        if name == ".git" and not self.args.show_git:
            return False

        return self.args.all

    def _should_show_ignored(self, full_path: str) -> bool:
        """Check if gitignored files should be shown"""
        if not self.git_repo or not self.git_repo.is_git_repo:
            return True

        is_ignored = self.git_repo._is_ignored(full_path)
        if not is_ignored:
            return True

        # Show ignored files only if --show-ignored is specified
        return self.args.show_ignored

    def _get_file_display_name(self, name: str, full_path: str, is_dir: bool) -> Text:
        text = Text()

        # Get status code if requested
        status_code = ""
        if self.args.show_status_codes and self.git_repo and self.git_repo.is_git_repo:
            raw_code = self.git_repo.get_file_status_code(full_path)
            if raw_code and raw_code != "  ":
                status_code = raw_code + " "
            else:
                status_code = "   "  # 3 spaces for alignment when no status

        if is_dir:
            display_name = status_code + name + "/"
            if self.args.highlight_dirs:
                text.append(display_name, style="bold blue")
            else:
                text.append(display_name)  # No color for directories by default
        else:
            # Default color for files
            file_style = None

            # If in a git repo, apply git status colors (PyCharm style)
            if self.git_repo and self.git_repo.is_git_repo:
                status = self.git_repo.get_file_status(full_path)
                if status == "untracked":
                    file_style = "red"  # Red: not in VCS
                elif status == "staged":
                    file_style = "green"  # Green: staged for commit
                elif status == "modified":
                    file_style = "yellow"  # Yellow: modified but not staged
                elif status == "deleted":
                    file_style = "bright_black"  # Dark grey: deleted files
                # If status is None (committed files), use no special color
            else:
                # Not in git repo - show in grey
                file_style = "dim"

            display_name = status_code + name

            if file_style:
                text.append(display_name, style=file_style)
            else:
                text.append(display_name)  # Default color for committed files

        return text

    def _should_include_by_git_filter(self, full_path: str) -> bool:
        if not self.git_repo or not self.git_repo.is_git_repo:
            return True

        status = self.git_repo.get_file_status(full_path)

        # Handle the old-style filters (mutually exclusive)
        if self.args.git_uncommitted_only:
            # Show only files with any kind of changes
            return status in ["staged", "modified", "deleted", "untracked"]
        elif self.args.git_exclude_uncommitted:
            # Show only committed files (no git status = committed)
            return status is None

        # Handle the new specific filters (can be combined with OR logic)
        specific_filters = []
        if self.args.only_staged:
            specific_filters.append("staged")
        if self.args.only_modified:
            specific_filters.append("modified")
        if self.args.only_untracked:
            specific_filters.append("untracked")
        if self.args.only_deleted:
            specific_filters.append("deleted")

        # If any specific filters are active, use OR logic
        if specific_filters:
            return status in specific_filters

        # No filters active - show all files
        return True

    def _directory_has_matching_files(self, path: str) -> bool:
        """Check if directory contains files that match current filters"""
        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)

                if entry in self.ignore_dirs:
                    continue

                if not self._should_show_hidden(entry):
                    continue

                if not self._should_show_ignored(full_path):
                    continue

                if os.path.isfile(full_path):
                    if self._should_include_by_git_filter(full_path):
                        return True
                elif os.path.isdir(full_path) and not os.path.islink(full_path):
                    if self._directory_has_matching_files(full_path):
                        return True
            return False
        except (PermissionError, OSError):
            return False

    def build_tree(self, path: str, tree: Tree):
        try:
            entries = os.listdir(path)

            # Separate directories and files, then sort each alphabetically
            directories = []
            files = []

            for entry in entries:
                full_path = os.path.join(path, entry)

                if entry in self.ignore_dirs:
                    continue

                if not self._should_show_hidden(entry):
                    continue

                if not self._should_show_ignored(full_path):
                    continue

                if os.path.isdir(full_path) and not os.path.islink(full_path):
                    directories.append(entry)
                elif os.path.isfile(full_path):
                    files.append(entry)

            # Sort both lists alphabetically
            directories.sort()
            files.sort()

            # Process directories first
            for entry in directories:
                full_path = os.path.join(path, entry)
                inode = os.stat(full_path).st_ino
                if inode in self.visited:
                    continue
                self.visited.add(inode)

                # Only show directory if it has matching files (when any git filters are active)
                if (
                    self.args.git_uncommitted_only
                    or self.args.git_exclude_uncommitted
                    or self.args.only_staged
                    or self.args.only_modified
                    or self.args.only_untracked
                    or self.args.only_deleted
                ):
                    if not self._directory_has_matching_files(full_path):
                        continue

                display_name = self._get_file_display_name(entry, full_path, True)
                subtree = tree.add(display_name)

                if self.args.max_depth is None or self.args.max_depth > 1:
                    old_depth = self.args.max_depth
                    if self.args.max_depth is not None:
                        self.args.max_depth -= 1

                    self.build_tree(full_path, subtree)
                    self.args.max_depth = old_depth

            # Then process files
            for entry in files:
                full_path = os.path.join(path, entry)

                # Apply git filter only to files
                if not self._should_include_by_git_filter(full_path):
                    continue

                display_name = self._get_file_display_name(entry, full_path, False)
                tree.add(display_name)

        except PermissionError:
            tree.add(Text("Permission denied", style="red"))
        except Exception as e:
            tree.add(Text(f"Error: {str(e)}", style="red"))

    def print_tree(self, root_path: str):
        root_path = os.path.abspath(root_path)

        # Always initialize git repo to check for colors
        self.git_repo = GitRepository(root_path)

        root_display = Text(root_path, style="bold magenta")
        if self.git_repo and self.git_repo.is_git_repo:
            root_display.append(" [dim](git)[/]")

        tree = Tree(root_display)
        self.build_tree(root_path, tree)
        self.console.print(tree)

        # Only show legend when explicitly requested with --git-status
        if self.args.git_status and self.git_repo and self.git_repo.is_git_repo:
            self._print_git_legend()

    def _print_git_legend(self):
        legend = Text("\nGit Status: ", style="bold")
        legend.append("Red=Untracked  ", style="red")
        legend.append("Green=Staged  ", style="green")
        legend.append("Yellow=Modified  ", style="yellow")
        legend.append("Dark Grey=Deleted  ", style="bright_black")
        legend.append("Default=Committed  ", style="default")
        legend.append("Grey=Non-Git", style="dim")

        legend.append("\n\nFilter Options: ", style="bold")
        legend.append(
            "--only-staged --only-modified --only-untracked --only-deleted",
            style="cyan",
        )
        legend.append("\n(Combine multiple filters with OR logic)", style="dim")

        if self.args.show_status_codes:
            legend.append("\n\nStatus Codes: ", style="bold")
            legend.append("?? = Untracked, A  = Staged, ", style="dim")
            legend.append(" M = Modified,  D = Deleted", style="dim")

        if not self.args.show_ignored:
            legend.append(
                "\nNote: .gitignore files are hidden (use --show-ignored to show)",
                style="dim",
            )

        if not self.args.show_git:
            legend.append(
                "\nNote: .git folder is hidden (use --show-git to show)", style="dim"
            )

        self.console.print(legend)


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Directory Tree Printer with Git integration",
        epilog="Examples:\n"
        "  treels                                    # Basic tree (respects .gitignore, hides .git)\n"
        "  treels -a                                 # Show hidden files (but not .git)\n"
        "  treels -a --show-git                      # Show all files including .git folder\n"
        "  treels --git-status                       # Show git status legend\n"
        "  treels --show-status-codes                # Show git status codes before filenames\n"
        "  treels --only-staged                      # Show only staged files (green)\n"
        "  treels --only-modified                    # Show only modified files (yellow)\n"
        "  treels --only-untracked                   # Show only untracked files (red)\n"
        "  treels --only-deleted                     # Show only deleted files (dark grey)\n"
        "  treels --only-staged --only-modified      # Show staged OR modified files\n"
        "  treels --only-untracked --only-modified   # Show untracked OR modified files\n"
        "  treels --git-uncommitted-only             # Show any files with changes\n"
        "  treels --git-exclude-uncommitted          # Show only committed files\n"
        "  treels --show-status-codes --git-status   # Show codes + colors + legend\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add version argument - this should be one of the first arguments
    parser.add_argument(
        "-v", "--version", action="version", version=f"treels {get_version()}"
    )

    parser.add_argument(
        "path", nargs="?", default=".", help="Root path (default: current directory)"
    )

    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show hidden files and directories (starting with .)",
    )

    parser.add_argument(
        "--show-ignored", action="store_true", help="Show files ignored by .gitignore"
    )

    parser.add_argument(
        "--show-git",
        action="store_true",
        help="Show .git folder (hidden by default even with -a)",
    )

    parser.add_argument(
        "--show-status-codes",
        action="store_true",
        help="Show git status codes before filenames (like git status --short)",
    )

    parser.add_argument(
        "--ignore", type=str, help="Comma-separated list of directories to ignore"
    )

    parser.add_argument("--max-depth", type=int, help="Maximum depth to traverse")

    parser.add_argument(
        "--git-status",
        action="store_true",
        help="Show git status legend (colors always shown in git repos)",
    )

    parser.add_argument(
        "--git-uncommitted-only",
        action="store_true",
        help="Show only uncommitted files",
    )

    parser.add_argument(
        "--git-exclude-uncommitted",
        action="store_true",
        help="Exclude uncommitted files (show only committed files)",
    )

    parser.add_argument(
        "--only-staged", action="store_true", help="Show only staged files (green)"
    )

    parser.add_argument(
        "--only-modified", action="store_true", help="Show only modified files (yellow)"
    )

    parser.add_argument(
        "--only-untracked", action="store_true", help="Show only untracked files (red)"
    )

    parser.add_argument(
        "--only-deleted",
        action="store_true",
        help="Show only deleted files (dark grey)",
    )

    parser.add_argument(
        "--highlight-dirs", action="store_true", help="Highlight directories in blue"
    )

    args = parser.parse_args()

    # Validate git filter combinations
    old_style_filters = [args.git_uncommitted_only, args.git_exclude_uncommitted]
    specific_filters = [
        args.only_staged,
        args.only_modified,
        args.only_untracked,
        args.only_deleted,
    ]

    # Don't allow mixing old-style filters with specific filters
    if sum(old_style_filters) > 0 and sum(specific_filters) > 0:
        parser.error(
            "Cannot combine --git-uncommitted-only or --git-exclude-uncommitted with specific --only-* filters"
        )

    # Don't allow multiple old-style filters
    if sum(old_style_filters) > 1:
        parser.error(
            "Cannot use --git-uncommitted-only and --git-exclude-uncommitted together"
        )

    if not os.path.exists(args.path):
        print(f"Error: Path '{args.path}' does not exist", file=sys.stderr)
        sys.exit(1)

    printer = DirectoryTreePrinter(args)
    printer.print_tree(args.path)


if __name__ == "__main__":
    main()
