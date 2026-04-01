FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[memory]"

COPY sebastian/ ./sebastian/
COPY knowledge/ ./knowledge/

CMD ["python", "-m", "sebastian.main"]
