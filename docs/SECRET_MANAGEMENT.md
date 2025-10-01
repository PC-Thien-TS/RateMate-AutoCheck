# Secret Management in RateMate-AutoCheck

- **Never commit secrets or credentials to the repository.**
- Use `.env` for local secrets (not tracked by git).
- Use `.env.example` to document required variables for contributors.
- For CI/CD, set secrets in the platform (GitHub Actions: Settings > Secrets).
- Audit the repo for accidental secrets with:
  ```bash
  pre-commit run detect-secrets --all-files
  ```
- If a secret is leaked, rotate it immediately and remove from git history.

## Recommended Pre-commit Hook
Add to `.pre-commit-config.yaml`:
```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.4.0
  hooks:
    - id: detect-secrets
```
