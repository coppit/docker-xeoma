FROM alpine:3.7

MAINTAINER David Coppit <david@coppit.org>

ENV TERM=xterm-256color

RUN true && \
\
echo "http://dl-cdn.alpinelinux.org/alpine/v3.7/community" >> /etc/apk/repositories && \
apk --update upgrade && \
\
# Basics, including runit
apk add bash curl htop runit && \
\
# Needed by our code
apk add alsa-lib python3 procps && \
wget "https://github.com/sgerrand/alpine-pkg-glibc/releases/download/2.28-r0/glibc-2.28-r0.apk" && \
apk add --allow-untrusted glibc-2.28-r0.apk && \
rm glibc-2.28-r0.apk && \
\
rm -rf /var/cache/apk/* && \
\
# RunIt stuff
adduser -h /home/user-service -s /bin/sh -D user-service -u 2000 && \
chown user-service:user-service /home/user-service && \
mkdir -p /etc/run_once /etc/service

# Boilerplate startup code
COPY ./boot.sh /sbin/boot.sh
RUN chmod +x /sbin/boot.sh
CMD [ "/sbin/boot.sh" ]

VOLUME [ "/config", "/archive" ]

EXPOSE 8090
EXPOSE 10090

# Create template config file
COPY xeoma.conf.default /files/

# run-parts ignores files with "." in them
COPY parse_config_file.sh /etc/run_once/30_parse_config_file
COPY 40_install_xeoma.py /etc/run_once/40_install_xeoma
COPY 50_configure_xeoma.sh /etc/run_once/50_configure_xeoma
RUN chmod +x /etc/run_once/40_install_xeoma /etc/run_once/50_configure_xeoma /etc/run_once/30_parse_config_file

# Add a cron job for updating Xeoma
COPY update_xeoma.sh /etc/periodic/hourly/update_xeoma

# Also start cron as a service
copy cron.sh /etc/service/cron/run
RUN chmod +x /etc/service/cron/run

copy xeoma.sh /etc/service/xeoma/run
RUN chmod +x /etc/service/xeoma/run
