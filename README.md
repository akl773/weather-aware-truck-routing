# Weather-Aware Truck Routing

Choose the lowest-risk truck route. The app takes an origin, destination, departure time and load weight,
gets three route options, reads the forecast at the truck's ETA every 10, 25 or 50 miles, classifies
risk with load-aware rules, and recommends a route. A 0–48 hour heatmap shows the weather across the
trip corridor.

> Work in progress. Live link and walkthrough arrive with the deploy (#15, #16).

## Run locally

Requires Docker, [uv](https://docs.astral.sh/uv/) and Node 24.

```bash
cp backend/.env.example backend/.env   # optional for now
make dev                               # http://localhost:5173
make sanity                            # every gate CI runs
```

## Documentation

- [Spec](docs/SPEC.md): the brief and its gaps
- [Context](docs/CONTEXT.md): domain vocabulary
- [Decisions](docs/decisions/README.md): every design choice, with the alternatives rejected
- [Workflow](docs/ISSUE_WORKFLOW.md): how issues become merged PRs
- [Backlog](docs/BACKLOG.md): what was deliberately left out
- [AGENTS.md](AGENTS.md): working rules for humans and coding agents
