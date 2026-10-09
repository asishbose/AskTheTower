# syntax=docker/dockerfile:1.7
FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f AS build
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY services/ref-client ./services/ref-client
# Only the client's own dependencies: no Tower, no policy, no consent, no carrier client in this image.
RUN uv export --frozen --no-dev --no-emit-workspace --package ref-client -o requirements.txt && \
    python -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /venv/bin/pip install --no-cache-dir --no-deps ./services/ref-client

FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
RUN useradd -r -u 10001 -m app && mkdir /out && chown app /out
COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH PYTHONUNBUFFERED=1 REF_ARTIFACTS_DIR=/out
USER app
WORKDIR /home/app
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import ref_client" || exit 1
ENTRYPOINT ["ref-client"]
CMD ["demo"]
