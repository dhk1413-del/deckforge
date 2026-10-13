"""保留真实生成资产与输入快照；切换版本不修改页面内容。"""
import json
import os
from . import db

FIELDS = ('image_path', 'width', 'height', 'provider', 'model', 'size', 'cost_cny',
          'latency_ms', 'generated_revision', 'generated_style', 'generated_content_json',
          'verify_json', 'reviewed_image', 'editable', 'native_status', 'native_scene_json',
          'native_object_count', 'native_warnings_json', 'error')


def preserve(conn, row, job_id=None):
    if not row.get('image_path'):
        return None
    vid = db.uid('v')
    snapshot = {key: row.get(key) for key in FIELDS}
    conn.execute('INSERT INTO slide_versions VALUES(?,?,?,?,?)',
                 (vid, row['id'], json.dumps(snapshot, ensure_ascii=False), job_id, db.now()))
    conn.execute('UPDATE slides SET current_version_id=? WHERE id=?', (vid, row['id']))
    return vid


def backfill():
    conn = db.connect()
    conn.execute('BEGIN IMMEDIATE')
    try:
        for row in conn.execute('SELECT * FROM slides WHERE image_path IS NOT NULL AND current_version_id IS NULL').fetchall():
            preserve(conn, dict(row))
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise


def select(slide_id, version_id):
    conn = db.connect()
    conn.execute('BEGIN IMMEDIATE')
    try:
        version = conn.execute('SELECT * FROM slide_versions WHERE id=? AND slide_id=?', (version_id, slide_id)).fetchone()
        if not version:
            raise ValueError('版本不存在')
        data = json.loads(version['snapshot_json'])
        if not os.path.isfile(data.get('image_path') or '') or not os.path.getsize(data['image_path']):
            raise ValueError('版本资产不可访问，无法回退；历史记录仍保留')
        data.update(current_version_id=version_id, status='done', updated_at=db.now())
        conn.execute('UPDATE slides SET '+','.join(key+'=?' for key in data)+' WHERE id=?', (*data.values(), slide_id))
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
