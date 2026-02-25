FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pipenv
WORKDIR /app
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system
COPY . .
RUN chmod +x start.sh
EXPOSE 5050
CMD ["./start.sh"]
