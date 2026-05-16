FROM python:3.11

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# Node.js is kept because the original project can still run the frontend and
# backend together through `npm run dev`. Enhanced backend services override
# CMD from docker-compose.yml.
RUN apt-get update \
  && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy uv from the official image so Python dependencies are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first to improve Docker build caching.
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY backend/pyproject.toml backend/uv.lock ./backend/

RUN npm ci \
  && npm ci --prefix frontend \
  && cd backend && uv sync --frozen

COPY . .

EXPOSE 3000 5001

# Default remains the original local full-stack development command.
# docker-compose.yml overrides this for backend-app, celery-worker, and scheduler.
CMD ["npm", "run", "dev"]
