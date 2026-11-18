FROM alpine:3.20
RUN apk add --no-cache nginx php83 php83-fpm php83-json php83-mbstring \
      php83-curl php83-openssl php83-session php83-ctype php83-pdo \
      php83-pdo_mysql php83-pdo_sqlite php83-mysqli php83-zip php83-xml tzdata
ENV TZ=Europe/Vienna
COPY rootfs/ /
RUN chmod +x /run.sh
CMD ["/run.sh"]
