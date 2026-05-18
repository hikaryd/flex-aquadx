FROM python:3.12-slim AS builder
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
RUN pip install --no-cache-dir uv==0.5.*
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache .

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd -g 10001 app && useradd -u 10001 -g app -s /usr/sbin/nologin app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src ./src
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=2).status==200 else 1)"
CMD ["uvicorn", "aquadx.main:app", "--host", "0.0.0.0", "--port", "8000"]
