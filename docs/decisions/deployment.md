# Deployment

Status: decided by Akhil, 2026-10-18. Issue: #15.

## North Star
One command takes a commit that is on `origin/main` to the live site at
`https://spotter.akhilsingh.in`, and the live site says which commit it is running. The host is a
shared Oracle Cloud VM (aarch64) that already runs other apps, so this stack must not expose ports,
hold source code or take memory it cannot give back. Out of scope: autoscaling, zero-downtime
rollouts, multi-host.

## Decisions

### D1. Images are built on the laptop for linux/arm64 and shipped over SSH
`deploy.sh` builds the api and web images, pipes them through `docker save | gzip | ssh docker
load`, copies the compose file and env, and runs `docker compose up -d`. The VM holds no source tree
and never builds.
Rejected: a container registry, because it adds credentials on the VM and a third party in the
path for a single host. Rejected: building on the VM, because it puts source and build tools on a
shared box and is slower on its CPU.
Enforced by: `deploy.sh`.

### D2. nginx is the only published service, on 127.0.0.1:8150
nginx serves the built frontend and proxies `/api/` to the api container, so the browser sees one
origin and there is no CORS. The api and redis containers publish nothing. Publishing on loopback
keeps the port off the internet, because Docker's iptables rules bypass the host firewall for
`0.0.0.0` bindings.
Rejected: a separate API hostname, because it needs CORS and a second tunnel route for no gain.
Enforced by: `docker-compose.prod.yml`, `frontend/nginx.conf`.

### D3. TLS and DNS come from the VM's existing Cloudflare tunnel
`spotter.akhilsingh.in` is a public hostname on the VM's `oracle` tunnel, pointing at
`http://localhost:8150`. The VM opens no inbound port.
Rejected: opening 443 with a certificate on the VM, because the other apps on this host already
use the tunnel and a second ingress path is one more thing to secure.
Enforced by: the tunnel's public hostname list in the Cloudflare dashboard.

### D4. Only a clean commit that is on `origin/main` can be deployed
`deploy.sh` refuses a dirty tree and a HEAD that `origin/main` does not contain. The image tag and
the `GIT_SHA` baked into the api are that commit's short SHA, so every deploy maps to one reviewed,
CI-checked commit.
Rejected: deploying the working tree, because the live site could then run code no one can find.
Enforced by: `deploy.sh` guards.

### D5. A deploy succeeds only when the live API reports the new SHA
After `up -d`, `deploy.sh` polls `/api/health` through nginx on the VM until it returns the
deployed SHA, and fails after 60 s otherwise. A green health check from the old container does not
count.
Rejected: checking only that the containers are running, because a crash-looping api still shows
as running between restarts.
Enforced by: `deploy.sh` health gate, `make prod-check`.

### D6. Redis is a bounded cache with no persistence
`maxmemory 128mb` with `allkeys-lru`, no RDB or AOF. Everything in it is a provider response that
can be fetched again, so losing it on restart costs only latency.
Rejected: persistence, because it writes to the shared disk for data that is cheap to refetch.
Enforced by: `docker-compose.prod.yml` redis command.

### D7. Production secrets live in a gitignored env file on the laptop
`backend/.env.production` holds `DJANGO_SECRET_KEY` and provider keys. `deploy.sh` generates the
secret key on the first deploy if it is missing and copies the file to the VM as `api.env`.
Rejected: secrets in the compose file or in CI, because there is no CI deploy and the compose file
is committed.
Enforced by: `.gitignore` (`.env.*`), `deploy.sh`.
