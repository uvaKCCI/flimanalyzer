# Headless FLIMAnalyzer: batch mode (flimbatch), no wxPython.
#
#   docker build -t flimanalyzer .
#   docker run --rm -v "$PWD:/work" flimanalyzer \
#       -i data/ -o results/ -c settings.json --run Summarize
#
# Build arguments:
#   TORCH_INDEX  replaces PyTorch from the lock file (the CUDA 12.8 build on x86_64,
#                several GB) by the same version from this index: another CUDA version,
#                e.g. https://download.pytorch.org/whl/cu126, or the CPU-only build,
#                https://download.pytorch.org/whl/cpu
#   EXTRAS       optional extras: "dask" for Dask executors and workers. Not "gui": the
#                image does not support a display, and wxPython has no Linux wheels on PyPI

# --- build: the locked environment, with FLIMAnalyzer (version from the git tags) ---
# base image pinned by digest (updated by Dependabot); the same in both stages
FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS build

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
RUN for e in $EXTRAS; do \
        if [ "$e" = gui ]; then \
            echo "EXTRAS=gui is not supported: this image is headless (batch mode)." >&2; \
            exit 1; \
        fi; \
    done \
    && uv sync --frozen --no-group gui --no-group docs --no-editable \
    $(for e in $EXTRAS; do printf -- "--extra %s " "$e"; done)

ARG TORCH_INDEX=""
RUN if [ -n "$TORCH_INDEX" ]; then \
        version=$(/opt/venv/bin/python -c "from importlib.metadata import version; print(version('torch').split('+')[0])") \
        && cuda=$(uv pip list --python /opt/venv --format freeze | grep -E '^(nvidia-|cuda-|triton)' | cut -d= -f1) \
        && uv pip uninstall --python /opt/venv torch $cuda \
        && uv pip install --python /opt/venv --index-url "$TORCH_INDEX" "torch==$version"; \
    fi

# --- runtime ---
FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30

COPY --from=build /opt/venv /opt/venv
# no display support: matplotlib draws off-screen; no Prefect usage statistics
ENV PATH=/opt/venv/bin:$PATH \
    MPLBACKEND=Agg \
    PREFECT_SERVER_ANALYTICS_ENABLED=false \
    PREFECT_HOME=/tmp/prefect

RUN useradd --create-home flim

USER flim
WORKDIR /work
ENTRYPOINT ["flimbatch"]
CMD ["--help"]

# OCI metadata: fixed here; per build from CI (docker.yml), empty in local builds
LABEL org.opencontainers.image.title="FLIMAnalyzer" \
      org.opencontainers.image.description="FLIMAnalyzer in batch mode (flimbatch) without the GUI: analysis of Fluorescence Lifetime Imaging Microscopy (FLIM) data." \
      org.opencontainers.image.authors="Karsten Siller <khsiller@gmail.com>" \
      org.opencontainers.image.vendor="The University of Virginia" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/uvaKCCI/flimanalyzer" \
      org.opencontainers.image.documentation="https://flimanalyzer.readthedocs.io" \
      org.opencontainers.image.source="https://github.com/uvaKCCI/flimanalyzer"
ARG VERSION="" REVISION="" CREATED="" BASE_NAME="" BASE_DIGEST=""
LABEL org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.created=$CREATED \
      org.opencontainers.image.base.name=$BASE_NAME \
      org.opencontainers.image.base.digest=$BASE_DIGEST
