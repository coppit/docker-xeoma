FROM phusion/baseimage:noble-1.0.2

LABEL org.opencontainers.image.authors="David Coppit <david@coppit.org>" \
      org.opencontainers.image.source="https://github.com/coppit/docker-xeoma"

ENV TERM=xterm-256color
ENV TZ=Etc/UTC

# Use baseimage-docker's init system
CMD ["/sbin/my_init"]

# Speed up APT and install prerequisites
RUN echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup && \
  echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache && \
  \
  # Install prerequisites
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -qy --no-install-recommends libasound2t64 iproute2 wget tzdata && \
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

# Set up start up scripts
COPY --chmod=0755 parse_config_file.sh /etc/my_init.d/30_parse_config_file.sh
COPY --chmod=0755 40_install_xeoma.py 50_configure_xeoma.sh /etc/my_init.d/

# Add a cron job for updating Xeoma
COPY --chmod=0755 update_xeoma.sh /etc/cron.hourly/update_xeoma

# Script to set permissions to not be world-writable
COPY --chmod=0755 update-permissions.sh /etc/cron.hourly/update-permissions

COPY --chmod=0755 xeoma.sh /etc/service/xeoma/run

RUN mkdir /archive-cache && \
  echo 'This is a placeholder to detect when a host volume is mapped to /archive-cache' > /archive-cache/4vagl0js6k
