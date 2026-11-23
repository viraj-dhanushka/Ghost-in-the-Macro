FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc-nogui libreoffice-script-provider-python fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 ghost
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY ghost ghost
COPY mcp_server mcp_server
COPY web web
COPY samples samples

# Editable install keeps the /app layout that web/app.py uses to find samples,
# templates and static files.
RUN pip install --no-cache-dir -e .

# Bundled sample workbooks are generated at build time by the committed scripts.
RUN python samples/make_discount.py samples/discount.xlsx \
 && python samples/make_haunted.py samples/haunted.xlsx \
 && python samples/make_scenarios.py samples/scenarios.xlsx

RUN chown -R ghost:ghost /app
USER ghost

ENV GHOST_SOFFICE=/usr/bin/soffice \
    GHOST_MAX_JOBS=2 \
    PORT=8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=8)"

CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${PORT}"]
