FROM docker.io/library/python:3.12

COPY . /scoutbot


RUN pip install scoutbot/

WORKDIR /scoutbot

CMD ["python3", "-m", "Scout.scout"]
