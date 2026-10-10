# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.lock pyproject.toml ./
COPY src ./src
# Optional combined CA bundle for managed proxy environments; never copied into image layers.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.lock && pip install --no-deps .
COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests
RUN chmod -R a+rX /app && useradd --create-home --uid 10001 ballx
USER ballx
EXPOSE 8000
CMD ["uvicorn", "ballx.main:app", "--host", "0.0.0.0", "--port", "8000"]
