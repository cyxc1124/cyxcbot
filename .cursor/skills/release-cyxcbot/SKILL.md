---
name: release-cyxcbot
description: >-
  Prepare a new cyxcbot release end to end — pick the next semver version,
  sync deploy default image tags (Compose/Helm), verify local CI checks, draft
  annotated-tag release notes, and emit the vX.Y.Z tag/push commands. Use when
  asked to cut, prepare, plan, or draft a new cyxcbot release or version bump.
---

# Release cyxcbot

Prepares a cyxcbot application release: deploy-default bump + verification +
annotated tag notes, ready for the maintainer to tag. This is a
**version-and-verify** task — it does **not** publish. Tagging/pushing is the
maintainer's call; never tag or push unless explicitly asked.

## Source of truth

- **Version**: git tags `vX.Y.Z` (matches `.github/workflows/build-and-push.yml`
  and `build-windows.yml` `tags: ['v*']`). There is **no** project version in
  `pyproject.toml`. Do **not** invent prefixes like `cyxcbot-v*`.
- **Deploy cosmetic sync** (must match the release being tagged):
  - `deploy/compose/docker-compose.yml` → `image: ...:vX.Y.Z`
  - `deploy/helm/values.yaml` → `image.tag: "vX.Y.Z"`
  - `deploy/helm/Chart.yaml` → `appVersion: "X.Y.Z"` (**no** leading `v`)
  - `deploy/helm/README.md` → example `tag: "vX.Y.Z"`
- **Artifacts** (CI on tag push):
  - Docker: `ghcr.io/cyxc1124/cyxcbot:vX.Y.Z` (+ branch/sha labels on non-tag)
  - Windows: `cyxcbot-windows-vX.Y.Z.zip` attached to GitHub Release
  - GitHub Release: `softprops/action-gh-release` with
    `generate_release_notes: true` (auto notes); annotated tag body is the
    hand-written summary.
- **Not version sources** — do **not** bump as part of a routine release:
  - `web/package.json` `"version"` (stays `0.0.0`)
  - `deploy/helm/Chart.yaml` `version` (Helm chart packaging version; only
    bump when the Chart templates/values schema themselves change)
  - `admin/app.py` FastAPI `version=` (API schema metadata, unrelated)

## Steps

### 1. Pick the next version

- Last release: `git tag --list 'v*' --sort=-v:refname | head -1`
- Current deploy default (should equal last release):
  ```bash
  awk -F: '/image:.*cyxcbot:/{print $NF; exit}' deploy/compose/docker-compose.yml
  ```
- Review changes since last tag: `git log --no-merges <last-tag>..HEAD`
- Also list schema-touching migrations since last tag:
  ```bash
  git log --oneline <last-tag>..HEAD -- shared/db/migrations/
  ```
- Semver: fixes/reliability/dependency bumps only → **patch**; new
  user-facing feature → **minor**; breaking change or upgrade needing
  manual user action beyond normal Alembic auto-upgrade → **major**.
  Prefer staying on the current 2.x line unless intentionally cutting 3.0.

### 2. Confirm branch and CI readiness

- Prefer cutting from **`main`** after the intended commits are merged
  (historical tags point at `main`; `develop` is the integration branch).
- If `develop` is ahead of `main`, confirm with the user whether to merge
  first or tag a specific commit.
- Confirm recent CI is green on the tip you will bump from (PR checks:
  Python ruff/pytest + Web lint/test/build).
- Spot-check deploy paths still match expectations (`deploy/README.md`,
  `deploy/compose/`, `deploy/helm/`).

### 3. Bump deploy defaults

Edit only:

1. `deploy/compose/docker-compose.yml` → `ghcr.io/cyxc1124/cyxcbot:vX.Y.Z`
2. `deploy/helm/values.yaml` → `tag: "vX.Y.Z"`
3. `deploy/helm/Chart.yaml` → `appVersion: "X.Y.Z"`
4. `deploy/helm/README.md` → example `tag: "vX.Y.Z"`

No lockfile refresh. No `web/package.json` sync.

### 4. Verify locally (same bar as CI)

Use repo `.venv` and Python 3.14 (see `AGENTS.md`):

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
WEB_SECRET_KEY=ci-test-secret-key-not-for-production-use ./.venv/bin/pytest -v
npm --prefix web ci
npm --prefix web run lint
npm --prefix web run test
npm --prefix web run build
```

Optional docs smoke (not required for app release CI):

```bash
npm --prefix docs ci
npm --prefix docs run build
```

### 5. Draft annotated tag notes

Prepare the tag message body (Chinese, match recent tags). Template:

```text
vX.Y.Z

相对 vPREV 的主要变化：

- <user-facing highlight>
- ...

升级说明：<无 schema 变更可写「无数据库 schema 变更，从 vPREV 直接换镜像/包即可」；
有 migration 则点名影响与是否依赖启动时 Alembic upgrade>
```

Summarize from `git log` — prefer product impact over commit titles. Call out
Python/runtime, env, or deploy behavior changes explicitly.

### 6. Commit (only when asked)

Stage only the bump files:

- `deploy/compose/docker-compose.yml`
- `deploy/helm/Chart.yaml`
- `deploy/helm/values.yaml`
- `deploy/helm/README.md`

Suggested message:

```text
chore(deploy): 将默认镜像版本更新为 vX.Y.Z

同步 Docker Compose、Helm values 与 Chart appVersion，与最新 release 对齐。
```

Do **not** include unrelated dirty files.

### 7. Tag (only when asked)

Tag the **release commit** (the deploy-bump commit on the branch you intend
to ship, typically `main`):

```bash
git tag -a vX.Y.Z -m "$(cat <<'EOF'
vX.Y.Z

相对 vPREV 的主要变化：

- ...

升级说明：...
EOF
)"
git push origin main
git push origin vX.Y.Z
```

Pushing `vX.Y.Z` triggers:

1. Docker build/push to GHCR (`build-and-push.yml`)
2. Windows zip + GitHub Release with auto notes (`build-windows.yml`)

Emit these commands for the maintainer; do not run tag/push unless
explicitly requested.

## Files touched

| File | Action |
| --- | --- |
| `deploy/compose/docker-compose.yml` | bump image tag `vX.Y.Z` |
| `deploy/helm/values.yaml` | bump `image.tag` `vX.Y.Z` |
| `deploy/helm/Chart.yaml` | bump `appVersion` `X.Y.Z` |
| `deploy/helm/README.md` | sync example tag |

Do **not** touch: `web/package.json`, Helm `Chart.yaml` `version`, workflow
YAMLs, `Dockerfile` (they already read git tag / build-args).

## Out of scope

- Creating CHANGELOG / `docs/release-notes/` trees (not present; add only if
  the user asks).
- Publishing to PyPI.
- Force-pushing tags or rewriting release history.
- Merging Dependabot majors as part of a routine release without explicit
  review.
- Bumping Helm chart `version` unless chart packaging itself changed.
