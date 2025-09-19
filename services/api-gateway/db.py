import os
import psycopg2
from psycopg2.extras import Json, RealDictCursor
import hashlib


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

    create table if not exists api_keys (
      id bigserial primary key,
      name text,
      project text,
      key_hash text not null,
      rate_limit_per_min int default 60,
      active boolean default true,
      created_at timestamptz default now()
    );
    create index if not exists idx_api_keys_hash on api_keys(key_hash);
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


def list_sessions(limit: int = 50, offset: int = 0, project: str | None = None, kind: str | None = None, status: str | None = None, test_type: str | None = None, since: str | None = None, until: str | None = None):
    q = "select id, project, kind, test_type, status, created_at, updated_at from test_sessions"
    where = []
    args = []
    if project:
        where.append("project = %s"); args.append(project)
    if kind:
        where.append("kind = %s"); args.append(kind)
    if status:
        where.append("status = %s"); args.append(status)
    if test_type:
        where.append("test_type = %s"); args.append(test_type)
    if since:
        where.append("created_at >= %s"); args.append(since)
    if until:
        where.append("created_at <= %s"); args.append(until)
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


def list_results(session_id: str, limit: int = 50, offset: int = 0):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "select id, session_id, created_at, summary from test_results where session_id=%s order by created_at desc limit %s offset %s",
                (session_id, limit, offset)
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def get_result(result_id: int):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id, session_id, created_at, summary from test_results where id=%s", (result_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def _hash_key(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def insert_api_key(name: str, project: str | None, raw_key: str, rate_limit_per_min: int = 60) -> dict:
    key_hash = _hash_key(raw_key)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "insert into api_keys(name, project, key_hash, rate_limit_per_min, active) values (%s,%s,%s,%s,true) returning id, name, project, rate_limit_per_min, active",
                (name, project, key_hash, rate_limit_per_min),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else {}


def list_api_keys(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id, name, project, rate_limit_per_min, active, created_at from api_keys order by id desc limit %s", (limit,))
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def verify_api_key(raw_key: str) -> dict | None:
    if not raw_key:
        return None
    key_hash = _hash_key(raw_key)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id, name, project, rate_limit_per_min, active from api_keys where key_hash=%s", (key_hash,))
            row = cur.fetchone()
            if not row:
                return None
            rec = dict(row)
            if not rec.get("active"):
                return None
            return rec


def update_api_key(key_id: int, active: bool | None = None, rate_limit_per_min: int | None = None) -> dict | None:
    sets = []
    args: list = []
    if active is not None:
        sets.append("active=%s"); args.append(active)
    if rate_limit_per_min is not None:
        sets.append("rate_limit_per_min=%s"); args.append(rate_limit_per_min)
    if not sets:
        return None
    args.append(key_id)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"update api_keys set {', '.join(sets)} where id=%s returning id, name, project, rate_limit_per_min, active, created_at", args)
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def list_projects() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select project, count(*) as sessions from test_sessions group by project order by sessions desc nulls last")
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]
