# 단일 컨테이너: app.py + src/he, src/geo, src/agent, src/rag 전체를 하나로 패키징 (도메인별 컨테이너 분리 없음)
FROM python:3.10-slim

WORKDIR /app

# Pyfhel(CKKS 라이브러리)은 pip 설치 시 네이티브 빌드가 필요함
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src/ src/
COPY data/ data/

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
