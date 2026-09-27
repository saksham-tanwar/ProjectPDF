# One image for both Render services: the web service runs the default CMD,
# the worker overrides it with `python -m app.worker`.

FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    PORT=8000
WORKDIR /srv
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && adduser --system --group --no-create-home app \
    && mkdir -p /data/uploads \
    && chown app:app /data/uploads
ENV MODEL_CACHE_DIR=/srv/.models
RUN python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; \
    TextCrossEncoder(model_name='Xenova/ms-marco-MiniLM-L-6-v2', cache_dir='/srv/.models')" \
    && chown -R app:app /srv/.models
COPY app ./app
COPY --from=frontend /frontend/dist ./frontend/dist
USER app
EXPOSE 8000
CMD ["python", "-m", "app.main"]
