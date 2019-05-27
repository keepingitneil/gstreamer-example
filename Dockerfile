FROM keepingitneil/gstreamer-1.14.1

RUN apt install -y python3-pip && \
    apt-get update && \
    pip3 install aiohttp aiodns aioredis && \
    apt install -y graphviz gdb

WORKDIR /usr/local/stood_rtc

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

ENV CONTROLLER ingest
ENV GST_DEBUG=1
ENV GST_DEBUG_DUMP_DOT_DIR=/tmp/dot_files

COPY sidecar-ingest.yaml sidecar.yaml

CMD ["sh", "-c", "python3 -u ./stood_rtc.py"]
