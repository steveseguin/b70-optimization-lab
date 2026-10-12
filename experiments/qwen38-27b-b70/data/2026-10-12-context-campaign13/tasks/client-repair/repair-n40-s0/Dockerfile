FROM python:3.12-slim
COPY more_itertools /app/more_itertools
COPY tests /app/tests
COPY tickets.jsonl end_text /opt/repair/
COPY next t /usr/local/bin/
RUN chmod +x /usr/local/bin/next /usr/local/bin/t && echo 'ulimit -v 163840 2>/dev/null' > /etc/repair-limits.sh     && sleep 1 && touch /opt/repair/.built
ENV BASH_ENV=/etc/repair-limits.sh
ENV http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
    PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
