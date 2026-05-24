import psycopg2
from app.modules.auth.service import hash_password

conn = None
cursor = None

try:
    conn = psycopg2.connect(
        host='localhost',
        database='xpert_erp',
        user='xpert',
        password='rootadmin'
    )
    cursor = conn.cursor()

    # Get admin role ID
    cursor.execute("SELECT id FROM role WHERE code='admin' LIMIT 1")
    result = cursor.fetchone()
    if not result:
        print('ERROR: admin role not found')
        exit(1)
    admin_role_id = result[0]

    # Delete existing admin@gmail.com user
    cursor.execute("DELETE FROM app_user WHERE email = 'admin@gmail.com'")

    # Insert new admin user
    password_hash = hash_password('Test1234!')
    cursor.execute(
        """
        INSERT INTO app_user (garage_id, email, full_name, password_hash, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (1, 'admin@gmail.com', 'Admin User', password_hash, 'active')
    )
    admin_user_id = cursor.fetchone()[0]

    # Assign admin role
    cursor.execute(
        "INSERT INTO user_role (user_id, role_id) VALUES (%s, %s)",
        (admin_user_id, admin_role_id)
    )

    conn.commit()
    print('✓ Admin user created: admin@gmail.com / Test1234!')

except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    if conn:
        conn.rollback()
finally:
    if cursor:
        cursor.close()
    if conn:
        conn.close()
