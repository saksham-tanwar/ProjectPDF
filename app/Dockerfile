FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*
RUN pip install -r requirements.txt
COPY app/ /app/app/
CMD ["python", "-m", "app.main"]