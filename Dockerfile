FROM phusion/baseimage:0.9.19

MAINTAINER David Coppit <david@coppit.org>

ENV TERM=xterm

# Use baseimage-docker's init system
CMD ["/sbin/my_init"]

ENV DEBIAN_FRONTEND noninteractive

RUN \

# Speed up APT
echo "force-unsafe-io" > /etc/dpkg/dpkg.cfg.d/02apt-speedup && \
echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache && \

# Install prerequisites
apt-get update && \
apt-get install -qy libasound2 && \

# clean up
apt-get clean && \
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
/usr/share/man /usr/share/groff /usr/share/info \
/usr/share/lintian /usr/share/linda /var/cache/man && \
(( find /usr/share/doc -depth -type f ! -name copyright|xargs rm || true )) && \
(( find /usr/share/doc -empty|xargs rmdir || true )) && \

mkdir -p /files/stable /files/beta && \

# Grab latest 64bit builds for Linux. They don't publish versions to stable URLs, unfortunately. So running this
# Dockerfile later may end up grabbinga newer version.

# Current version is 16.12.26
curl -o /files/stable/xeoma_linux64.tgz http://felenasoft.com/xeoma/downloads/xeoma_linux64.tgz && \
tar -xvzf /files/stable/xeoma_linux64.tgz -C /files/stable && \
rm /files/stable/xeoma_linux64.tgz && \

# Current version is 17.3.30
curl -o /files/beta/xeoma_beta_linux64.tgz http://felenasoft.com/xeoma/downloads/xeoma_beta_linux64.tgz && \
tar -xvzf /files/beta/xeoma_beta_linux64.tgz -C /files/beta && \
rm /files/beta/xeoma_beta_linux64.tgz

# Add local files
COPY xeoma.conf.default /files/

# Set up start up scripts
ADD 50_configure_xeoma.sh /etc/my_init.d/

RUN mkdir /etc/service/xeoma
ADD xeoma.sh /etc/service/xeoma/run
RUN chmod +x /etc/service/xeoma/run

VOLUME [ "/config", "/archive" ]

EXPOSE 8090
