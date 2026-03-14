FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY contextgraph/ contextgraph/
COPY sdk/ sdk/
RUN pip install --no-cache-dir ".[server]"

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/contextgraph-server /usr/local/bin/
COPY --from=builder /app .
EXPOSE 8420
ENV CG_HOST=0.0.0.0
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8420/health')"
CMD ["contextgraph-server"]
