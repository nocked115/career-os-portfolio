# Career OS — 한 컨테이너에 화면과 API 를 같이 담는다.
#
# 둘로 나누면 CORS, 두 개의 URL, 두 번의 배포가 생긴다.
# 1인용 앱에 그럴 이유가 없다.

# --- 1단계: 화면을 빌드한다 ---
FROM node:22-slim AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# 같은 서비스가 API 도 내므로 주소를 비워 같은 출처를 쓰게 한다.
ENV VITE_API_BASE_URL=""
RUN npm run build


# --- 2단계: 실행 ---
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# 빌드된 화면을 backend/static 으로 옮긴다 (main.py 가 여기서 찾는다).
COPY --from=frontend /frontend/dist ./static

# DB 가 놓일 자리. 이 줄이 없으면 볼륨 없이 띄울 때
# "unable to open database file" 로 죽는다 — 데모 배포가 그 경우다.
# 볼륨을 붙이면 이 위에 덮인다.
RUN mkdir -p /data

# 실사용은 /data 를 영속 볼륨으로 잡는다.
# 데모는 CAREER_OS_SEED_DEMO=1 로 매번 다시 채우므로 볼륨이 없어도 된다.
ENV CAREER_OS_DATABASE_URL="sqlite:////data/career_os.db" \
    CAREER_OS_ENV=production

EXPOSE 8000

# 스키마는 Alembic 이 소유한다. 뜰 때마다 최신으로 맞춘다.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
