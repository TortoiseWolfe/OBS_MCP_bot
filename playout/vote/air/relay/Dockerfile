FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends nginx libnginx-mod-rtmp && rm -rf /var/lib/apt/lists/*
USER root
CMD ["nginx", "-g", "daemon off;", "-c", "/etc/nginx/relay/nginx.conf"]
