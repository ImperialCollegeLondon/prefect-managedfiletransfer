ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

# Enable bytecode compilation
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_SYSTEM_PYTHON=1

# Install system requirements - see https://github.com/PrefectHQ/prefect/blob/main/Dockerfile
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    tini=0.19.* \
    build-essential \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install UV from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:0.8.9 /uv /bin/uv

WORKDIR /app

COPY ./uv.lock ./pyproject.toml ./

RUN uv sync --locked --no-install-project --no-dev

COPY ./prefect_managedfiletransfer ./prefect_managedfiletransfer/

RUN uv sync --compile-bytecode --locked --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

# Smoke test
RUN prefect version

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "./prefect_managedfiletransfer/entrypoint.sh"]

CMD [ "bash", "./prefect_managedfiletransfer/run_as_standalone_server.sh" ]

