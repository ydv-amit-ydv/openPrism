FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --create-home --uid 10001 openprism \
 && mkdir -p /data && chown openprism /data
COPY --chown=root:root . .
ENV OPENPRISM_DATA=/data
USER openprism
VOLUME /data
EXPOSE 5000
# HTTPS with an auto-generated certificate on 5000; the admin console listens on
# 127.0.0.1:47219 INSIDE the container (use `docker exec` or an SSH tunnel).
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "5000", "--admin-port", "47219"]
