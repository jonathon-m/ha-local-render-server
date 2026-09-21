FROM ghcr.io/home-assistant/base:3.21

RUN apk add --no-cache \
    python3 \
    py3-pillow \
    py3-numpy

COPY server.py /server.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
