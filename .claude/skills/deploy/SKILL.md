---
name: deploy
description: Ship the current origin/main commit to https://spotter.akhilsingh.in with deploy.sh, and roll back if it fails. Use when asked to deploy, ship, release or roll back production. Deploying is a privileged action; run it only when the user asks.
---

# Deploy

Decisions: `docs/decisions/deployment.md` (D1–D7). Read it before changing `deploy.sh`,
`docker-compose.prod.yml` or `frontend/nginx.conf`.

## Before

1. The change is merged: `git switch main && git pull`. `deploy.sh` refuses a dirty tree and a
   HEAD that `origin/main` does not contain (D4).
2. `.env.deploy` exists (copy `.env.deploy.example`). `backend/.env.production` exists with the
   provider keys (copy `backend/.env.production.example`); the secret key is generated if empty.
3. Docker is running locally. The images are built here, never on the VM (D1).

## Run

```sh
make deploy        # build, ship, up -d, wait until /api/health reports the new SHA
make prod-check    # the live SHA equals origin/main
```

A deploy prints `deploy: <sha> is live` only when the new api answers through nginx (D5). On
failure it prints `docker compose ps` and the last 50 log lines of api and web.

## Roll back

The previous image pair stays on the VM. Point the stack at it:

```sh
ssh oci 'cd ~/spotter && docker image ls spotter-api'          # find the previous tag
ssh oci 'cd ~/spotter && echo IMAGE_TAG=<tag> > .env && docker compose up -d'
```

Then fix forward on `main` and deploy again.

## Traps

- The VM is shared. Never `docker system prune` there, never publish a port on `0.0.0.0` (D2),
  never touch other compose projects.
- The public hostname is a route on the VM's `oracle` Cloudflare tunnel, managed in the Cloudflare
  dashboard. The route points at `http://localhost:8150`; change the port in both places or neither.
- `api.env` on the VM is a copy. Edit `backend/.env.production` locally and redeploy.
