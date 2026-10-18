# Issue workflow

How work moves from an issue to `main`. GitHub holds the plan and task state; the repo holds the
decisions. Everything runs through the `gh` CLI.

## Map

| Concept | Home |
|---|---|
| Phase | Milestone (`M1 Foundation` … `M4 Map, heatmap and ship`) |
| Task | Issue, with scope and acceptance criteria |
| Decisions for a task | `docs/decisions/<area>.md`, committed in the task's PR |
| Work in progress | One branch per issue, in its own worktree |
| Done | PR merged with `Fixes #<n>`, which closes the issue |

## The loop

1. **Start from the issue.** Its scope is the boundary of the branch. Anything outside it becomes a
   new issue or a `docs/BACKLOG.md` entry.
2. **Branch** from current `main`: `<type>/<n>-<slug>`, e.g. `feat/5-risk-bands`.
3. **Decision first.** If the issue has open choices, its first commit records them in
   `docs/decisions/`. Code follows the decision, never the other way round.
4. **Commit at every green step.** One concern per commit, with a conventional message, scope and
   issue: `feat(risk): classify rain bands (#5)`. Run `make check` before each commit.
5. **Open the PR** with `gh pr create`: what changed, why, which decisions it implements, how it was
   tested, and `Fixes #<n>`.
6. **CI passes and the diff is reviewed.** Review findings are fixed as new commits on the branch,
   not by rewriting history.
7. **Merge with a merge commit** (`gh pr merge --merge`). The branch's commits stay readable in
   `main`; the merge commit groups them under the PR.
8. **Clean up**: remove the worktree and delete the branch.

## Branch types

`feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `ci`, `perf`.

## Changing a decision

Edit the decision record in a PR, state what changed and why, and update the code and tests it
governs in the same PR. Never change behaviour a decision covers without touching the record.
