FROM phusion/baseimage:0.9.19

MAINTAINER David Coppit <david@coppit.org>

ENV TERM=xterm

# Use baseimage-docker's init system
CMD ["/sbin/my_init"]

RUN true && \

DEBIAN_FRONTEND=noninteractive && \

# Speed up APT
echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup && \
echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache && \

# Install prerequisites
apt-get update && \
apt-get install -qy libasound2 wget && \

# clean up
apt-get clean && \
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
/usr/share/man /usr/share/groff /usr/share/info \
/usr/share/lintian /usr/share/linda /var/cache/man && \
(( find /usr/share/doc -depth -type f ! -name copyright|xargs rm || true )) && \
(( find /usr/share/doc -empty|xargs rmdir || true ))

# Add local files
COPY xeoma.conf.default /files/

# Set up start up scripts
COPY 30_default_config_file.sh 40_install_xeoma.py 50_configure_xeoma.sh /etc/my_init.d/

# And a cron job for updating Xeoma
COPY update_xeoma.sh /etc/cron.hourly/update_xeoma

RUN mkdir /etc/service/xeoma
ADD xeoma.sh /etc/service/xeoma/run
RUN chmod +x /etc/service/xeoma/run

VOLUME [ "/config", "/archive" ]

EXPOSE 8090
EXPOSE 10090
