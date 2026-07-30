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

- **Version**: published git tags `vX.Y.Z` on **origin** (matches
  `.github/workflows/build-and-push.yml` and `build-windows.yml`
  `tags: ['v*']`). There is **no** project version in `pyproject.toml`.
  Do **not** invent prefixes like `cyxcbot-v*`. Local `refs/tags/v*` is
  not authoritative when it disagrees with origin.
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

- Refresh remote branch tips + tags first (shallow / `--no-tags` / stale
  checkouts otherwise omit or lag tags):
  ```bash
  git fetch origin --tags --prune
  ```
  Do **not** pass `--prune-tags` (clobbers changed local tags). Only use
  destructive tag sync if the maintainer explicitly asks. If the clone is
  shallow and history around the last release is missing, deepen or
  unshallow before relying on `git log` ranges.
- Last **published** stable release name — from origin only, filter to
  `vX.Y.Z` (reject `v2.4.0-rc1`, `vtest`, etc.; workflows accept any `v*`
  but this skill only cuts stable SemVer):
  ```bash
  LAST_TAG=$(git ls-remote --tags --refs origin 'refs/tags/v*' \
    | awk '{print $2}' | sed 's|refs/tags/||' \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
  echo "$LAST_TAG"
  ```
  If empty, stop — do not invent a version from deploy defaults alone.
- Resolve that published tag via a **remote-only** ref (do not trust
  `refs/tags/$LAST_TAG` for ranges — a same-named local tag may point
  elsewhere, and non-destructive fetch will not overwrite it):
  ```bash
  git fetch origin "+refs/tags/${LAST_TAG}:refs/release-check/${LAST_TAG}"
  if LOCAL_OID=$(git rev-parse -q --verify "refs/tags/${LAST_TAG}"); then
    REMOTE_OID=$(git rev-parse "refs/release-check/${LAST_TAG}")
    if [ "$LOCAL_OID" != "$REMOTE_OID" ]; then
      echo "local refs/tags/${LAST_TAG} != origin; stop and reconcile" >&2
      exit 1
    fi
  fi
  ```
  If a newer local-only `v*` exists, warn before proposing the next
  version (do not treat it as published).
- Current deploy default (should equal last published release **before**
  the bump in step 3):
  ```bash
  awk -F: '/image:.*cyxcbot:/{print $NF; exit}' deploy/compose/docker-compose.yml
  ```
- Choose `<release-tip>` (branch tip or commit from step 2; default
  `HEAD` only if that is what you will ship). Review:
  ```bash
  git log --no-merges "refs/release-check/${LAST_TAG}"..<release-tip>
  git log --oneline "refs/release-check/${LAST_TAG}"..<release-tip> -- shared/db/migrations/
  ```
- Semver: fixes/reliability/dependency bumps only → **patch**; new
  user-facing feature → **minor**; breaking change or upgrade needing
  manual user action beyond normal Alembic auto-upgrade → **major**.
  Prefer staying on the current 2.x line unless intentionally cutting 3.0.

### 2. Confirm branch and CI readiness

- Prefer cutting from **`main`** after the intended commits are merged
  (historical tags point at `main`; `develop` is the integration branch).
- If `develop` is ahead of `main`, confirm with the user whether to merge
  first or tag a specific commit. Record `<release-branch>` and
  `<release-base>` (full SHA of the pre-bump tip you intend to ship).
  The SHA that step 7 tags is **only** the step-6 deploy-bump commit —
  never tag `<release-base>` itself.
- Lint/format/test CI jobs run only on **pull_request** (see
  `build-and-push.yml`); push to `main`/`develop` builds images but does
  not re-run that gate. Confirm the last merged PR checks were green
  and/or rely on step 4 local verify.
- Spot-check deploy paths still match expectations (`deploy/README.md`,
  `deploy/compose/`, `deploy/helm/`).

### 3. Bump deploy defaults

Work on a **named branch** whose tip is `<release-base>` before editing.
Do **not** use `git switch --detach` — a detached bump has no branch tip
to push, so step 7 cannot publish it.

```bash
# Preferred: release from the branch tip (usually main)
git switch <release-branch>
test "$(git rev-parse HEAD)" = "$(git rev-parse <release-base>)"
```

If `<release-base>` is not the current tip of `<release-branch>`, stop
and confirm with the maintainer. Options:

1. Merge/rebase so the intended code is the branch tip, then re-record
   `<release-base>`, or
2. Create a publishable branch at that base (then use it as
   `<release-branch>` for the rest of the flow):
   ```bash
   git switch -c release/vX.Y.Z <release-base>
   ```

Never edit ambient `HEAD` that differs from `<release-base>`.

Edit only:

1. `deploy/compose/docker-compose.yml` → `ghcr.io/cyxc1124/cyxcbot:vX.Y.Z`
2. `deploy/helm/values.yaml` → `tag: "vX.Y.Z"`
3. `deploy/helm/Chart.yaml` → `appVersion: "X.Y.Z"`
4. `deploy/helm/README.md` → example `tag: "vX.Y.Z"`

No lockfile refresh. No `web/package.json` sync.

### 4. Verify locally (same bar as PR CI)

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

Summarize from the `refs/release-check/${LAST_TAG}..<release-tip>` log —
prefer product impact over commit titles. Call out Python/runtime, env,
or deploy behavior changes explicitly.

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

Do **not** include unrelated dirty files. After commit, set
`<release-commit>` to that new SHA and verify ancestry + branch tip:

```bash
test "$(git rev-parse <release-commit>^)" = "$(git rev-parse <release-base>)"
test "$(git rev-parse <release-branch>)" = "$(git rev-parse <release-commit>)"
```

Step 7 **must not** run until this bump commit exists and
`<release-commit>` points at it.

### 7. Tag (only when asked)

**Preflight** — stop if any fail:

1. Step 6 bump is committed (working tree clean for the four deploy
   files; they show `vX.Y.Z` / `appVersion: "X.Y.Z"` at
   `<release-commit>`).
2. `<release-commit>` is the bump commit SHA from step 6 — not
   `<release-base>`.
3. Parent of `<release-commit>` equals `<release-base>`:
   ```bash
   test "$(git rev-parse <release-commit>^)" = "$(git rev-parse <release-base>)"
   ```
4. Tag the **explicit** `<release-commit>` — never assume ambient `HEAD`:

```bash
git rev-parse --verify <release-commit>
git show <release-commit>:deploy/compose/docker-compose.yml \
  | grep -F "cyxcbot:vX.Y.Z"
git tag -a vX.Y.Z <release-commit> -m "$(cat <<'EOF'
vX.Y.Z

相对 vPREV 的主要变化：

- ...

升级说明：...
EOF
)"
```

**Push** — `<release-commit>` must be the tip of `<release-branch>`
(guaranteed if step 3 stayed on a named branch). Push branch + tag
atomically so a rejected branch update never leaves a published tag:

```bash
test "$(git rev-parse <release-branch>)" = "$(git rev-parse <release-commit>)"
git push --atomic origin <release-branch> vX.Y.Z
```

Do **not** hard-code `main`. Do **not** push the tag alone after a
failed branch push. Do **not** leave the bump on a detached HEAD.

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
