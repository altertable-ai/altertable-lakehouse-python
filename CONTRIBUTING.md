# Contributing to altertable-lakehouse

## Development Setup

1. Fork and clone the repository
2. Install dependencies: `poetry install`
3. Run tests: `poetry run pytest`

## Making Changes

1. Create a branch from `main`
2. Make your changes
3. Add or update tests
4. Run the full check suite: `poetry run ruff check . && poetry run mypy . && poetry run pytest`
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, etc.)
6. Open a pull request

## Code Style

This project uses `Ruff` for linting and `Ruff` for formatting. Run `poetry run ruff check .` before committing.

## Tests

- Unit tests are required for all new functionality
- Integration tests run in CI when credentials are available
- Run tests locally: `poetry run pytest`

## Pull Requests

- Keep PRs focused on a single change
- Update `CHANGELOG.md` under `[Unreleased]`
- Ensure CI passes before requesting review
