FROM python:3-alpine3.13
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt
EXPOSE 5000
CMD flask --app main run --host 0.0.0.0