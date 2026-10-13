# -*- coding: utf-8 -*-
"""SQLite 数据层（WAL）。表结构对齐 spec §5，MVP 只落必要字段。"""
import atexit
import os
import threading
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .paths import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "deckforge.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, source_type TEXT DEFAULT 'markdown',
  intake_mode TEXT DEFAULT 'doc', source_path TEXT, parsed_text TEXT,
  target_pages INTEGER DEFAULT 0, style_pack_id TEXT, size TEXT DEFAULT '2K',
  status TEXT DEFAULT 'draft',                    -- draft|outlined|generating|done|failed
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS slides (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, page_no INTEGER NOT NULL,
  title TEXT, role TEXT, layout TEXT,
  outline TEXT, points_json TEXT DEFAULT '[]', must_keep_json TEXT DEFAULT '[]',
  keep INTEGER DEFAULT 1,
  image_path TEXT, width INTEGER, height INTEGER,
  status TEXT DEFAULT 'pending',                  -- pending|running|done|failed
  provider TEXT, model TEXT, size TEXT, cost_cny REAL DEFAULT 0,
  latency_ms INTEGER DEFAULT 0,
  editable INTEGER DEFAULT 0,                     -- 1=已转可编辑
  native_scene_json TEXT DEFAULT '{}',            -- 原生 PPTX 的结构化真源
  native_status TEXT DEFAULT 'pending',           -- pending|building|ready|failed|legacy_overlay
  native_object_count INTEGER DEFAULT 0,
  native_warnings_json TEXT DEFAULT '[]',
  verify_json TEXT, error TEXT,
  created_at TEXT, updated_at TEXT,
  UNIQUE(project_id, page_no)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT,
  total INTEGER DEFAULT 0, done INTEGER DEFAULT 0,
  status TEXT DEFAULT 'running',                  -- running|done|failed|cancelled
  message TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS usage_log (
  id TEXT PRIMARY KEY, ts TEXT, project_id TEXT, page_no INTEGER, action TEXT,
  provider TEXT, model TEXT, size TEXT, cny REAL DEFAULT 0,
  latency_ms INTEGER DEFAULT 0, ok INTEGER DEFAULT 1, detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_log_ts ON usage_log(ts);
CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
  path TEXT, pages INTEGER DEFAULT 0,
  editable_pages_json TEXT DEFAULT '[]', passthrough_pages_json TEXT DEFAULT '[]',
  size_bytes INTEGER DEFAULT 0, created_at TEXT
);
CREATE TABLE IF NOT EXISTS operation_submissions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 quote_json TEXT NOT NULL, job_id TEXT, response_json TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS operation_quotes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, fingerprint TEXT NOT NULL, body_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS slide_versions (
 id TEXT PRIMARY KEY, slide_id TEXT NOT NULL, snapshot_json TEXT NOT NULL, job_id TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_slide_versions_slide ON slide_versions(slide_id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
-- ── PPT 备注模块（独立于生成流程：上传已有 pptx → 逐页生成讲稿备注 → 写回备注栏）──
CREATE TABLE IF NOT EXISTS notes_jobs (
  id TEXT PRIMARY KEY,
  title TEXT,                       -- 展示名（原文件名去扩展名）
  source_name TEXT,                 -- 原始文件名
  source_path TEXT,                 -- 上传的 .pptx 绝对路径
  pages INTEGER DEFAULT 0,
  image_pages INTEGER DEFAULT 0,    -- 图片页（文本框文字过少、需视觉识别的页数）
  notes_existing INTEGER DEFAULT 0, -- 原文件已有备注的页数
  status TEXT DEFAULT 'uploaded',   -- uploaded|analyzing|analyzed|generating|done|failed
  render_dir TEXT,                  -- 渲染出的逐页 PNG 目录
  export_path TEXT,                 -- 最近一次导出产物
  cost_cny REAL DEFAULT 0,
  error TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS notes_pages (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  page_no INTEGER NOT NULL,
  text_source TEXT DEFAULT '',      -- 页面文本框/表格文字（我们提取的）
  pic_count INTEGER DEFAULT 0,
  note_original TEXT DEFAULT '',    -- 原文件该页已有备注
  low_info INTEGER DEFAULT 0,       -- 1=低信息页（文字少，靠画面）
  render_path TEXT,                 -- 该页渲染 PNG
  vision_json TEXT DEFAULT '{}',    -- 视觉识别结果（原始，可审计）
  vision_status TEXT DEFAULT 'pending',   -- pending|done|failed|skipped
  vision_model TEXT, vision_ms INTEGER DEFAULT 0, vision_cost_cny REAL DEFAULT 0,
  note TEXT DEFAULT '',             -- 最终备注正文
  note_status TEXT DEFAULT 'pending',     -- pending|running|done|failed
  note_model TEXT, note_ms INTEGER DEFAULT 0, note_cost_cny REAL DEFAULT 0,
  note_edited INTEGER DEFAULT 0,    -- 1=人工改过（重生成前提示会覆盖）
  note_prompt TEXT DEFAULT '',      -- 最近一次使用的自定义提示词
  error TEXT,
  created_at TEXT, updated_at TEXT,
  UNIQUE(job_id, page_no)
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def uid(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


_INITIALIZED = False


def _migrate(conn: sqlite3.Connection) -> None:
    """SQLite 的 CREATE TABLE 不会为旧库补字段，启动时做幂等轻量迁移。"""
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(slides)").fetchall()}
    additions = {
        "native_scene_json": "TEXT DEFAULT '{}'",
        "native_status": "TEXT DEFAULT 'pending'",
        "native_object_count": "INTEGER DEFAULT 0",
        "native_warnings_json": "TEXT DEFAULT '[]'",
    }
    for name, ddl in additions.items():
        if name not in existing:
            conn.execute("ALTER TABLE slides ADD COLUMN %s %s" % (name, ddl))
    for table, additions in {
        "exports": {"snapshot_json": "TEXT DEFAULT '[]'"},
        "usage_log": {"job_id": "TEXT"},
        "jobs": {"owner_pid": "INTEGER", "version": "INTEGER DEFAULT 0", "pages_json": "TEXT DEFAULT '{}'"},
        "projects": {"page_drafts_json": "TEXT", "pages_confirmed_at": "TEXT", "content_confirmed_at": "TEXT"},
        "slides": {"current_version_id": "TEXT", "source_page_no": "INTEGER", "display_order": "INTEGER",
                   "source_available": "INTEGER DEFAULT 1", "content_revision": "INTEGER DEFAULT 1", "generated_revision": "INTEGER",
                   "modules_json": "TEXT DEFAULT '[]'", "source_note": "TEXT DEFAULT ''",
                   "source_content_json": "TEXT", "material_strategy": "TEXT DEFAULT 'reference'",
                   "generated_style": "TEXT", "generated_content_json": "TEXT", "reviewed_image": "TEXT"},
    }.items():
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, ddl))
    # 旧 MVP 的 editable 只代表“PNG 上叠字”，绝不能误标为完整原生可编辑。
    conn.execute("UPDATE slides SET native_status='legacy_overlay' "
                 "WHERE editable=1 AND (native_status IS NULL OR native_status='pending')")


def _restrict_permissions() -> None:
    for path in (DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm"):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


_LOCAL = threading.local()
_CONNECTIONS: List[sqlite3.Connection] = []
_CONNECTION_LOCK = threading.Lock()


def _close_connections() -> None:
    with _CONNECTION_LOCK:
        for conn in _CONNECTIONS:
            conn.close()
        _CONNECTIONS.clear()


atexit.register(_close_connections)


def connect() -> sqlite3.Connection:
    global _INITIALIZED
    cached = getattr(_LOCAL, "connection", None)
    if cached is not None and _LOCAL.path == DB_PATH:
        return cached
    with _CONNECTION_LOCK:
        if cached is not None:
            cached.close()
            _CONNECTIONS.remove(cached)
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        # Queries use only the owning thread; disabling this check permits atexit
        # to close worker-thread connections after workers have stopped.
        conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None,
                               check_same_thread=False)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            if not _INITIALIZED:
                conn.executescript(SCHEMA)
                _migrate(conn)
                _INITIALIZED = True
        except BaseException:
            conn.close()
            raise
        _LOCAL.connection, _LOCAL.path = conn, DB_PATH
        _CONNECTIONS.append(conn)
        _restrict_permissions()
        return conn


def init_db() -> None:
    global _INITIALIZED
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
    _INITIALIZED = True


def q(sql: str, args: tuple = ()) -> List[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(sql, args).fetchall()


def q1(sql: str, args: tuple = ()) -> Optional[sqlite3.Row]:
    rows = q(sql, args)
    return rows[0] if rows else None


def x(sql: str, args: tuple = ()) -> int:
    with connect() as conn:
        cur = conn.execute(sql, args)
        return cur.rowcount


def insert(table: str, data: Dict[str, Any]) -> str:
    keys = list(data.keys())
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(keys), ",".join("?" * len(keys)))
    with connect() as conn:
        conn.execute(sql, tuple(data[k] for k in keys))
    return data.get("id", "")


_COLUMNS_CACHE: Dict[str, set] = {}


def table_columns(table: str) -> set:
    """表实际有哪些列（带缓存）。`update()` 据此决定要不要写 updated_at。"""
    if table not in _COLUMNS_CACHE:
        # 列探测是只读操作，不能提交调用方正在保存的版本事务。
        conn = connect()
        _COLUMNS_CACHE[table] = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)}
    return _COLUMNS_CACHE[table]


def update(table: str, id_value: str, data: Dict[str, Any]) -> None:
    """按主键更新。

    注意：只有表里**真的有** `updated_at` 列时才写它——`exports` 表就没有这列，
    以前无条件写会让所有对 exports 的更新抛 `no such column: updated_at`（实际踩过）。
    """
    data = dict(data)
    if "updated_at" in table_columns(table):
        data["updated_at"] = now()
    if not data:
        return
    sets = ", ".join("%s=?" % k for k in data)
    conn = connect()
    sql = "UPDATE %s SET %s WHERE id=?" % (table, sets)
    args = tuple(data.values()) + (id_value,)
    if conn.in_transaction:
        conn.execute(sql, args)
    else:
        with conn:
            conn.execute(sql, args)


# ── settings（key 存储；MVP 存本地文件，权限 600，读取时掩码）──
def setting_get(key: str, default: str = "") -> str:
    row = q1("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def setting_set(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# ── usage ──
def log_usage(project_id: Optional[str], page_no: Optional[int], action: str, provider: str,
              model: str, size: str, cny: float, latency_ms: int, ok: bool = True,
              detail: str = "", job_id: Optional[str] = None) -> None:
    if job_id is None:
        from .operations import submission_key
        key = submission_key.get()
        if key:
            row = q1("SELECT job_id FROM operation_submissions WHERE id=?", (key,))
            job_id = row["job_id"] if row else None
    insert("usage_log", dict(id=uid("u"), ts=now(), project_id=project_id, page_no=page_no,
                             action=action, provider=provider, model=model, size=size,
                             cny=round(float(cny), 4), latency_ms=int(latency_ms),
                             ok=1 if ok else 0, detail=detail, job_id=job_id))
