# ⚙️ PhoenixAuto-Ops — Continuous Integration

This document describes the automated CI implementation that validates every
change to PhoenixAuto-Ops before it reaches `main`. It covers what the two
workflows actually do, why they're structured the way they are, and what is
intentionally *not* part of this stage yet.

This is not a general GitHub Actions tutorial — it documents this project's
actual `.github/workflows/` files.

---

## CI Overview

PhoenixAuto-Ops reached a point where Phase 1 (core monitoring/alerting/
healing) and Phase 2 (Docker) were both complete and manually verified —
see [docs/development-workflow.md](development-workflow.md). Manual
verification doesn't scale: every new alert channel, healing action, or
Dockerfile change up to now has relied on the person making the change
remembering to run lint, tests, and a manual Docker build/run cycle
themselves.

CI formalizes that as an automated, mandatory gate. It's introduced now —
before Phase 4 (AWS) — because deploying automation to production without
first automating validation of that automation would just move the same
manual-discipline problem downstream. This stage builds directly on the
`tests/` suite (`conftest.py` fixtures, unit tests for `ConfigLoader`,
`SystemMetrics`, `NetworkMetrics`, all three alert senders, and
`HealingActions`, plus integration-style tests for `MonitoringEngine`)
that was written and verified locally before CI existed — CI automates
running that suite, it didn't create the need for it.

---

## CI Architecture

Two workflows, split by what they actually validate:

| Workflow | Validates | Runs on |
|---|---|---|
| `ci.yml` | Application Python code — lint, tests, dependency & static security | Every PR/push to `main` |
| `docker-ci.yml` | The Docker image — build, runtime behavior, image vulnerabilities | Only when Docker-relevant files change |

They're separated rather than combined into one workflow because they
validate genuinely different things at genuinely different costs: `ci.yml`
finishes in roughly a minute and should run on every change; `docker-ci.yml`
builds a real image and starts a real container, which is both slower and
irrelevant to a documentation-only or comment-only change. Forcing every PR
through a full Docker build regardless of what changed would just be wasted
runner time.

---

## Application CI (`ci.yml`)

### Triggers

- `pull_request` targeting `main` — every change must pass before merge.
- `push` to `main` — re-validates the actual state of `main` itself (an
  admin merge or hotfix bypasses the PR path but not this trigger).
- `workflow_dispatch` — lets a re-run be triggered manually (e.g. after
  bumping a pinned action version) without an empty commit.

There is no `develop` or staging branch in this project's Git workflow (see
[docs/development-workflow.md](development-workflow.md)), so `main` is the
only branch these triggers target.

### Permissions

Workflow-level: `contents: read` only. The `security` job additionally
requests `security-events: write`, scoped to that job alone, because it's
the only one that uploads SARIF results to the repository's Security tab.
`lint` and `test` never get more than read access.

### Python setup

Pinned to **Python 3.11**, matching the `python:3.11-slim` base image used
in both stages of the project's `Dockerfile`. Testing against a different
interpreter version than the one actually shipped in the container would
validate the wrong runtime.

### Dependencies & caching

Installed straight from the existing `requirements.txt` — no second
dependency-management system introduced. `actions/setup-python`'s built-in
`cache: pip` (keyed off `requirements.txt`) avoids re-downloading the same
wheels (`psutil`, `pyyaml`, `requests`, `pytest`, `pytest-cov`, etc.) on
every run.

### Tests

Runs the project's real `pytest`/`pytest-cov` suite via `pytest -v`.
Coverage behavior (`--cov=app`, `--cov-report=term-missing`,
`--cov-report=xml`) is configured once in the project's own `pytest.ini`
rather than repeated on the CI command line — this keeps `pytest.ini` as
the single source of truth for how coverage runs, whether invoked from CI
or locally by `bash scripts/run_monitor.sh`-adjacent manual testing.
Test failures are blocking; this job has no conditional pass-through for
a failing test.

The `tests/conftest.py` `patch_config` fixture means the suite runs
without touching the filesystem or network — `psutil` calls are fully
mocked in `SystemMetrics`/`NetworkMetrics` tests, and alert-sender tests
mock the HTTP/SMTP layer — so no CI-specific environment setup (`.env`,
network access, elevated permissions) is required for the suite to pass.

The generated `coverage.xml` is uploaded as a workflow artifact
(`coverage-xml`, 14-day retention) so coverage is inspectable per-run
without requiring an external service — see Deferred Improvements for the
planned Codecov integration this already prepares for.

### Code quality

`flake8` (linting) and `black --check` (formatting), both scoped to `app/`.
Both tools are pinned (`flake8==7.1.1`, `black==24.8.0`) and installed
directly in the workflow rather than added to `requirements.txt`, since
they're CI-only tooling, not a runtime dependency of the monitoring engine.
`--extend-ignore=E203,W503` on flake8 is the standard black/flake8
compatibility pair, not a general loosening of the ruleset.

isort and mypy were deliberately **not** added — the codebase's import
style is already consistent, and adding a third overlapping quality tool
without a concrete problem it solves would just be YAML for its own sake.

### Security

Two checks, each catching a different class of problem:

- **`bandit`** (static analysis of `app/`) — `--severity-level medium
  --confidence-level medium`. Low-severity/low-confidence findings are
  excluded by design: they're dominated by things like the `subprocess`
  usage in `app/healing/actions.py`, which is a deliberate, reviewed
  pattern (list-form arguments, `shell=False`, hardcoded script paths —
  see the Security Model table in [docs/architecture.md](architecture.md)),
  not an actual finding worth gating merges on.
- **`pip-audit`** (dependency CVE scan against `requirements.txt`) — any
  hit is treated as actionable and blocking. Unlike bandit's
  confidence/severity axes, a known CVE against a pinned package doesn't
  have a meaningful "informational-only" bucket — it either needs a
  version bump or a consciously documented exception.

Bandit results are also uploaded as SARIF to the repository's Security tab
via `github/codeql-action/upload-sarif`. That upload step uses
`continue-on-error: true` deliberately — a failed upload usually means
GitHub Advanced Security isn't enabled for the repo's current visibility/
plan, which is an environment limitation, not a security regression in the
code. The bandit *scan* step itself has no such exception and fails the job
normally on a real finding.

### Concurrency

`cancel-in-progress: true`, grouped by workflow + ref. A new push to an
open PR makes the previous run's result stale, so it's cancelled instead of
burning runner minutes validating a diff nobody will look at.

### Failure behavior

No `continue-on-error` is used to hide a meaningful failure anywhere in
this workflow. The one exception (SARIF upload) is explained above and is
about visibility, not correctness.

### Required check aggregation

`lint`, `test`, and `security` run in parallel — there's no real dependency
between them. A final `ci-status` job with `needs: [lint, test, security]`
exists purely so branch protection can require a single named check
instead of three, and so a partial run (one job cancelled, another failed)
is reported clearly instead of ambiguously.

---

## Docker CI (`docker-ci.yml`)

### Scope and triggers

Triggered only when files that actually affect the built image change:
`Dockerfile`, `.dockerignore`, `docker-compose.yml`, `app/**`, `config/**`,
`scripts/**`, `requirements.txt`, or the workflow file itself. A change to
`README.md` or `docs/architecture.md` doesn't rebuild anything here.

### Dockerfile linting

`hadolint` runs against the existing `Dockerfile` with
`failure-threshold: error` — style/info/warning-level findings are still
printed for visibility but don't block the build; only genuine correctness
problems do. This threshold was chosen deliberately over the stricter
default so the check reflects real risk rather than every stylistic
opinion hadolint has.

### Build

Uses Docker Buildx (`docker/setup-buildx-action`) with GitHub Actions cache
backend (`cache-from`/`cache-to: type=gha`). `load: true` (not `push`)
loads the image straight into the runner's local daemon so it can be run
and inspected immediately — nothing is published anywhere from this step.
The existing multi-stage `Dockerfile` is used as-is; no second Dockerfile
was introduced. Build args (`VERSION`, `VCS_REF`, `BUILD_DATE`) are passed
through the same way [docs/docker.md](docker.md) documents for a manual
local build, so CI-built images carry the same real provenance labels.

### Runtime validation

This is the part that actually exercises the application, not just the
image metadata:

1. **Non-root check** — `docker image inspect` confirms `Config.User` is
   `phoenixops`, verifying the non-root design from
   `feat/docker-security` actually landed in the built image.
2. **Container start** — run the image the same way `docker-compose.yml`
   does (module entrypoint), without the host `/proc`/`/` mounts (see
   "Docker Compose Evaluation" below for why).
3. **Healthcheck polling** — polls `docker inspect
   --format='{{.State.Health.Status}}'` until `healthy`, with a bounded
   timeout, failing (with logs) on `unhealthy` or timeout. This exercises
   the actual `HEALTHCHECK` from `feat/docker-healthcheck` — a log-
   freshness check, not an import-only smoke test.
4. **Startup log assertions** — greps container logs for the real log
   lines emitted by `app/main.py` and `app/engine.py`
   (`"PhoenixAuto-Ops starting"`, `"Monitoring engine initialized"`,
   `"Entering continuous monitoring mode"`).
5. **Graceful shutdown** — `docker stop --time 40` (matching
   `docker-compose.yml`'s `stop_grace_period: 40s`) sends SIGTERM, then
   asserts the logs contain `"Received shutdown signal"` and `"Monitoring
   engine stopped"`. This is the single check in this workflow that would
   have caught the original silent-SIGKILL bug described in
   [docs/docker.md](docker.md#graceful-shutdown) — it validates the exact
   fix delivered in `feat/docker-runtime`, not a generic assumption.

No `.env` file is present in CI. This is intentional, not an oversight:
`ConfigLoader._load_environment()` already handles a missing `.env`
gracefully (falls back to system environment variables and logs a notice),
and `BaseAlertSender` subclasses log a warning and skip sending rather than
crashing when credentials are absent — this is real, existing application
behavior, not something invented for CI.

### Docker Compose evaluation

`docker-compose.yml` is **not** used for CI validation. Its host-monitoring
mounts (`/proc:/host/proc`, `/:/rootfs`) exist to let the container observe
a *real host's* vitals — see [docs/docker.md](docker.md#host-system-monitoring).
A GitHub Actions runner isn't the kind of host this project is meant to
monitor, and mounting a shared CI runner's root filesystem read-only into a
container for a validation step that doesn't need it is unnecessary
exposure surface. Plain `docker run` already validates everything Compose
would for CI purposes (image, entrypoint, healthcheck, shutdown).

### Image vulnerability scanning (Trivy)

Two Trivy scans, not one, to distinguish actionable from informational
findings:

- **Full report (`HIGH,CRITICAL`, `exit-code: 0`)** — non-blocking,
  uploaded as SARIF to the Security tab. HIGH-severity findings in a
  `python:3.11-slim` base image without an upstream fix yet are common and
  worth seeing, but shouldn't stop every merge.
- **CRITICAL gate (`exit-code: 1`)** — blocking. This matches the severity
  policy already recorded in this project's own roadmap
  ([docs/development-workflow.md](development-workflow.md)).

Both scans use `ignore-unfixed: true` — a CVE with no available fix yet
isn't something the project can act on today, so it isn't held against the
build.

### Build caching

Both jobs share a GitHub Actions cache scope (`phoenixops-image`). The
`image-security-scan` job's "rebuild" is a cache hit against layers the
`build-and-validate` job already populated — effectively free, and avoids
transferring the built image between jobs as a workflow artifact.

### Image tagging

Images are tagged `phoenixauto-ops:ci-<commit-sha>` — immutable per run,
never `latest`, so two concurrent runs on different branches can't collide
in the same runner's local image cache.

### Container Registry decision

**No image is published to GHCR (or any registry) from this workflow.**
This CI stage's job is to prove the image builds correctly, starts
correctly, and passes a security gate — not to produce a deployable
artifact. Registry publishing is a deployment concern, sits outside this
task's scope, and is explicitly listed under Deferred Improvements below.
This also sidesteps a real security question this project doesn't need to
answer yet: a pull request from an external fork must never be able to
push an image using this repository's credentials, and not publishing
anything from this workflow removes that risk entirely rather than
requiring careful trigger/permission separation to manage it.

---

## Security

- **Least privilege** — both workflows default to `contents: read` at the
  top level; any broader permission (`security-events: write`) is added
  only on the specific job that needs it.
- **Action version control** — GitHub-owned actions (`actions/checkout`,
  `actions/setup-python`, `actions/upload-artifact`, `github/codeql-action/*`)
  are pinned to a major version tag, which is a reasonable trust boundary
  since GitHub follows semver on these and controls the publishing
  pipeline directly. Third-party actions (`docker/*`,
  `hadolint/hadolint-action`, `aquasecurity/trivy-action`) are pinned to
  explicit version tags rather than `@master`/`@latest`. Full commit-SHA
  pinning was intentionally left out for now — it's a real further-
  hardening step but adds noticeable noise to the YAML for a solo project
  at this maturity stage; it's listed under Deferred Improvements.
- **Secrets** — neither workflow declares or references any repository
  secret. Nothing is printed, and `.env` is never present in the CI
  environment (it's git-ignored and not checked out).
- **Pull request security** — because no publishing step exists in either
  workflow, a pull request from a fork can never combine untrusted code
  with write access to a registry or repository secret. Both workflows
  read at most `contents` and, for two specific jobs, write to
  `security-events` (the repo's own Security tab) — nothing that could be
  abused to exfiltrate anything.
- **Dependency security** — `pip-audit` against `requirements.txt` in
  `ci.yml`; Trivy against the built filesystem/OS layers in
  `docker-ci.yml`. These check different layers (Python packages vs. the
  full image including the base OS) rather than duplicating each other.

### Accepted findings

`pip-audit`'s CRITICAL-by-default policy has one explicit, documented
exception: **PYSEC-2026-1845** (pytest, predictable `/tmp/pytest-of-{user}`
directory naming) is ignored via `--ignore-vuln`. This is a test-only
dependency, the exploit requires local multi-user access to a shared `/tmp`
- not a condition GitHub Actions' ephemeral, single-tenant runners meet -
and the fix requires a pytest major-version bump (8.x → 9.x) that needs its
own compatibility verification against `pytest-cov==4.0.0` and
`pytest-mock==3.10.0` before it's safe to land. This is revisited under
Deferred Improvements, not silently ignored forever.

---

## Git Workflow Integration

Both workflows plug into the existing feature-branch process documented in
[docs/development-workflow.md](development-workflow.md) without changing
it:

1. A feature branch (e.g. `feat/ci-lint-test`) is opened as usual.
2. Its pull request into `main` triggers `ci.yml` always, and
   `docker-ci.yml` only if the diff touches a Docker-relevant path.
3. All required jobs (`ci-status`, and `build-and-validate` /
   `image-security-scan` when triggered) must pass before merge.
4. After merge, the same workflows re-run against `main` itself via the
   `push` trigger.

No new branch names, merge strategy, or commit convention is introduced —
CI observes and gates the existing process rather than replacing it.

---

## Current Scope

**Implemented:**
- Python lint, format check, real test execution against the project's
  existing `pytest`/`pytest-cov` suite (`ConfigLoader`, `SystemMetrics`,
  `NetworkMetrics`, all three alert senders, `HealingActions`, and
  `MonitoringEngine` integration tests), coverage report artifact upload,
  static security analysis, dependency vulnerability scanning
- Docker image build, non-root verification, healthcheck validation,
  startup/shutdown log verification, Dockerfile linting, image
  vulnerability scanning with a CRITICAL severity gate

**Explicitly not implemented at this stage:**
- Container registry publishing (GHCR or otherwise)
- Any deployment workflow or infrastructure (AWS, Terraform, Kubernetes)
- Matrix builds across multiple Python versions or OSes
- `docker-compose.yml`-based CI validation
- Codecov or any external coverage-reporting service (the `coverage.xml`
  artifact this workflow already produces is what that integration would
  consume)
- Commit-SHA pinning of third-party GitHub Actions

---

## Deferred Improvements

Genuinely useful next steps, intentionally kept outside this CI stage's
scope rather than added just to make the pipeline look more complete:

- Bump `pytest` to 9.x (resolves PYSEC-2026-1845) after verifying
  compatibility with `pytest-cov` and `pytest-mock`, and separating
  test-only dependencies (`pytest`, `pytest-cov`, `pytest-mock`) into a
  `requirements-dev.txt` so they stop shipping inside the production
  Docker image
- Container registry publishing (GHCR) once a deployment stage exists
- Commit-SHA pinning of third-party GitHub Actions
- Dependabot/Renovate for automated dependency and action version bumps
- A dynamic CI status badge in `README.md`