# Contributing

How we work on NatureCheckpoint. Technical decisions and interface contracts are in [docs/architecture.md](docs/architecture.md).

## Workflow

1. **Pick an issue** from the [board](https://github.com/users/julianzangl/projects/2). Assign it to yourself and move it to *In progress*.
2. **Create a branch** from `main`: `feature/<issue>-<short-slug>`, e.g. `feature/10-backend-skeleton`. For bugs use `fix/<issue>-<slug>`.
3. **Commit** from your own GitHub account, in small steps.
4. **Open a pull request.** Fill in the template and reference the issue with `Closes #<issue>`.
5. **Get one approval from a teammate**, wait for green CI, then **squash merge**.

Review rotation:

| Author | Reviewer |
|---|---|
| Florian | Julian |
| Julian | Hischam |
| Hischam | Florian |

`main` is protected: no direct pushes and no force pushes.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/).

Format: `type(scope): short description in imperative, lower case`

| Type | Use for |
|---|---|
| `feat` | New functionality |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or changing tests |
| `refactor` | Code change without behaviour change |
| `build` | Dependencies, Dockerfiles, packaging |
| `ci` | GitHub Actions |
| `chore` | Other maintenance (config, repo structure) |

**Scope** is optional: `sensor-node`, `backend`, `ingest`, `web`, `deploy`, `docs`.

Examples:

- `feat(backend): add health endpoint`
- `fix(sensor-node): retry failed DHT reads`

Commits that complete an issue can add `Closes #<issue>` in the body. Usually the PR does that.

Aim for **1 to 3 commits per issue**, e.g. feature, tests, and docs or deployment. Not one giant commit, but no micro-commits either.

**Pair work:** if you work together on one computer, credit your teammate in the commit message:

```text
Co-authored-by: Name <email>
```

## Local setup

```bash
uv venv -p 3.13 .venv          # or: python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt -r backend/requirements.txt -r sensor-node/requirements.txt
```

Before every push:

```bash
ruff check . && ruff format --check . && pytest
```

Run the backend locally:

```bash
cd backend && uvicorn app.main:app --reload
```

Then open http://localhost:8000/docs.

## Rules

- **Secrets:** never commit `.env`, tokens, passwords or database files. The repository is public.
- **Contracts:** if you change a contract (MQTT payload, InfluxDB schema, REST response), update `docs/architecture.md` in the same PR. The owners of the affected components review it.
- **Docs:** update the matching wiki page in `wiki/` when behaviour changes.
