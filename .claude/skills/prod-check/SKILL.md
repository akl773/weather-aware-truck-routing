---
name: prod-check
description: Check that https://spotter.akhilsingh.in is up, serving the expected commit, and healthy on the VM; read its container logs. Use when asked whether production is up, what is deployed, or why the live site misbehaves.
---

# Production check

## Is it up, and which commit?

```sh
make prod-check                                   # live SHA vs origin/main, non-zero if they differ
curl -s https://spotter.akhilsingh.in/api/health  # {"status":"ok","version":"<sha>"}
```

The app footer shows the same SHA.

## On the VM

The stack lives in `~/spotter` on the `oci` host as compose project `spotter` (web, api, redis).

```sh
ssh oci 'cd ~/spotter && docker compose ps'
ssh oci 'cd ~/spotter && docker compose logs --tail 100 api'
ssh oci 'curl -s localhost:8150/api/health'       # bypasses Cloudflare
```

## Reading symptoms

| Symptom | Likely cause |
|---|---|
| Cloudflare 502/1033 | stack down, or the tunnel route no longer points at `localhost:8150` |
| nginx 502 on `/api/` | api container restarting; read its logs |
| `DisallowedHost` in api logs | hostname missing from `DJANGO_ALLOWED_HOSTS` in `backend/.env.production` |
| Plans fail, health is fine | a provider key is missing or exhausted; the api logs name the provider |

Read-only by default. Restarting or redeploying is the `deploy` skill, and only when asked.
