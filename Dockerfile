FROM phusion/baseimage:0.11

MAINTAINER David Coppit <david@coppit.org>

ENV TERM=xterm-256color

# Use baseimage-docker's init system
CMD ["/sbin/my_init"]

RUN true && \
\
DEBIAN_FRONTEND=noninteractive && \
\
# Speed up APT
echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup && \
echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache && \
\
# Install prerequisites
apt-get update && \
apt-get install -qy libasound2 wget && \
\
# clean up
apt-get clean && \
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
/usr/share/man /usr/share/groff /usr/share/info \
/usr/share/lintian /usr/share/linda /var/cache/man && \
(( find /usr/share/doc -depth -type f ! -name copyright|xargs rm || true )) && \
(( find /usr/share/doc -empty|xargs rmdir || true ))

VOLUME [ "/config", "/archive" ]

EXPOSE 8090
EXPOSE 10090

# Create template config file
COPY xeoma.conf.default /files/

# Set up start up scripts
COPY parse_config_file.sh /etc/my_init.d/30_parse_config_file.sh
COPY 40_install_xeoma.py 50_configure_xeoma.sh /etc/my_init.d/
RUN chmod +x /etc/my_init.d/30_parse_config_file.sh /etc/my_init.d/40_install_xeoma.py /etc/my_init.d/50_configure_xeoma.sh

# Add a cron job for updating Xeoma
COPY update_xeoma.sh /etc/cron.hourly/update_xeoma
RUN chmod +x /etc/cron.hourly/update_xeoma

COPY xeoma.sh /etc/service/xeoma/run
RUN chmod +x /etc/service/xeoma/run

RUN mkdir /archive-cache && \
echo 'This is a placeholder to detect when a host volume is mapped to /archive-cache' > /archive-cache/4vagl0js6k
