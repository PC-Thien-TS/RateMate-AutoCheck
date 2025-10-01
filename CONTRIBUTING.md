# CONTRIBUTING to RateMate-AutoCheck

Thank you for considering contributing!

## Getting Started
- Clone the repository and install dependencies:
  ```bash
  pip install -r requirements.txt
  cp .env.example .env  # Fill in required secrets
  ```
- Install pre-commit hooks:
  ```bash
  pip install pre-commit
  pre-commit install
  ```

## Code Style & Quality
- Run `pre-commit run --all-files` before pushing.
- Use Black, Flake8, and MyPy for formatting, linting, and type-checking.

## Testing
- Run tests locally with:
  ```bash
  pytest -vv tests --browser=chromium
  ```
- Add new tests for any new features or bug fixes.

## Secrets & Sensitive Data
- Never commit secrets or credentials. Use `.env` (not tracked) and `.env.example` for documentation.

## Pull Requests
- Ensure all checks pass (CI, lint, tests).
- Provide clear descriptions and reference related issues.

## Need Help?
- Check the README and docs/ for more info.
- Ask in the team chat or open an issue.
