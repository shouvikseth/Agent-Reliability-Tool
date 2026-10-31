FROM python:3.11.14-slim@sha256:c8271b1f627d0068857dce5b53e14a9558603b527e46f1f901722f935b786a39
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
COPY docker/requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt && mkdir /input && chmod 755 /input
COPY docker/worker.py /opt/worker.py
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["python", "/opt/worker.py"]
