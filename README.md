# Qaryati - Palestinian Villages Knowledge Platform

## Run
```bash
cp .env.example .env
docker compose up --build
```
- Swagger: http://localhost:8000/docs
- Health:  http://localhost:8000/api/v1/health

## Test
```bash
pip install -r requirements.txt
pytest
```

## Database migrations
```bash
docker compose exec api alembic upgrade head      # apply
docker compose exec api alembic downgrade -1      # rollback one step
docker compose exec api alembic revision --autogenerate -m "message"
```
