FROM ghcr.io/linuxserver/baseimage-ubuntu:resolute@sha256:3b5862c04c04d3cf3aed92ac6d4a75e0a36208fd15e2a968563a0c7e11898401

LABEL org.opencontainers.image.authors="David Coppit <david@coppit.org>" \
      org.opencontainers.image.source="https://github.com/coppit/docker-xeoma"

ENV TERM=xterm-256color
ENV TZ=Etc/UTC

# LinuxServer supplies /init and maps abc to PUID/PGID before Xeoma initialization.
ENV PUID=911 PGID=911 UMASK=022 S6_BEHAVIOUR_IF_STAGE2_FAILS=2

# Speed up APT and install prerequisites
RUN echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup && \
  echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache && \
  \
  # Install prerequisites
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -qy --no-install-recommends libasound2t64 iproute2 wget tzdata python3 procps && \
  \
  ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime && echo "${TZ}" > /etc/timezone && \
  \
  # clean up
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
  /usr/share/man /usr/share/groff /usr/share/info \
  /usr/share/lintian /usr/share/linda /var/cache/man && \
  find /usr/share/doc -depth -type f ! -name copyright -delete && \
  find /usr/share/doc -depth -type d -empty -delete

VOLUME [ "/config", "/archive" ]

EXPOSE 8090
EXPOSE 10090

# Create template config file
COPY xeoma.conf.default /files/

COPY --chmod=0755 parse_config_file.sh install_xeoma.py configure_xeoma.sh update_xeoma.sh /usr/local/lib/xeoma/
COPY root/ /

# Initialization and supervision through LinuxServer's s6 service graph.
COPY --chmod=0755 init-xeoma.sh /etc/s6-overlay/s6-rc.d/init-xeoma/run
COPY --chmod=0755 xeoma.sh /etc/s6-overlay/s6-rc.d/svc-xeoma/run

RUN mkdir /archive-cache && \
  echo 'This is a placeholder to detect when a host volume is mapped to /archive-cache' > /archive-cache/4vagl0js6k
