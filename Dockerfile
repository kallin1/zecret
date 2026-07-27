# 단일 컨테이너: app.py + src/he, src/compliance, src/agent, src/rag 전체를 하나로 패키징 (도메인별 컨테이너 분리 없음)
FROM python:3.10-slim

WORKDIR /app

# TenSEAL은 이 베이스 이미지(cp310-manylinux)용 prebuilt wheel이 제공되어 별도 빌드 도구가 필요 없음

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src/ src/
COPY data/ data/
# scripts/도 함께 패키징한다 — authority_verify_node가 scripts/mock_authority_verify.py를
# "관리기관 HSM API 호출 자리"로 사용하기 때문에 지금 단계에서는 런타임에 필요하다.
# scripts/keys/(비밀키)는 .dockerignore에 의해 이 COPY에서 항상 제외된다. 실제 배포에서는
# scripts/mock_authority_verify.py 전체가 별도의, 이 이미지와 분리된 HSM 서비스로
# 교체되어야 하며, 이 이미지에는 비밀키를 다루는 코드가 전혀 포함되어서는 안 된다.
COPY scripts/ scripts/

# 이미지 빌드 전 `python scripts/generate_mock_ciphertexts.py`를 로컬에서 먼저 실행해
# src/db/ciphertext_cache.db와 src/he/public_context.bin을 준비해 두어야 한다 — 이
# 파일들은 COPY src/ src/에 포함되어 함께 패키징된다 (비밀키는 포함되지 않는다).

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
