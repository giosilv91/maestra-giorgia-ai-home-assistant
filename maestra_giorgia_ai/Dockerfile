FROM ghcr.io/home-assistant/base:latest

LABEL io.hass.version="1.3.1" \
      io.hass.type="app" \
      io.hass.arch="aarch64|amd64"

RUN apk add --no-cache python3 py3-pip\nRUN pip3 install --no-cache-dir --break-system-packages reportlab
WORKDIR /app
COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
