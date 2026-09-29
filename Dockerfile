FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 copilot
USER 10001
EXPOSE 8000
ENTRYPOINT ["data-copilot-mcp"]
