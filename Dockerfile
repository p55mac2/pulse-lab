# registry.access.redhat.com is pull-anonymous (registry.redhat.io requires auth)
FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /opt/app-root/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY schema.sql .
COPY src/ ./src/

# UBI python images already run as the non-root default user (1001)
EXPOSE 8080
CMD ["gunicorn", "--chdir", "src", "--bind", "0.0.0.0:8080", "--workers", "2", "main:app"]
