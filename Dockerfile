FROM python:3.12-slim-bullseye

WORKDIR /env
RUN apt update -y && apt install gcc -y

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY / /env/orcha_ui

ENV PYTHONUNBUFFERED 1

EXPOSE 8050
CMD python -m orcha_ui.app
