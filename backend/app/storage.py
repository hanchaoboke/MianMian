import json
import sqlite3
import re
from contextlib import contextmanager
from uuid import uuid4
from .services import settings

try:
    import psycopg
except ImportError:
    psycopg = None


class Store:
    """Single-process teaching MVP: durable records with atomic import commits."""
    def __init__(self, directory=None):
        self.postgres = directory is None and settings.environment == 'production'
        if self.postgres:
            if not settings.database_url or psycopg is None:
                raise RuntimeError('生产环境必须配置 DATABASE_URL，并安装 psycopg[binary]')
            self.path = None
            with self.connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, data JSONB NOT NULL, PRIMARY KEY(kind,id))')
                db.execute("CREATE INDEX IF NOT EXISTS bookmarks_owner_created_idx ON records ((data->>'user_id'), (data->>'created_at') DESC) WHERE kind='bookmark' AND data->>'active'='true'")
            return
        directory = directory or settings.data_dir
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'mianmian.sqlite3'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, data TEXT, PRIMARY KEY(kind,id))')
            db.execute("CREATE INDEX IF NOT EXISTS bookmarks_owner_created_idx ON records (json_extract(data, '$.user_id'), json_extract(data, '$.created_at') DESC) WHERE kind='bookmark' AND json_extract(data, '$.active')=1")

    @contextmanager
    def connect(self):
        if self.postgres:
            with psycopg.connect(settings.postgres_dsn) as db:
                yield db
            return
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, kind, id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM records WHERE kind=%s AND id=%s' if self.postgres else 'SELECT data FROM records WHERE kind=? AND id=?', (kind,id)).fetchone()
        return row[0] if self.postgres and row else (json.loads(row[0]) if row else None)

    def overview(self):
        with self.connect() as db:
            counts = dict(db.execute('SELECT kind,count(*) FROM records GROUP BY kind').fetchall())
            if self.postgres:
                has_usage = db.execute("SELECT to_regclass('token_usage')").fetchone()[0] is not None
                has_migration = db.execute("SELECT to_regclass('storage_migrations')").fetchone()[0] is not None
            else:
                has_usage = db.execute("SELECT name FROM sqlite_master WHERE name='token_usage'").fetchone() is not None
                has_migration = False
            usage = db.execute('SELECT count(*),coalesce(sum(total_tokens),0) FROM token_usage').fetchone() if has_usage else (0, 0)
            migration = db.execute('SELECT details FROM storage_migrations ORDER BY completed_at DESC LIMIT 1').fetchone() if has_migration else None
        return {'record_counts': counts, 'record_total': sum(counts.values()), 'usage_rows': usage[0],
                'total_tokens': int(usage[1]), 'migration': migration[0] if migration else None}

    def list(self, kind):
        with self.connect() as db:
            rows = db.execute('SELECT data FROM records WHERE kind=%s ORDER BY id DESC' if self.postgres else 'SELECT data FROM records WHERE kind=? ORDER BY rowid DESC', (kind,)).fetchall()
        return [row[0] if self.postgres else json.loads(row[0]) for row in rows]

    def put(self, kind, id, data):
        with self.connect() as db:
            if self.postgres:
                db.execute('INSERT INTO records(kind,id,data) VALUES(%s,%s,%s) ON CONFLICT(kind,id) DO UPDATE SET data=EXCLUDED.data', (kind,id,json.dumps(data,ensure_ascii=False)))
            else:
                db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (kind,id,json.dumps(data,ensure_ascii=False)))

    def mutate(self, kind, id, change, initial=None):
        """Atomically change a record, including concurrent creation across workers."""
        with self.connect() as db:
            if not self.postgres:
                db.execute('BEGIN IMMEDIATE')
            if initial is not None:
                db.execute('INSERT INTO records(kind,id,data) VALUES(%s,%s,%s) ON CONFLICT(kind,id) DO NOTHING' if self.postgres else
                           'INSERT INTO records(kind,id,data) VALUES(?,?,?) ON CONFLICT(kind,id) DO NOTHING',
                           (kind, id, json.dumps(initial, ensure_ascii=False)))
            row = db.execute('SELECT data FROM records WHERE kind=%s AND id=%s FOR UPDATE' if self.postgres else
                             'SELECT data FROM records WHERE kind=? AND id=?', (kind, id)).fetchone()
            if row is None:
                return None
            record = row[0] if self.postgres else json.loads(row[0])
            change(record)
            db.execute('UPDATE records SET data=%s WHERE kind=%s AND id=%s' if self.postgres else
                       'UPDATE records SET data=? WHERE kind=? AND id=?',
                       (json.dumps(record, ensure_ascii=False), kind, id))
            return record

    def student_bookmarks(self, user_id, *, session_id=None, page=None, page_size=10):
        placeholder = '%s' if self.postgres else '?'
        field = (lambda name: f"data->>'{name}'") if self.postgres else (lambda name: f"json_extract(data, '$.{name}')")
        active = f"{field('active')} = 'true'" if self.postgres else f"{field('active')} = 1"
        where = f"kind='bookmark' AND {field('user_id')}={placeholder} AND {active}"
        params = [user_id]
        if session_id is not None:
            where += f" AND {field('session_id')}={placeholder}"
            params.append(session_id)
        with self.connect() as db:
            total = db.execute(f'SELECT COUNT(*) FROM records WHERE {where}', params).fetchone()[0]
            query = f"SELECT data FROM records WHERE {where} ORDER BY {field('created_at')} DESC, id DESC"
            if page is not None:
                query += f' LIMIT {placeholder} OFFSET {placeholder}'
                params.extend([page_size, (page - 1) * page_size])
            rows = db.execute(query, params).fetchall()
        return {'items': [r[0] if self.postgres else json.loads(r[0]) for r in rows],
                'total': total, 'page': page, 'page_size': page_size}

    def delete_trashed_question(self, id):
        with self.connect() as db:
            if not self.postgres:
                db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT data FROM records WHERE kind=%s AND id=%s FOR UPDATE' if self.postgres else
                             'SELECT data FROM records WHERE kind=? AND id=?', ('question', id)).fetchone()
            if row is None:
                return False
            record = row[0] if self.postgres else json.loads(row[0])
            if not record.get('deleted_at'):
                raise ValueError('请先将题目移入回收箱')
            db.execute('DELETE FROM records WHERE kind=%s AND id=%s' if self.postgres else
                       'DELETE FROM records WHERE kind=? AND id=?', ('question', id))
            return True

    def list_page(self, kind, page, page_size=10):
        with self.connect() as db:
            placeholder = '%s' if self.postgres else '?'
            total = db.execute(f'SELECT COUNT(*) FROM records WHERE kind={placeholder}', (kind,)).fetchone()[0]
            order = 'id DESC' if self.postgres else 'rowid DESC'
            rows = db.execute(
                f'SELECT data FROM records WHERE kind={placeholder} ORDER BY {order} LIMIT {placeholder} OFFSET {placeholder}',
                (kind, page_size, (page - 1) * page_size),
            ).fetchall()
        return {'items': [r[0] if self.postgres else json.loads(r[0]) for r in rows],
                'total': total, 'page': page, 'page_size': page_size}

    def update_answer(self, id, answer, updated_at, updated_by, job_track=None):
        with self.connect() as db:
            if not self.postgres:
                db.execute('BEGIN IMMEDIATE')
            row = db.execute(
                'SELECT data FROM records WHERE kind=%s AND id=%s FOR UPDATE' if self.postgres else
                'SELECT data FROM records WHERE kind=? AND id=?', ('question', id),
            ).fetchone()
            if row is None:
                return None
            question = row[0] if self.postgres else json.loads(row[0])
            if question.get('deleted_at'):
                return None
            question.update(answer=answer, updated_at=updated_at, updated_by=updated_by)
            if job_track is not None:
                question['job_track'] = job_track
            # UPDATE keeps list order stable; INSERT OR REPLACE would move SQLite rows.
            db.execute('UPDATE records SET data=%s WHERE kind=%s AND id=%s' if self.postgres else
                       'UPDATE records SET data=? WHERE kind=? AND id=?',
                       (json.dumps(question, ensure_ascii=False), 'question', id))
        return question

    def commit_import(self, id, questions):
        with self.connect() as db:
            if not self.postgres: db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT data FROM records WHERE kind=%s AND id=%s FOR UPDATE' if self.postgres else 'SELECT data FROM records WHERE kind=? AND id=?', ('import',id)).fetchone()
            if not row:
                raise ValueError('导入记录不存在')
            draft = row[0] if self.postgres else json.loads(row[0])
            if draft.get('committed'):
                return draft
            ids = []
            existing_rows = db.execute('SELECT data FROM records WHERE kind=%s' if self.postgres else 'SELECT data FROM records WHERE kind=?', ('question',)).fetchall()
            existing_keys = set()
            for existing in existing_rows:
                value = existing[0] if self.postgres else json.loads(existing[0])
                existing_keys.add(re.sub(r'\s+', '', (value.get('question') or '').strip()).casefold())
            skipped = 0
            for item in questions:
                key = re.sub(r'\s+', '', (item.get('question') or '').strip()).casefold()
                if key and key in existing_keys:
                    skipped += 1
                    continue
                qid = str(uuid4())
                record = {**item, 'id':qid, 'import_id':id, 'source_file':draft['filename'], 'job_track':draft['job_track']}
                if self.postgres:
                    db.execute('INSERT INTO records(kind,id,data) VALUES(%s,%s,%s)', ('question',qid,json.dumps(record,ensure_ascii=False)))
                else:
                    db.execute('INSERT INTO records VALUES (?,?,?)', ('question',qid,json.dumps(record,ensure_ascii=False)))
                ids.append(qid)
                existing_keys.add(key)
            draft.update(committed=True, question_ids=ids, questions=questions, skipped_duplicates=skipped)
            db.execute('UPDATE records SET data=%s WHERE kind=%s AND id=%s' if self.postgres else 'UPDATE records SET data=? WHERE kind=? AND id=?', (json.dumps(draft,ensure_ascii=False),'import',id))
        return draft


store = Store()
