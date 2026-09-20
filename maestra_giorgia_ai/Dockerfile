FROM ghcr.io/home-assistant/base:latest

LABEL io.hass.version="1.3.2" \
      io.hass.type="app" \
      io.hass.arch="aarch64|amd64"

RUN apk add --no-cache python3
WORKDIR /app
COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
