FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CC=gcc \
    CXX=g++ \
    CMAKE_BUILD_PARALLEL_LEVEL=2 \
    CMAKE_ARGS="-DGGML_CUDA=OFF -DGGML_NATIVE=OFF"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential cmake libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-agent.txt requirements-agent-base.txt ./
RUN pip install --no-cache-dir -r requirements-agent.txt

COPY agent_workspace ./agent_workspace
COPY agent_samples ./agent_samples
COPY scripts/download_agent_model.py ./scripts/download_agent_model.py

RUN useradd --create-home --uid 1000 user \
    && mkdir -p /home/user/ledgerlens-data \
    && chmod -R a+rX /app \
    && chown -R user:user /home/user/ledgerlens-data
USER user
ENV LEDGERLENS_DATA_DIR=/home/user/ledgerlens-data
EXPOSE 7860
CMD ["sh", "-c", "python scripts/download_agent_model.py && uvicorn agent_workspace.api:app --host 0.0.0.0 --port 7860"]
