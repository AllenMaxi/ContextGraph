# Contributing to ContextGraph

Thank you for your interest in contributing to ContextGraph! This document provides guidelines and instructions for contributing to the project.

## Getting Started

1. **Read the README** to understand the project architecture and goals.
2. **Check existing issues** for something you'd like to work on, or open a new one to discuss your idea.
3. **Review the [Code of Conduct](CODE_OF_CONDUCT.md)** before participating.

## Development Setup

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/AllenMaxi/ContextGraph.git
cd contextgraph

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the project with all development dependencies
pip install -e ".[server,neo4j,dev]"

# Copy the example environment file
cp .env.example .env
```

## Running Tests

```bash
# Run the full test suite
make test

# Run a specific test file
python -m pytest tests/test_service.py -v

# Run with coverage
python -m pytest tests/ -v --cov=contextgraph --cov-report=html
```

Web API tests require the `server` extra. Neo4j integration tests require `CG_RUN_NEO4J_TESTS=1` plus a reachable Neo4j instance.

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Configuration lives in `pyproject.toml`.

```bash
# Check for lint errors
make lint

# Auto-format code
make format
```

All code must pass `make lint` before being merged. Type hints are strongly encouraged throughout the codebase.

## Commit Messages

This project uses **conventional commits**. Please format your commit messages as:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`.

Examples:
- `feat(api): add granular permissions for cross-company sharing`
- `fix(extractor): handle empty input gracefully`
- `docs: update installation instructions`

## Pull Request Process

1. **Fork** the repository and create your branch from `main`.
2. **Write tests** for any new functionality.
3. **Run the full test suite** (`make test`) and ensure all tests pass.
4. **Run the linter** (`make lint`) and fix any issues.
5. **Write a clear PR description** explaining what changed and why.
6. **Keep PRs focused** — one feature or fix per PR.
7. **Link related issues** in your PR description (e.g., `Closes #42`).

A maintainer will review your PR as soon as possible. We may suggest changes or improvements before merging.

## Reporting Issues

- Use **GitHub Issues** for bugs and feature requests.
- Include steps to reproduce any bugs.
- Mention your Python version and operating system.
- Include relevant logs or error messages.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.
