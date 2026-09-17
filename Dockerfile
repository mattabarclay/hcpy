# Python 3.13.15 on Debian trixie, official linux/amd64 manifest resolved 2026-09-17.
FROM docker.io/library/python:3.13.15-slim-trixie@sha256:cc9dffa47c8294ba9bb795a8dfaeb7b76f2b30acade2c52a461a2999d127eb00

ARG BASHIO_VERSION="v0.16.2"
ARG BASHIO_SHA256="d0f0c780c4badd103c00c572b1bf9645520d15a8a8070d6e3d64e35cb9f583aa"

WORKDIR /app

COPY requirements.txt ./

RUN apt-get update && \
  apt-get upgrade -y --no-install-recommends && \
  apt-get install -y --no-install-recommends curl tar gcc jq python3-dev libxml2-dev libxslt-dev && \
  dpkg --compare-versions "$(dpkg-query -W -f='${Version}' gzip)" ge '1.13-1+deb13u1' && \
  dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libpcre2-8-0)" ge '10.46-1~deb13u2' && \
  dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libsqlite3-0)" ge '3.46.1-7+deb13u2' && \
  dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libssh2-1t64)" ge '1.11.1-1+deb13u2' && \
  dpkg --compare-versions "$(dpkg-query -W -f='${Version}' perl-base)" ge '5.40.1-6+deb13u1' && \
  pip3 install --no-cache-dir -r requirements.txt && \
  pip3 install --no-cache-dir msgpack==1.2.1 && \
  pip3 uninstall -y setuptools pip && \
  apt-get remove -y gcc python3-dev && \
  apt-get autoremove -y \
    && curl -J -L -o /tmp/bashio.tar.gz \
        "https://github.com/hassio-addons/bashio/archive/${BASHIO_VERSION}.tar.gz" \
    && echo "${BASHIO_SHA256} /tmp/bashio.tar.gz" | sha256sum --check \
    && mkdir /tmp/bashio \
    && tar zxvf \
        /tmp/bashio.tar.gz \
        --strip 1 -C /tmp/bashio \
    && mv /tmp/bashio/lib /usr/lib/bashio \
    && ln -s /usr/lib/bashio/bashio /usr/bin/bashio \
    && apt-get clean \
    && find /var/lib/apt/lists /tmp -mindepth 1 -delete

COPY hc2mqtt.py hc-login.py HADiscovery.py HCDevice.py HCSocket.py HCxml2json.py discovery.yaml utils.py ./
COPY --chmod=0755 run.sh ./

CMD ["./run.sh"]
