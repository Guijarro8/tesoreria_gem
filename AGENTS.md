# Repository Workflow

- Treat `master` as the repository's default branch. Do not rename it to `main`.
- Never develop or commit directly on `master`. It is protected and only accepts
  changes through pull requests.
- Before starting work, fetch `origin/master` and create a new feature branch
  from it. Keep unrelated changes on separate branches.
- Run `uv run pre-commit run --all-files` before pushing a feature branch.
- Open a pull request targeting `master`; do not attempt to bypass its branch
  protection rules.
