FROM keepingitneil/gstreamer-1.14.1

RUN apt install -y python3-pip && \
    pip3 install aiohttp aiodns aioredis && \
    apt install -y graphviz gdb

WORKDIR /usr/local/inbound

COPY . .

ENV GST_DEBUG=1
ENV GST_DEBUG_DUMP_DOT_DIR=/tmp/dot_files

CMD ["python3", "-u", "./main.py"]
