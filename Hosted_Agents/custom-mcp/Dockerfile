FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data directory and contoso.db are included
RUN mkdir -p data && ls -la data/

EXPOSE 8000

CMD ["python", "mcp_service.py"]
