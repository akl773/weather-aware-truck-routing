# Decisions

One file per area: `<area>.md`. Each holds the area's North Star and its decisions with their
reasoning. They live in the repo so they version with the code, show up in diffs, and every agent
reads them without extra tooling.

A recorded decision is settled. Later work builds on it instead of re-deciding it. To change one,
open a PR that edits the decision, says why, and updates the code and tests it governs.

## Index

| File | Area | Issue |
|---|---|---|
| `stack.md` | Frameworks, libraries and test strategy | #2, #3 |
| `risk-classification.md` | Bands, load rules, checkpoint level | #5 |
| `recommendation.md` | Owned miles, route summary, ranking | #6 |
| `routing.md` | Routing provider, third-route fallback | #7 |
| `checkpoints-and-eta.md` | Sampling, ETA, forecast interpolation | #8 |
| `weather.md` | Weather provider, units, cache | #9 |
| `plan-api.md` | Plan request, response, unknown levels, errors | #10 |
| `corridor-heatmap.md` | Corridor grid, frames, rendering, slider | #11, #14 |
| `deployment.md` | Images, host, tunnel, deploy gate | #15 |

Files are added by the issue that needs them.

## Template

```markdown
# <Area>

Status: decided by Akhil, <YYYY-MM-DD>. Issue: #<n>.

## North Star
What this area must achieve and why. What is out of scope.

## Decisions

### D1. <the decision, stated as a rule>
Why, in a few sentences. The spec line or measurement it rests on.
Rejected: <alternative>, because <reason>.
Enforced by: `<function or module>`, `<test name>`.

## Open questions
Anything deliberately deferred, and what would settle it.
```

## Conventions

- A decision is a rule someone can check against the code: "0.25 in/hr is High", not "handle edges
  carefully".
- Every decision names at least one rejected alternative. A decision without one was not a choice.
- `Enforced by` points at the code and tests that hold the rule, and code that implements a decision
  cites it in a comment (`# risk-classification D2`).
- Measurements carry their numbers and conditions: "118 KB gzipped for a 1,150-mile trip", not "small".
