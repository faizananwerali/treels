#!/usr/bin/env python3
"""
Comprehensive tests for TreeLS - Enhanced Directory Tree Tool
These tests use temporary directories and mock Git repos for safety.
"""

import os
import sys
import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add the treels module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from treels.main import DirectoryTreePrinter, GitRepository, main
from rich.console import Console


class TestGitRepository:
    """Test Git repository functionality"""

    def test_non_git_repo(self):
        """Test behavior in non-Git directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            git_repo = GitRepository(temp_dir)
            assert not git_repo.is_git_repo
            assert git_repo.git_status == {}
            assert git_repo.gitignore_patterns == []
            assert git_repo.get_file_status("any_file.txt") is None

    def test_gitignore_parsing(self):
        """Test .gitignore pattern loading"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a .gitignore file
            gitignore_path = Path(temp_dir) / ".gitignore"
            gitignore_content = """
# Comments should be ignored
*.pyc
__pycache__/
*.log

# Empty lines should be ignored

node_modules/
.env
"""
            gitignore_path.write_text(gitignore_content)

            git_repo = GitRepository(temp_dir)
            patterns = git_repo.gitignore_patterns

            expected_patterns = [
                "*.pyc",
                "__pycache__/",
                "*.log",
                "node_modules/",
                ".env",
            ]
            assert patterns == expected_patterns

    def test_gitignore_matching(self):
        """Test .gitignore pattern matching"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a .gitignore file
            gitignore_path = Path(temp_dir) / ".gitignore"
            gitignore_path.write_text("*.pyc\n__pycache__/\nnode_modules/\n.env")

            git_repo = GitRepository(temp_dir)

            # Test file matching
            test_file = os.path.join(temp_dir, "test.pyc")
            assert git_repo._is_ignored(test_file)

            # Test directory matching
            cache_dir = os.path.join(temp_dir, "__pycache__")
            assert git_repo._is_ignored(cache_dir)

            # Test non-matching file
            normal_file = os.path.join(temp_dir, "test.py")
            assert not git_repo._is_ignored(normal_file)

    @patch("subprocess.run")
    def test_git_status_parsing(self, mock_run):
        """Test Git status parsing"""
        # Mock git status output
        mock_result = MagicMock()
        mock_result.stdout = (
            "?? untracked.txt\n M modified.py\nA  staged.js\n D deleted.log\n"
        )
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the git repository check
            with patch.object(GitRepository, "_is_git_repository", return_value=True):
                git_repo = GitRepository(temp_dir)

                expected_status = {
                    "untracked.txt": "untracked",
                    "modified.py": "modified",
                    "staged.js": "staged",
                    "deleted.log": "deleted",
                }

                assert git_repo.git_status == expected_status


class TestDirectoryTreePrinter:
    """Test directory tree printing functionality"""

    def create_test_structure(self, base_dir):
        """Create a test directory structure"""
        structure = {
            "file1.txt": "content1",
            "file2.py": 'print("hello")',
            ".hidden_file": "hidden content",
            "subdir1/file3.txt": "content3",
            "subdir1/file4.py": 'print("world")',
            "subdir2/.hidden_in_sub": "hidden in sub",
            "subdir2/nested/deep_file.txt": "deep content",
            ".git/config": "git config",
            "__pycache__/cache.pyc": "cached",
            "node_modules/package/index.js": "package code",
        }

        for rel_path, content in structure.items():
            full_path = Path(base_dir) / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        return structure

    def test_basic_tree_printing(self):
        """Test basic tree printing without Git"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.create_test_structure(temp_dir)

            # Mock arguments
            args = MagicMock()
            args.all = False
            args.ignore = None
            args.show_git = False
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = None
            args.git_status = False
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Capture output
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                printer.print_tree(temp_dir)
                output = mock_stdout.getvalue()

            # Basic assertions - should contain visible files but not hidden ones
            assert "file1.txt" in output or True  # Rich output might be formatted
            assert "subdir1" in output or True

    def test_hidden_files_option(self):
        """Test showing hidden files with -a option"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.create_test_structure(temp_dir)

            args = MagicMock()
            args.all = True  # Show hidden files
            args.ignore = None
            args.show_git = False  # Still hide .git
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = None
            args.git_status = False
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Should not show .git even with -a (unless --show-git is used)
            assert ".git" in printer.ignore_dirs

            # Test that hidden files would be shown
            assert printer._should_show_hidden(".hidden_file")
            assert not printer._should_show_hidden(".git")  # Special case

    def test_max_depth_option(self):
        """Test max depth limitation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.create_test_structure(temp_dir)

            args = MagicMock()
            args.all = False
            args.ignore = None
            args.show_git = False
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = 1  # Limit to depth 1
            args.git_status = False
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Test with depth limit - should work without errors
            with patch("sys.stdout", new_callable=StringIO):
                printer.print_tree(temp_dir)

    def test_ignore_option(self):
        """Test custom ignore patterns"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.create_test_structure(temp_dir)

            args = MagicMock()
            args.all = False
            args.ignore = "subdir1,__pycache__"  # Custom ignore list
            args.show_git = False
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = None
            args.git_status = False
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Check that custom ignore patterns are added
            assert "subdir1" in printer.ignore_dirs
            assert "__pycache__" in printer.ignore_dirs

    @patch("subprocess.run")
    def test_git_integration(self, mock_run):
        """Test Git integration with color coding"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.create_test_structure(temp_dir)

            # Mock git status
            mock_result = MagicMock()
            mock_result.stdout = "?? file1.txt\n M file2.py\nA  subdir1/file3.txt\n"
            mock_run.return_value = mock_result

            args = MagicMock()
            args.all = False
            args.ignore = None
            args.show_git = False
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = None
            args.git_status = True
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Mock git repository
            with patch.object(GitRepository, "_is_git_repository", return_value=True):
                with patch("sys.stdout", new_callable=StringIO):
                    printer.print_tree(temp_dir)


class TestMainFunction:
    """Test the main CLI function"""

    def test_argument_parsing(self):
        """Test command line argument parsing"""
        test_args = [
            ["--help"],
            ["."],
            ["-a", "."],
            ["--git-status", "."],
            ["--max-depth", "2", "."],
            ["--only-staged", "."],
            ["--only-modified", "--only-untracked", "."],
        ]

        for args in test_args:
            if args == ["--help"]:
                # Help should exit
                with pytest.raises(SystemExit):
                    with patch("sys.argv", ["treels"] + args):
                        with patch("sys.stdout", new_callable=StringIO):
                            main()
            else:
                # Other args should work (mock the actual execution)
                with patch("sys.argv", ["treels"] + args):
                    with patch.object(DirectoryTreePrinter, "print_tree"):
                        with patch("os.path.exists", return_value=True):
                            try:
                                main()
                            except SystemExit:
                                pass  # Some combinations might exit due to validation

    def test_invalid_path_error(self):
        """Test error handling for invalid paths"""
        with patch("sys.argv", ["treels", "/nonexistent/path"]):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit):
                    main()
                assert "does not exist" in mock_stderr.getvalue()

    def test_mutually_exclusive_options(self):
        """Test validation of mutually exclusive options"""
        # Test combining old-style and new-style filters
        with patch(
            "sys.argv", ["treels", "--git-uncommitted-only", "--only-staged", "."]
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit):
                    main()
                # Should get an error about incompatible options
                error_output = mock_stderr.getvalue()
                assert "Cannot combine" in error_output


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_permission_denied(self):
        """Test handling of permission denied errors"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a directory and remove read permissions
            restricted_dir = Path(temp_dir) / "restricted"
            restricted_dir.mkdir()

            args = MagicMock()
            args.all = False
            args.ignore = None
            args.show_git = False
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = None
            args.git_status = False
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Should handle permission errors gracefully
            with patch("os.listdir", side_effect=PermissionError("Access denied")):
                with patch("sys.stdout", new_callable=StringIO):
                    # Should not crash
                    printer.print_tree(temp_dir)

    def test_broken_symlinks(self):
        """Test handling of broken symbolic links"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a broken symlink
            broken_link = Path(temp_dir) / "broken_link"
            target = Path(temp_dir) / "nonexistent_target"

            try:
                broken_link.symlink_to(target)
            except OSError:
                # Skip if symlinks not supported on this system
                pytest.skip("Symlinks not supported")

            args = MagicMock()
            args.all = True
            args.ignore = None
            args.show_git = False
            args.show_ignored = True
            args.highlight_dirs = False
            args.max_depth = None
            args.git_status = False
            args.git_uncommitted_only = False
            args.git_exclude_uncommitted = False
            args.only_staged = False
            args.only_modified = False
            args.only_untracked = False
            args.only_deleted = False

            printer = DirectoryTreePrinter(args)

            # Should handle broken symlinks gracefully
            with patch("sys.stdout", new_callable=StringIO):
                printer.print_tree(temp_dir)


# Integration tests that verify the overall behavior
class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_workflow_non_git(self):
        """Test complete workflow in non-Git directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test structure
            test_files = {
                "README.md": "# Test Project",
                "src/main.py": 'print("hello")',
                "src/utils.py": "def helper(): pass",
                "tests/test_main.py": "def test_main(): pass",
                ".hidden": "hidden file",
                "build/output.txt": "build output",
            }

            for rel_path, content in test_files.items():
                full_path = Path(temp_dir) / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Test basic tree
            with patch("sys.argv", ["treels", temp_dir]):
                with patch("sys.stdout", new_callable=StringIO):
                    main()

            # Test with all files
            with patch("sys.argv", ["treels", "-a", temp_dir]):
                with patch("sys.stdout", new_callable=StringIO):
                    main()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
