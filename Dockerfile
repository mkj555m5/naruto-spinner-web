FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ── Cloudflare WARP userspace tooling (amd64/arm64) ──
ARG WGCF_VERSION=2.3.0
ARG WIREPROXY_VERSION=1.1.3
RUN ARCH="$(dpkg --print-architecture)" \
 && curl -fsSL -o /usr/local/bin/wgcf "https://github.com/ViRb3/wgcf/releases/download/v${WGCF_VERSION}/wgcf_${WGCF_VERSION}_linux_${ARCH}" \
 && chmod +x /usr/local/bin/wgcf \
 && curl -fsSL -o /tmp/wireproxy.tar.gz "https://github.com/windtf/wireproxy/releases/download/v${WIREPROXY_VERSION}/wireproxy_linux_${ARCH}.tar.gz" \
 && tar -xzf /tmp/wireproxy.tar.gz -C /usr/local/bin wireproxy \
 && chmod +x /usr/local/bin/wireproxy \
 && rm -f /tmp/wireproxy.tar.gz \
 && wgcf -h > /dev/null \
 && wireproxy -v

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY docker ./docker
RUN chmod +x /app/docker/*.sh

EXPOSE 8080

ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
