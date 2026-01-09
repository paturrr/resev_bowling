FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py /app/
COPY templates /app/templates

ENV BACKEND_URL=http://backend-service:5000
EXPOSE 5000
CMD ["python", "app.py"]
