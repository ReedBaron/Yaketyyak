import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pro_users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            stripe_customer_id TEXT UNIQUE,
            stripe_subscription_id TEXT,
            license_key TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL DEFAULT 'pro_monthly',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_pro_users_license_key ON pro_users(license_key);
        CREATE INDEX IF NOT EXISTS idx_pro_users_stripe_customer ON pro_users(stripe_customer_id);

        CREATE TABLE IF NOT EXISTS api_usage (
            id SERIAL PRIMARY KEY,
            license_key TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            endpoint TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_api_usage_license_key ON api_usage(license_key);
        CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
    """)
    conn.commit()
    cur.close()
    conn.close()


def get_user_by_license_key(license_key):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM pro_users WHERE license_key = %s", (license_key,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return dict(user) if user else None


def get_user_by_email(email):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM pro_users WHERE LOWER(email) = LOWER(%s) AND status = 'active' ORDER BY created_at DESC LIMIT 1", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return dict(user) if user else None


def get_user_by_stripe_customer(customer_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM pro_users WHERE stripe_customer_id = %s", (customer_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return dict(user) if user else None


def create_user(email, stripe_customer_id, stripe_subscription_id, license_key, plan="pro_monthly"):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO pro_users (email, stripe_customer_id, stripe_subscription_id, license_key, plan, status)
        VALUES (%s, %s, %s, %s, %s, 'active')
        ON CONFLICT (stripe_customer_id) DO UPDATE SET
            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
            license_key = EXCLUDED.license_key,
            plan = EXCLUDED.plan,
            status = 'active',
            updated_at = NOW()
        RETURNING *
    """, (email, stripe_customer_id, stripe_subscription_id, license_key, plan))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(user) if user else None


def update_user_status(stripe_customer_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE pro_users SET status = %s, updated_at = NOW()
        WHERE stripe_customer_id = %s
    """, (status, stripe_customer_id))
    conn.commit()
    cur.close()
    conn.close()


def update_user_subscription(stripe_customer_id, subscription_id, plan=None):
    conn = get_conn()
    cur = conn.cursor()
    if plan:
        cur.execute("""
            UPDATE pro_users SET stripe_subscription_id = %s, plan = %s, updated_at = NOW()
            WHERE stripe_customer_id = %s
        """, (subscription_id, plan, stripe_customer_id))
    else:
        cur.execute("""
            UPDATE pro_users SET stripe_subscription_id = %s, updated_at = NOW()
            WHERE stripe_customer_id = %s
        """, (subscription_id, stripe_customer_id))
    conn.commit()
    cur.close()
    conn.close()


def log_usage(license_key, tokens_used, endpoint):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO api_usage (license_key, tokens_used, endpoint)
        VALUES (%s, %s, %s)
    """, (license_key, tokens_used, endpoint))
    conn.commit()
    cur.close()
    conn.close()


def get_monthly_usage(license_key):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(tokens_used), 0) as total_tokens
        FROM api_usage
        WHERE license_key = %s
        AND created_at >= date_trunc('month', NOW())
    """, (license_key,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return dict(result) if result else {"count": 0, "total_tokens": 0}
