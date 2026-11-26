# Base on plain Debian and use Debian's own python3 so the image has exactly one
# libpython. python:3.11-slim ships /usr/local/lib/libpython3.11.so.1.0, which
# Debian's LibreOffice pyuno resolves instead of the system copy; the Python
# script provider then aborts (std::bad_alloc, exit 134) and the Referee never connects.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv \
    libreoffice-calc-nogui libreoffice-script-provider-python fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Venv without --system-site-packages; ensurepip inside it provides pip.
# The venv is deliberately NOT on PATH: soffice inherits PATH, and LibreOffice's
# embedded Python would then find /opt/venv/bin/python, adopt the venv's
# pyvenv.cfg, lose /usr/lib/python3/dist-packages (where `uno` lives) and crash
# the same way (std::bad_alloc, exit 134). Call venv binaries by absolute path.
RUN python3 -m venv /opt/venv

RUN useradd -m -u 10001 ghost
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY ghost ghost
COPY mcp_server mcp_server
COPY web web
COPY samples samples
# The router reads its thresholds from this one file (see .dockerignore: nothing else under .kiro is let in).
COPY .kiro/steering/routing-thresholds.md .kiro/steering/routing-thresholds.md

# Editable install keeps the /app layout that web/app.py uses to find samples,
# templates and static files.
RUN /opt/venv/bin/pip install --no-cache-dir -e .

# Bundled sample workbooks are generated at build time by the committed scripts.
RUN /opt/venv/bin/python samples/make_discount.py samples/discount.xlsx \
 && /opt/venv/bin/python samples/make_haunted.py samples/haunted.xlsx \
 && /opt/venv/bin/python samples/make_scenarios.py samples/scenarios.xlsx

RUN chown -R ghost:ghost /app
USER ghost

ENV GHOST_SOFFICE=/usr/bin/soffice \
    GHOST_MAX_JOBS=2 \
    PORT=8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD /opt/venv/bin/python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=8)"

CMD ["sh", "-c", "exec /opt/venv/bin/uvicorn web.app:app --host 0.0.0.0 --port ${PORT}"]
