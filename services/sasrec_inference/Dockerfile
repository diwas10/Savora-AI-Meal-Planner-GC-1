FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    HOME=/home/app

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt
COPY --chown=app:app app.py model.py sasrec_content.pt sasrec_content.json /app/
USER app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--limit-concurrency", "16", "--timeout-keep-alive", "5", "--no-access-log"]
