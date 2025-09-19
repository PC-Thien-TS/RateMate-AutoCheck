import os
import psycopg2
from psycopg2.extras import Json, RealDictCursor


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


def list_sessions(limit: int = 50, offset: int = 0, project: str | None = None, kind: str | None = None, status: str | None = None):
    q = "select id, project, kind, test_type, status, created_at, updated_at from test_sessions"
    where = []
    args = []
    if project:
        where.append("project = %s"); args.append(project)
    if kind:
        where.append("kind = %s"); args.append(kind)
    if status:
        where.append("status = %s"); args.append(status)
    if where:
        q += " where " + " and ".join(where)
    q += " order by created_at desc limit %s offset %s"
    args.extend([limit, offset])
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(q, args)
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def get_session(session_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id, project, kind, test_type, status, created_at, updated_at from test_sessions where id=%s", (session_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def latest_result(session_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id, created_at, summary from test_results where session_id=%s order by created_at desc limit 1", (session_id,))
            row = cur.fetchone()
            return dict(row) if row else None

