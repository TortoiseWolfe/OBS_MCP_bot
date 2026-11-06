FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      obs-studio xvfb xauth libgl1-mesa-dri libglx-mesa0 mesa-vulkan-drivers fonts-dejavu-core dbus-x11 ca-certificates \
      python3 python3-venv python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
RUN useradd -m obs && mkdir -p /app/content/failover && \
    for n in a b c; do ffmpeg -loglevel error -f lavfi -i testsrc=size=640x360:rate=30 -f lavfi -i sine=frequency=440 -t 6 -pix_fmt yuv420p /app/content/test_$n.mp4; done && \
    cp /app/content/test_a.mp4 /app/content/failover/default_failover.mp4 && chown -R obs:obs /app
USER obs
COPY --chown=obs:obs ci/obs-test/run.sh /home/obs/run.sh
ENTRYPOINT ["/bin/bash","/home/obs/run.sh"]
