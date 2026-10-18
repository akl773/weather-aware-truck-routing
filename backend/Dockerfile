# Dependencies resolve from uv.lock with --frozen, so the image runs exactly the locked versions
# (stack D4). The runtime stage has no uv, no build tools and no tests.
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .

# Local development: dev dependencies and the auto-reloading server. Source is bind-mounted.
FROM build AS dev
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM python:3.14-slim AS runtime
ARG GIT_SHA=dev
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 GIT_SHA=$GIT_SHA
USER app
EXPOSE 8000
# A plan waits on routing and weather providers; the timeout sits just under nginx's 65 s.
# No control socket: nothing here uses gunicornc, and the app user cannot write one in its home.
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", \
     "--access-logfile", "-", "--no-control-socket"]
