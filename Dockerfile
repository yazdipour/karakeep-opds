FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

EXPOSE 8000

CMD ["uvicorn", "karakeep_opds.app:app", "--host", "0.0.0.0", "--port", "8000"]
