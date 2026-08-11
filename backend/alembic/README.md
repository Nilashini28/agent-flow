Alembic migration environment.

Initialize with:
    alembic init alembic   # (already scaffolded here)

Generate a migration:
    alembic revision --autogenerate -m "message"

Apply migrations:
    alembic upgrade head
