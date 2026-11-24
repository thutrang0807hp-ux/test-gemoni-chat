FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --system --uid 10001 studio && mkdir /data && chown studio /data
COPY app.py studio_server.py ./
COPY templates ./templates
ENV STUDIO_DATABASE=/data/jobs.sqlite3
USER studio
VOLUME ["/data"]
EXPOSE 8080
CMD ["python", "studio_server.py"]
