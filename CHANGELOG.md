# Changelog

All notable changes to TreeLS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2025-06-21

### Added
- **Version Information**: New `--version/-v` command-line argument
- **Dynamic Version Detection**: Automatic version reading from package metadata using `importlib.metadata`

### Fixed
- **Documentation**: Updated README.md installation instructions to use correct package name `treels-cli`
- **Package References**: All documentation now consistently references the correct PyPI package name
- **CLI Standards**: Added standard version argument following conventional CLI patterns

### Technical
- Improved CLI interface with proper version reporting
- Enhanced user experience with easy version verification
- Better package name consistency across all documentation

## [1.0.0] - 2025-06-21

### Added
- Initial release of TreeLS
- Directory tree visualization with rich terminal output
- Git status integration with PyCharm-style color coding
- Smart filtering options for Git status (`--only-staged`, `--only-modified`, etc.)
- .gitignore pattern matching and respect
- Comprehensive command-line interface with depth limiting
- Custom ignore patterns and directory highlighting
- Extensive test suite with mocked Git operations
- Professional documentation with usage examples
- Cross-platform support (Linux, macOS, Windows)
- Python 3.8+ compatibility

### Features
- **Git Integration**: Color-coded file status (red=untracked, green=staged, yellow=modified)
- **Filtering**: Combine multiple `--only-*` flags with OR logic
- **Safety**: Hides .git folder and respects .gitignore by default
- **Flexibility**: Show hidden files, custom ignore patterns, max depth
- **Performance**: Fast traversal with efficient Git status checking
- **UX**: Rich terminal output with legends and helpful messages

### Technical
- Built with Rich library for beautiful terminal output
- Comprehensive error handling and permission checks
- Safe default behaviors for production use
- Modular architecture with separate Git and tree printing classes
- Extensive test coverage with temporary directory isolation

[Unreleased]: https://github.com/faizananwerali/treels/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/faizananwerali/treels/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/faizananwerali/treels/releases/tag/v1.0.0