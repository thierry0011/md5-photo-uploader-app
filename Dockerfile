# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------

FROM builder AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
RUN flake8 .
RUN DJANGO_TESTING=true DJANGO_SECRET_KEY=ci pytest -v
RUN touch /tests-passed

# ---------------------------------------------------------------------------

FROM python:3.13-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/false --create-home app

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

# Forces the test stage to pass first - a failed flake8/pytest run fails this COPY, and the whole build
COPY --from=test /tests-passed /tmp/tests-passed
RUN find . -name "tests.py" -delete

# collectstatic needs no live DB/AWS credentials, just settings that import cleanly.
RUN DJANGO_SECRET_KEY=build-time-only python manage.py collectstatic --noinput

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
