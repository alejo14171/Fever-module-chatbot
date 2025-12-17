---
layout: default
title: Contributing
nav_order: 5
---

# Contributing to Docokids

Thank you for your interest in contributing to the Docokids project! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please read it before contributing.

## How to Contribute

### 1. Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/Fever-module-chatbot.git
   cd Fever-module-chatbot
   ```

### 2. Set Up Development Environment (Recommended with uv)

1. Install [uv](https://github.com/astral-sh/uv).

2. Sync dependencies:
   ```bash
   uv sync
   ```

3. (Optional) Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```

### 3. Create a Branch

Create a feature branch for your changes:
```bash
git checkout -b feature/your-feature-name
```

### 4. Make Changes

1. Make your changes following our coding standards
2. Write or update tests as needed
3. Update documentation if necessary

### 5. Run Tests

```bash
uv run pytest
uv run black . --check
```

### 6. Commit Changes

Follow our commit message format:
```
type(scope): description

[optional body]

[optional footer]
```

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes
- refactor: Code refactoring
- test: Adding or updating tests
- chore: Maintenance tasks

### 7. Push and Create Pull Request

1. Push your changes:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Create a Pull Request on GitHub

## Development Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all functions and classes
- Keep functions small and focused
- Use meaningful variable names

### Testing

- Write unit tests for new nodes or logic in `src/fever_routing/`
- Maintain test coverage above 80%
- Test edge cases and error conditions

### Documentation

- Update README.md if needed
- Add or update API documentation
- Include docstrings for new functions
- Update CHANGELOG.md for significant changes

## Review Process

1. All PRs require at least one review
2. CI checks must pass
3. Code coverage must not decrease
4. Documentation must be updated
5. Tests must be included

## Getting Help

- Open an issue for bugs or feature requests
- Join our community chat
- Contact the maintainers at agomez@docokids.com

## License

By contributing, you agree that your contributions will be licensed under the project's GNU GPL v3.0 License.

---

## Issues & Feature Requests

If you find a bug or want to suggest an improvement, please use our issue templates:

- [Report a Bug](https://github.com/alejo14171/Fever-module-chatbot/issues/new?template=bug_report.md): For reporting errors or unexpected behavior in the pediatric fever chatbot. Please provide as much detail as possible.
- [Request a Feature](https://github.com/alejo14171/Fever-module-chatbot/issues/new?template=feature_request.md): For suggesting new features or improvements. Tell us how your idea could help users or improve the project.

This helps us keep the project organized and ensures your feedback is addressed efficiently.
