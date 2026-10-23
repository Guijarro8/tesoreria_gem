# Repository Workflow

- Treat `master` as the repository's default branch. Do not rename it to `main`.
- Never develop or commit directly on `master`. It is protected and only accepts
  changes through pull requests.
- Before starting work, fetch `origin/master` and create a new feature branch
  from it. Keep unrelated changes on separate branches.
- Run `uv run pre-commit run --all-files` before pushing a feature branch.
- Do not create pull requests or merge them. The repository owner creates and
  merges PRs manually; do not attempt to bypass `master` protection rules.
- Never commit, log, or expose real member names, transfer descriptions, bank
  exports, service-account credentials, or private lookup data. Keep those files
  under `private/`, which is ignored, and use synthetic names in tests.
