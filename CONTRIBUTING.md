# Contributing to robotframework-trace-viewer

Thank you for your interest in contributing to robotframework-trace-viewer! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Contributing Code](#contributing-code)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

This project adheres to a code of conduct that all contributors are expected to follow. Please be respectful and constructive in all interactions.

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates. When creating a bug report, use the bug report template and include as much detail as possible:

- Clear and descriptive title
- Exact steps to reproduce the problem
- Expected behavior
- Actual behavior
- Environment details (Python version, Robot Framework version, OS)
- Screenshots or traces if applicable

### Suggesting Features

Feature suggestions are welcome! Please use the feature request template and include:

- Clear description of the feature
- Use case and motivation
- Proposed solution or implementation approach
- Alternative solutions you've considered

### Contributing Code

Code contributions are greatly appreciated! Please follow the development workflow and code standards outlined below.

## Development Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/robotframework-trace-viewer.git
   cd robotframework-trace-viewer
   ```

3. Install the package in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Create a branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

1. Make your changes in your feature branch
2. Add or update tests as needed
3. Run the test suite:
   ```bash
   pytest tests/
   ```

4. Format your code:
   ```bash
   black src/ tests/ --line-length=100
   ```

5. Run the linter:
   ```bash
   ruff check src/ tests/
   ```

6. Run type checking:
   ```bash
   mypy src/
   ```

7. Commit your changes (see commit guidelines below)
8. Push to your fork
9. Submit a pull request

## Code Standards

### Python Code Style

- **Formatter**: Black with line-length=100
- **Linter**: Ruff
- **Type hints**: Required for all public functions and methods
- **Docstrings**: Google style for all public functions and classes

### Naming Conventions

- **Modules**: snake_case (`trace_listener.py`)
- **Classes**: PascalCase (`TraceListener`)
- **Functions/methods**: snake_case (`capture_screenshot`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_OUTPUT_DIR`)

### Testing

- All new features must include tests
- Aim for high test coverage
- Tests should be runnable without a browser (use mocks for Selenium)
- Use pytest as the testing framework

### Documentation

- Update README.md if adding user-facing features
- Add docstrings to all public APIs
- Update PLANNING.md for architectural changes
- Update TASKS.md when completing tasks

## Commit Message Guidelines

Use the following format for commit messages:

```
type(scope): description

[optional body]

[optional footer]
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding or updating tests
- `chore`: Changes to build process or auxiliary tools

### Examples

```
feat(listener): add screenshot capture on keyword end
fix(storage): handle unicode in test names
docs(readme): add installation instructions
test(listener): add tests for keyword timing
refactor(capture): simplify screenshot capture logic
```

## Pull Request Process

1. Ensure all tests pass and code meets quality standards
2. Update documentation as needed
3. Fill out the pull request template completely
4. Link any related issues
5. Wait for review from maintainers
6. Address any review comments
7. Once approved, a maintainer will merge your PR

### Pull Request Checklist

- [ ] Tests added/updated and passing
- [ ] Code formatted with Black
- [ ] No linting errors from Ruff
- [ ] Type checking passes with mypy
- [ ] Documentation updated
- [ ] Commit messages follow guidelines
- [ ] PR description clearly explains the changes

## Questions?

If you have questions about contributing, feel free to open an issue with your question or reach out to the maintainers.

Thank you for contributing to robotframework-trace-viewer!
