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
[[ "$DEPLOY_TARGET_DIR" == /* ]] || die "DEPLOY_TARGET_DIR must be absolute; ~ is not expanded"
DEPLOY_PLATFORM="${DEPLOY_PLATFORM:-linux/arm64}"

# --- Only a clean commit that origin/main contains (deployment D4) ----------------------------
[[ -z "$(git -C "$ROOT_DIR" status --porcelain)" ]] || die "working tree is dirty; commit first"
git -C "$ROOT_DIR" fetch -q origin main
git -C "$ROOT_DIR" merge-base --is-ancestor HEAD origin/main \
  || die "HEAD is not on origin/main; merge the PR first"
# A fixed length, so the tag, the live /api/health version and `make prod-check` always agree.
TAG="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)"

# --- Secret key on first deploy (deployment D7) -------------------------------------------------
chmod 600 "$PROD_ENV_FILE"
if ! grep -Eq '^DJANGO_SECRET_KEY=[^"'"'"'[:space:]]+' "$PROD_ENV_FILE"; then
  key="$(openssl rand -base64 48 | tr -d '\n/+=')"
  if grep -q '^DJANGO_SECRET_KEY=' "$PROD_ENV_FILE"; then
    sed -i '' "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$key|" "$PROD_ENV_FILE"
  else
    [[ -z "$(tail -c1 "$PROD_ENV_FILE")" ]] || echo >>"$PROD_ENV_FILE"
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
# Created owner-only from the start: the VM is shared and the file holds the keys.
ssh "$DEPLOY_REMOTE" "umask 077 && cat > '$DEPLOY_TARGET_DIR/api.env'" <"$PROD_ENV_FILE"

# --- Roll and wait for the new SHA (deployment D5) ----------------------------------------------
ssh "$DEPLOY_REMOTE" TAG="$TAG" DIR="$DEPLOY_TARGET_DIR" TIMEOUT="$HEALTH_TIMEOUT_S" bash <<'REMOTE'
set -euo pipefail
cd "$DIR"
diagnose() {
  docker compose ps >&2
  docker compose logs --tail 50 api web >&2
}
if ! IMAGE_TAG="$TAG" docker compose up -d --remove-orphans; then
  echo "deploy: docker compose up failed for $TAG" >&2
  diagnose
  exit 1
fi
# Plain `docker compose` commands on the VM use the tag that is now running.
printf 'IMAGE_TAG=%s\n' "$TAG" >.env
deadline=$((SECONDS + TIMEOUT))
while ((SECONDS < deadline)); do
  if curl -fsS -m 3 http://localhost:8150/api/health 2>/dev/null | grep -q "\"version\":\"$TAG\""; then
    echo "deploy: $TAG is live"
    # Deploy order, newest last. Rollback and pruning read it (image build dates can tie).
    { grep -vx "$TAG" deploys.log 2>/dev/null || true; echo "$TAG"; } >deploys.log.new
    mv deploys.log.new deploys.log
    exit 0
  fi
  sleep 1
done
echo "deploy: $TAG did not report healthy within ${TIMEOUT}s" >&2
diagnose
exit 1
REMOTE

# Old images pile up on a shared disk; keep the running tag and the one deployed before it.
ssh "$DEPLOY_REMOTE" DIR="$DEPLOY_TARGET_DIR" bash <<'PRUNE'
keep="$(tail -n 2 "$DIR/deploys.log")"
for repo in spotter-api spotter-web; do
  docker image ls "$repo" --format '{{.Tag}}' | grep -vxF "$keep" \
    | sed "s|^|$repo:|" | xargs -r docker image rm >/dev/null || true
done
PRUNE
echo "deploy: done, https://spotter.akhilsingh.in runs $TAG"
