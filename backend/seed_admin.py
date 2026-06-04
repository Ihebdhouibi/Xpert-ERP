import asyncio
import logging
import asyncpg
from app.modules.auth.service import hash_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

async def seed() -> None:
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(
            host='127.0.0.1',
            port=5433,
            database='xpert_erp',
            user='xpert',
            password='xpert_dev_password',
        )

        # Get admin role ID
        admin_role_id = await conn.fetchval("SELECT id FROM role WHERE code='admin' LIMIT 1")
        if not admin_role_id:
            log.error("admin role not found")
            return

        # Delete existing admin@gmail.com user
        await conn.execute("DELETE FROM app_user WHERE email = 'admin@gmail.com'")

        # Insert new admin user
        password_hash = hash_password('Test1234!')
        admin_user_id = await conn.fetchval(
            """
            INSERT INTO app_user (garage_id, email, full_name, password_hash, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            1, 'admin@gmail.com', 'Admin User', password_hash, 'active',
        )

        # Assign admin role
        await conn.execute(
            "INSERT INTO user_role (user_id, role_id) VALUES ($1, $2)",
            admin_user_id, admin_role_id,
        )

        log.info("Admin user created: admin@gmail.com")

    except Exception as e:
        log.error("Seed failed: %s", e)
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()


if __name__ == '__main__':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
