FROM python:3.11-slim-bullseye

RUN apt-get update && apt-get install -y \
    redis-server \
    git \
    redis-tools \
    && apt-get clean

WORKDIR /project

COPY requirements_for_docker.txt .
COPY tests/ tests/

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements_for_docker.txt

CMD ["bash"]
