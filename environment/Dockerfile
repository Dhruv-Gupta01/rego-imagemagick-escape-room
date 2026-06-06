FROM python:3.13-slim-bookworm@sha256:e4fa1f978c539608a10cdf74700ac32a3f719dfc6e8b6b6001da82deb36302a2

# ── System tools ──────────────────────────────────────────────────────────────
# imagemagick : generate + inspect glyph PNGs (convert / identify)
# tmux + asciinema : mandatory for Snorkel agent recording
# curl : download OPA binary below
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        imagemagick \
        tmux \
        asciinema \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── OPA (Open Policy Agent) ───────────────────────────────────────────────────
# Static linux/amd64 binary — no shared-lib deps, works on any x86_64 Debian.
# sha256 pinned so a tampered or re-uploaded release binary is caught at build.
RUN curl -fsSL -o /usr/local/bin/opa \
        https://github.com/open-policy-agent/opa/releases/download/v0.68.0/opa_linux_amd64_static \
    && echo "dfd5081fc6f930dfeaf2a225e31e616fc227dc0c7b43019b73d6f8fb8a1de1aa  /usr/local/bin/opa" \
       | sha256sum -c - \
    && chmod +x /usr/local/bin/opa

# ── Python packages (runtime only) ───────────────────────────────────────────
# Verifier-only deps (pytest, requests, ...) are NOT baked here — they install
# from vendored wheels inside tests/test.sh at verify time.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# ── App code ──────────────────────────────────────────────────────────────────
WORKDIR /app

COPY api/     /app/api/
COPY data/    /app/data/
COPY glyphs/  /app/glyphs/
COPY schemas/ /app/schemas/
COPY docs/    /app/docs/
COPY policy/  /app/policy/

# Generate the 4 glyph PNGs at build time (deterministic; fixed widths baked in)
RUN bash /app/glyphs/generate_glyphs.sh

EXPOSE 5000
CMD ["python", "/app/api/app.py"]
