FROM python:3.14-slim-trixie

WORKDIR /env/orcha_ui

RUN apt update -y && apt install -y gcc curl unzip && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY / /env/orcha_ui

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/env

EXPOSE 3000
EXPOSE 8000

CMD ["reflex", "run", "--backend-host", "0.0.0.0"]