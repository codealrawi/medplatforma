"""
database.py — модуль PostgreSQL для МедПлатформы
Подключается через asyncpg, graceful fallback на in-memory
"""
import os, ssl, logging

logger = logging.getLogger(__name__)

DB_HOST     = os.getenv("DB_HOST",     "")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME",     "default_db")
DB_USER     = os.getenv("DB_USER",     "gen_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

pool = None


async def init_pool():
    """Вызывается при startup FastAPI. Возвращает True если успешно."""
    global pool
    if not DB_HOST or not DB_PASSWORD:
        logger.warning("DB_HOST или DB_PASSWORD не заданы — работаю без БД")
        return False
    try:
        import asyncpg
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        pool = await asyncpg.create_pool(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            ssl=ctx, min_size=1, max_size=5, command_timeout=10,
        )
        await pool.fetchval("SELECT 1")
        logger.info(f"PostgreSQL OK: {DB_HOST}/{DB_NAME}")
        return True
    except Exception as e:
        logger.error(f"PostgreSQL ОШИБКА: {e}")
        pool = None
        return False


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


async def db_ok() -> bool:
    if not pool:
        return False
    try:
        await pool.fetchval("SELECT 1")
        return True
    except Exception:
        return False
