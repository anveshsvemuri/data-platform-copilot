FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge
RUN pip install --no-cache-dir .
ENTRYPOINT ["data-copilot-mcp"]

