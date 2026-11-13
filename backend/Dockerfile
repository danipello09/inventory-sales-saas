FROM python:3.12.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home developer
COPY --chown=developer:developer . .
USER developer
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
