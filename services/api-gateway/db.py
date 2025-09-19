import os
import psycopg2
from psycopg2.extras import Json


def get_conn():
    dsn = {
        "host": os.getenv("PGHOST", "postgres"),
        "port": int(os.getenv("PGPORT", "5432")),
        "user": os.getenv("PGUSER", "taas"),
        "password": os.getenv("PGPASSWORD", "taas"),
        "dbname": os.getenv("PGDATABASE", "taas"),
    }
    return psycopg2.connect(**dsn)


def ensure_schema():
    sql = """
    create table if not exists test_sessions (
      id uuid primary key,
      project text,
      kind text,
      test_type text,
      status text,
      created_at timestamptz default now(),
      updated_at timestamptz default now()
    );
    create table if not exists test_results (
      id bigserial primary key,
      session_id uuid references test_sessions(id) on delete cascade,
      summary jsonb,
      created_at timestamptz default now()
    );
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def insert_session(session_id: str, kind: str, test_type: str, project: str | None = None, status: str = "queued"):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into test_sessions(id, project, kind, test_type, status) values (%s,%s,%s,%s,%s)"
                " on conflict (id) do update set status=excluded.status, updated_at=now()",
                (session_id, project, kind, test_type, status),
            )
        conn.commit()

