FROM python:3.10-slim

RUN apt-get update && apt-get install -y curl build-essential && \
    rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=1.5.1
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    chmod +x /root/.local/bin/poetry
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --no-interaction --no-ansi

COPY . .

EXPOSE 3000
EXPOSE 5000

CMD ["poetry", "run", "python", "main.py"]
