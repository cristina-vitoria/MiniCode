FROM python:3.12-slim
COPY requirements.lock /opt/minicode-requirements.lock
RUN pip install --no-cache-dir -r /opt/minicode-requirements.lock
ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
