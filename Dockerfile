FROM python:3.11-slim

WORKDIR /app

# ffmpeg is required by faster-whisper to decode arbitrary input audio
# formats (it shells out to it internally for anything not already PCM/WAV).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV WHISPER_MODEL_SIZE=medium \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8

# SUBTITLE_SERVICE_API_KEY has no default here on purpose -- baking a secret
# into the image would leak it to anyone with the image. Pass it at run time:
#   docker run -e SUBTITLE_SERVICE_API_KEY=... -p 8100:8100 vimo-subtitle-service
# The process refuses to start without it (see app/auth.py).

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
