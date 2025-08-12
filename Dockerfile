ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Install UV from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:0.8.9 /uv /bin/uv

WORKDIR /app

COPY ./uv.lock ./pyproject.toml ./

RUN uv sync --locked --no-install-project --no-dev

COPY ./prefect_managedfiletransfer ./prefect_managedfiletransfer/

ENV PATH="/app/.venv/bin:$PATH"

