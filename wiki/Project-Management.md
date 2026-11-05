# Project Management

We work in **Scrum** sprints up to the MVP and manage the project entirely on GitHub.

## Board

[Nature Checkpoint Kanban](https://github.com/users/julianzangl/projects/2)

| Field | Values |
|---|---|
| Status | Backlog → Ready (sprint backlog) → In progress → Done |
| Priority | **P0** MVP-critical, **P1** important for the grade, **P2** optional |
| Size | XS, S, M, L |
| Milestone | Sprint 1, Sprint 2, Sprint 3 |
| Labels | `sensor-node`, `backend`, `web`, `documentation` |

Every item is an issue with:

- a **user story**
- a short **description**
- a **Definition of Done**

Each issue is assigned to one team member.

## Sprints

| Sprint | Dates | Goal / checkpoint |
|---|---|---|
| Sprint 1 | 3 Nov → 17 Nov 2026 | Sprint Review 1: repo and board set up, prioritised backlog, architecture defined, sensors and actuators tested on the Pi |
| Sprint 2 | 17 Nov → 3 Dec 2026 | Sprint Review 2: at least one complete flow from sensor to storage/visualisation, shown live |
| Sprint 3 | 3 Dec → 11 Dec 2026 | MVP delivered, release tagged `v1.0` |
| Demo | Week of 14 Dec 2026 | 15-minute live demonstration |

## Git workflow

- `main` is protected. Changes go in through pull requests only.
- **Branch names:** `<type>/<issue>-<short-name>`, e.g. `feature/4-temp-humidity-sensor`.
- **Reviews:** every pull request is reviewed by a teammate before merging.
- **Issue references:** commits and pull requests reference their issue, e.g. `Closes #4`.
- **Own accounts:** everyone commits from their own GitHub account.
- **Pair work:** when you work together on one computer, credit your partner with a `Co-authored-by:` line.
- **No secrets:** never commit `.env`, passwords or tokens.

## Definition of Done (general)

An item is done when:

1. All points of the issue's Definition of Done are checked.
2. The code is reviewed via a pull request and merged into `main`.
3. The documentation (README and wiki) is updated.
4. It works on the real hardware, if hardware is involved.

## Team

| Name | GitHub |
|---|---|
| Hischam Chahil | [@MA-Hischam](https://github.com/MA-Hischam) |
| Florian Sylkaj | [@fsylkaj](https://github.com/fsylkaj) |
| Julian Zangl | [@julianzangl](https://github.com/julianzangl) |
