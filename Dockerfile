# FROM registry.hub.docker.com/library/python:3.11.3-slim
FROM docker.io/library/python:3.11.3-alpine

COPY requirements.txt /tmp

RUN pip install -r /tmp/requirements.txt

COPY . /nerris

RUN pip install /nerris

CMD ["python3", "-m", "Nerris.nerris"]
