# Headless FLIMAnalyzer: batch mode (flimbatch), no wxPython.
#
#   docker build -t flimanalyzer .
#   docker run --rm -v "$PWD:/work" flimanalyzer \
#       -i data/ -o results/ -c settings.json --run Summarize
#
# Build arguments:
#   TORCH_INDEX  replaces PyTorch from the lock file (the CUDA build on x86_64, several
#                GB) by the build of this index, e.g. https://download.pytorch.org/whl/cpu
#   EXTRAS       optional extras, e.g. "dask" for Dask executors and workers

# --- build: the locked environment, with FLIMAnalyzer (version from the git tags) ---
FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.18
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /src
COPY . .
ARG EXTRAS=""
RUN uv sync --frozen --no-dev --no-editable \
    $(for e in $EXTRAS; do printf -- "--extra %s " "$e"; done)
ARG TORCH_INDEX=""
RUN if [ -n "$TORCH_INDEX" ]; then \
        version=$(/opt/venv/bin/python -c "from importlib.metadata import version; print(version('torch').split('+')[0])") \
        && cuda=$(uv pip list --python /opt/venv --format freeze | grep -E '^(nvidia-|cuda-|triton)' | cut -d= -f1) \
        && uv pip uninstall --python /opt/venv torch $cuda \
        && uv pip install --python /opt/venv --index-url "$TORCH_INDEX" "torch==$version"; \
    fi

# --- runtime ---
FROM python:3.12-slim
COPY --from=build /opt/venv /opt/venv
# no display: matplotlib draws off-screen; no Prefect usage statistics
ENV PATH=/opt/venv/bin:$PATH \
    MPLBACKEND=Agg \
    PREFECT_SERVER_ANALYTICS_ENABLED=false \
    PREFECT_HOME=/tmp/prefect
RUN useradd --create-home flim
USER flim
WORKDIR /work
ENTRYPOINT ["flimbatch"]
CMD ["--help"]
