FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 JOB_HUNTER_DOCKER=1
WORKDIR /app/backend
COPY backend/pyproject.toml ./
# Install dependencies first for better layer caching
RUN python -c "import tomllib,subprocess,sys; d=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; subprocess.check_call([sys.executable,'-m','pip','install','--no-cache-dir',*d])"
COPY backend/ ./
COPY .env.example /app/.env.example
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
