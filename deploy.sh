#!/usr/bin/env bash
# Build the api and web images on this machine, ship them to the VM over SSH and roll the stack.
# The VM holds no source and never builds. Decisions: docs/decisions/deployment.md.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-$ROOT_DIR/.env.deploy}"
PROD_ENV_FILE="$ROOT_DIR/backend/.env.production"
HEALTH_TIMEOUT_S=60

die() { echo "deploy: $*" >&2; exit 1; }

[[ -f "$DEPLOY_ENV_FILE" ]] || die "missing $DEPLOY_ENV_FILE (copy .env.deploy.example)"
[[ -f "$PROD_ENV_FILE" ]] || die "missing $PROD_ENV_FILE (copy backend/.env.production.example)"
set -a; source "$DEPLOY_ENV_FILE"; set +a
: "${DEPLOY_REMOTE:?set in .env.deploy}" "${DEPLOY_TARGET_DIR:?set in .env.deploy}"
DEPLOY_PLATFORM="${DEPLOY_PLATFORM:-linux/arm64}"

# --- Only a clean commit that origin/main contains (deployment D4) ----------------------------
[[ -z "$(git -C "$ROOT_DIR" status --porcelain)" ]] || die "working tree is dirty; commit first"
git -C "$ROOT_DIR" fetch -q origin main
git -C "$ROOT_DIR" merge-base --is-ancestor HEAD origin/main \
  || die "HEAD is not on origin/main; merge the PR first"
TAG="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"

# --- Secret key on first deploy (deployment D7) -------------------------------------------------
if ! grep -Eq '^DJANGO_SECRET_KEY=.+' "$PROD_ENV_FILE"; then
  key="$(openssl rand -base64 48 | tr -d '\n/+=')"
  if grep -q '^DJANGO_SECRET_KEY=' "$PROD_ENV_FILE"; then
    sed -i '' "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$key|" "$PROD_ENV_FILE"
  else
    printf 'DJANGO_SECRET_KEY=%s\n' "$key" >>"$PROD_ENV_FILE"
  fi
  echo "deploy: generated DJANGO_SECRET_KEY in $PROD_ENV_FILE"
fi

# --- Build (deployment D1) ----------------------------------------------------------------------
echo "deploy: building spotter-api:$TAG and spotter-web:$TAG for $DEPLOY_PLATFORM"
docker buildx build --platform "$DEPLOY_PLATFORM" --build-arg "GIT_SHA=$TAG" \
  -t "spotter-api:$TAG" --load "$ROOT_DIR/backend"
docker buildx build --platform "$DEPLOY_PLATFORM" \
  -t "spotter-web:$TAG" --load "$ROOT_DIR/frontend"

# --- Ship: a tag is a commit, so an image already on the VM is the same image -------------------
for image in "spotter-api:$TAG" "spotter-web:$TAG"; do
  if ssh "$DEPLOY_REMOTE" "docker image inspect '$image' >/dev/null 2>&1"; then
    echo "deploy: $image already on the VM"
  else
    echo "deploy: shipping $image"
    docker save "$image" | gzip | ssh "$DEPLOY_REMOTE" "gunzip | docker load"
  fi
done

ssh "$DEPLOY_REMOTE" "mkdir -p '$DEPLOY_TARGET_DIR'"
scp -q "$ROOT_DIR/docker-compose.prod.yml" "$DEPLOY_REMOTE:$DEPLOY_TARGET_DIR/docker-compose.yml"
scp -q "$PROD_ENV_FILE" "$DEPLOY_REMOTE:$DEPLOY_TARGET_DIR/api.env"

# --- Roll and wait for the new SHA (deployment D5) ----------------------------------------------
ssh "$DEPLOY_REMOTE" TAG="$TAG" DIR="$DEPLOY_TARGET_DIR" TIMEOUT="$HEALTH_TIMEOUT_S" bash <<'REMOTE'
set -euo pipefail
cd "$DIR"
printf 'IMAGE_TAG=%s\n' "$TAG" >.env
chmod 600 api.env
docker compose up -d --remove-orphans
for _ in $(seq "$TIMEOUT"); do
  if curl -fsS http://localhost:8150/api/health 2>/dev/null | grep -q "\"version\":\"$TAG\""; then
    echo "deploy: $TAG is live"
    exit 0
  fi
  sleep 1
done
echo "deploy: $TAG did not report healthy within ${TIMEOUT}s" >&2
docker compose ps >&2
docker compose logs --tail 50 api web >&2
exit 1
REMOTE

# Old images pile up on a shared disk; keep the running tag and the one before it for rollback.
ssh "$DEPLOY_REMOTE" bash <<'PRUNE'
for repo in spotter-api spotter-web; do
  docker image ls "$repo" --format '{{.CreatedAt}}\t{{.Repository}}:{{.Tag}}' \
    | sort -r | tail -n +3 | cut -f2 | xargs -r docker image rm >/dev/null || true
done
PRUNE
echo "deploy: done, https://spotter.akhilsingh.in runs $TAG"
