FROM alpine:3.20
RUN apk add --no-cache iproute2 bridge-utils tcpdump lldpd
COPY entrypoint.sh /entrypoint.sh
# the script lives in root's home, with a symlink so "pvlan" also works from anywhere
COPY pvlan /root/pvlan
RUN chmod +x /entrypoint.sh /root/pvlan && ln -s /root/pvlan /usr/local/bin/pvlan
# prompt and colors for every interactive shell (docker exec ... sh), also for login shells
COPY shellrc /etc/pvlan.shellrc
RUN cp /etc/pvlan.shellrc /root/.profile
ENV ENV=/etc/pvlan.shellrc
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
