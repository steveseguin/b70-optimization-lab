# ctxkeeper in a container: standard library only, so the image is just Python and two files.
#   docker build -t ctxkeeper https://github.com/steveseguin/b70-optimization-lab/releases/download/ctxkeeper-v1.2.0/ctxkeeper-1.2.0.tar.gz
#   docker run --rm --network host -v ctxkeeper-state:/state ctxkeeper --recipe agent --upstream http://127.0.0.1:8000
FROM python:3.12-slim
WORKDIR /app
COPY ctxkeeper.py notesdelta.py LICENSE /app/
VOLUME /state
EXPOSE 18200
ENTRYPOINT ["python3", "/app/ctxkeeper.py", "--host", "0.0.0.0", "--port", "18200", "--state-dir", "/state"]
CMD ["--recipe", "agent"]
