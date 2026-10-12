FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    CHROME_BIN=/usr/bin/chromium \
    OPENMONTAGE_PROJECTS_DIR=/data/projects \
    OPENMONTAGE_DELIVERY_DIR=/data/deliveries \
    OPENMONTAGE_JOB_QUEUE_DIR=/data/jobs \
    OPENMONTAGE_JOB_INPUT_DIR=/data/inbox \
    OPENMONTAGE_WORKER_ENABLED=1 \
    BACKLOT_HOST=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        ffmpeg \
        fonts-dejavu-core \
        fonts-liberation \
        libsndfile1 \
        openjdk-17-jre-headless \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

WORKDIR /app

COPY OpenMontage/requirements-educational-core.txt ./requirements-educational-core.txt
COPY OpenMontage/requirements-educational.txt ./requirements-educational.txt
COPY OpenMontage/.runtime/hyperframes/package.json ./.runtime/hyperframes/package.json
COPY OpenMontage/.runtime/hyperframes/package-lock.json ./.runtime/hyperframes/package-lock.json

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-educational.txt \
    && npm ci --prefix .runtime/hyperframes --omit=dev

COPY OpenMontage/ ./

RUN mkdir -p /data/projects /data/deliveries /data/jobs /data/inbox

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + (os.environ.get('PORT') or '8080') + '/api/health', timeout=3)"

CMD ["python", "-m", "deployment.railway_service"]
