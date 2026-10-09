# 01 — Repo scaffold

> Load `00-conventions.md` first. Depends on: nothing. Day 1, ~2 hours.

## Goal

A monorepo where every later prompt has a place to land, CI runs on push, and every `make` target in `docs/architecture/components/10-scheduler-and-infra.md` §5 exists — as a stub that says what it will do, if the thing isn't built yet.

## Read first

- `docs/architecture/README.md`
- `docs/architecture/components/10-scheduler-and-infra.md` §5 (Makefile targets), §4 (secrets)
- `prompts/00-conventions.md` (layout, stack)

## Deliverables

```
pyproject.toml                 uv workspace; members packages/* services/*; ruff, mypy, pytest config
.python-version                3.12
Makefile                       every target from 10 §5; unbuilt ones print "not built yet — see prompts/NN"
.github/workflows/ci.yml       uv sync; ruff; mypy (packages only); pytest; gitleaks; privacy grep
.gitleaks.toml
.gitignore                     .env, .env.*, !.env.example, *.tfstate*, .terraform/, artifacts/** except *.md/.gitkeep, deploy/compose/logs/
.pre-commit-config.yaml        ruff, ruff-format, gitleaks
packages/{tower-policy,tower-consent,tower-audit,camara-client}/
    pyproject.toml, src/<pkg>/__init__.py, tests/test_smoke.py, README.md (one paragraph: role, doc link)
services/{mock-carrier,tower-mcp,binding-page,alerts,ref-client}/
    pyproject.toml, src/<svc>/__init__.py, tests/test_smoke.py, README.md, Dockerfile (builds, runs `python -c 'import <svc>'`), .env.example
deploy/compose/docker-compose.yml   services declared, images build, nothing wired yet
deploy/terraform/README.md          "see prompts/13"
deploy/helm/README.md               "see prompts/14"
specs/camara/README.md              "vendored in prompts/04"
scenarios/.gitkeep
artifacts/.gitkeep                  (artifacts/* ignored except .gitkeep and *.md committed by prompt 16)
tests/privacy/test_no_numbers.py    scans `artifacts/`, captured logs dir, and any `*.json` under services/*/tests/golden for E.164 patterns and health words — passes trivially now
README.md                           title, one-paragraph description, link to docs/architecture, "status: scaffold"
```

## Steps

1. `uv init` the workspace; add members; confirm `uv sync` resolves with no network beyond PyPI.
2. Write the Makefile with these exact targets: `up seed demo test policy-table corpus showcase-alexa showcase-tower showcase-binding showcase-gateway showcase-alerts showcase-audit showcase-mock showcase-ref showcase-infra showcase deploy down`. `test` runs `uv run pytest` across the workspace plus `tests/privacy`. `showcase` runs the showcase targets in the order of `testing-and-showcase.md` §4.
3. CI: matrix of one (ubuntu, 3.12). Steps: checkout, uv, `make test`, `docker build` every service, gitleaks.
4. Each service Dockerfile: multi-stage, `uv export` → `pip install` into a slim runtime stage, non-root user `app`, `HEALTHCHECK` placeholder.
5. Pre-commit hooks installed and documented in the root README.

## Acceptance

- Fresh clone → `uv sync && make test` passes in under 60 s.
- `docker compose -f deploy/compose/docker-compose.yml build` succeeds for all five services.
- CI green on the first push; `gitleaks detect` clean; `.env` ignored (a test commits a dummy `.env` in a temp clone and asserts git doesn't see it).
- `make showcase-tower` (and every other unbuilt target) prints a one-line pointer to its prompt and exits 0.

## Guardrails

- No application code yet. No carrier payloads, no table schemas — those come with their prompts and their tests.
- Don't add a `common/` or `utils/` package. Shared code goes into the four named packages only.

## Report back

Tree output of the repo, CI run link, and anything in the conventions that didn't fit the tooling (e.g. uv workspace quirks) — with the fix you applied.
