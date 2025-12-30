# syntax=docker/dockerfile:1

########## BUILD STAGE ##########
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

# We'll treat /app as the project root inside the container
WORKDIR /app

# Copy dependency metadata from your repo
# (pyproject.toml lives at app/applications/pyproject.toml on host)
COPY applications/pyproject.toml ./pyproject.toml
COPY applications/uv.lock ./uv.lock
# If you have a uv.lock, keep this; otherwise delete/comment it
# COPY app/applications/uv.lock ./uv.lock

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install all dependencies (including uvicorn) into /app/.venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Now bring in the actual source code
# applications package (where backend.py lives)
COPY applications ./applications
# agents directory (no __init__.py needed)
COPY agents ./agents


########## RUNTIME STAGE ##########
FROM python:3.12-slim AS runtime

WORKDIR /app

# Ensure we use the venv's python + scripts (uvicorn, etc.)
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # let Python see /app so "import agents" works
    PYTHONPATH="/app"

# Copy the venv and source code from build stage
COPY --from=build /app /app

# Sanity: this should run backend.py exactly like:
#   uv run applications/backend.py
# but using the venv python directly
CMD ["python", "applications/backend.py"]
