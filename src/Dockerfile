FROM python:3.7-alpine

RUN apk --no-cache add build-base linux-headers
WORKDIR /app
ADD requirements.txt /app
RUN pip install --trusted-host pypi.python.org -r requirements.txt

ADD . /app
