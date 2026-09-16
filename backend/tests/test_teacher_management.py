import json
import os
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import main, graph, services
from backend.app.storage import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'store', Store(tmp_path))
    monkeypatch.setattr(services.settings, 'data_dir', tmp_path)
    monkeypatch.setattr(services.settings, 'environment', 'development')
    for uid, role in [('admin', 'ADMIN'), ('teacher', 'TEACHER'), ('student', 'STUDENT'), ('zero', 'STUDENT')]:
        main.store.put('user', uid, {'user_id': uid, 'username': uid, 'display_name': '小明' if uid == 'student' else uid,
                                   'role': role, 'class_name': '已有班级' if uid == 'student' else ''})
    with TestClient(main.app) as client:
        client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'teacher'))
        yield client


def test_class_roster_creation_transfer_and_permissions(client):
    data = client.get('/api/v1/teacher/classes').json()
    assert data['items'][0]['name'] == '已有班级'
    assert data['items'][0]['students'][0]['display_name'] == '小明'
    assert data['unassigned'][0]['user_id'] == 'zero'
    assert client.post('/api/v1/teacher/classes', json={'name': '新班级'}).status_code == 201
    assert client.post('/api/v1/teacher/classes', json={'name': ' 新班级 '}).status_code == 409
    assert client.post('/api/v1/teacher/classes', json={'name': '  '}).status_code == 422
    assert client.patch('/api/v1/teacher/users/zero/class', json={'class_name': '不存在'}).status_code == 422
    assert client.patch('/api/v1/teacher/users/zero/class', json={'class_name': '新班级'}).status_code == 200
    assert main.store.get('user', 'zero')['class_name'] == '新班级'
    assert client.patch('/api/v1/teacher/users/zero/class', json={'class_name': ''}).status_code == 200
    assert client.get('/api/v1/teacher/users').status_code == 200
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
    assert client.get('/api/v1/teacher/classes').status_code == 403
    assert client.get('/api/v1/teacher/users').status_code == 403
    assert client.patch('/api/v1/teacher/users/zero/class', json={'class_name': '新班级'}).status_code == 403
    assert client.post('/api/v1/teacher/classes', json={'name': '伪造班级'}).status_code == 403


def test_accounts_require_existing_class(client):
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'admin'))
    payload = {'username': 'new-student', 'password': 'test-password', 'display_name': '小红', 'class_name': '未创建'}
    assert client.post('/api/v1/teacher/users', json=payload).status_code == 422
    payload['class_name'] = '已有班级'
    response = client.post('/api/v1/teacher/users', json=payload)
    assert response.status_code == 201
    assert response.json()['display_name'] == '小红'
    login = client.post('/api/v1/auth/login', json={'username': payload['username'], 'password': payload['password']})
    assert login.json()['display_name'] == '小红'


def test_usage_students_names_zero_totals_and_local_dates(client):
    import sqlite3
    services.record_usage('student', 'deepseek', {'prompt_tokens': 100, 'completion_tokens': 40, 'total_tokens': 140})
    services.record_usage('teacher', 'deepseek', {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12})
    with sqlite3.connect(services.settings.data_dir / 'mianmian.sqlite3') as db:
        db.execute("UPDATE token_usage SET created_at='2026-09-14 16:01:00'")
    data = client.get('/api/v1/teacher/usage').json()
    assert data['totals'] == {'student': 140, 'zero': 0}
    assert data['items'][0]['display_name'] == '小明'
    assert data['daily'] == [{'user_id': 'student', 'date': '2026-09-15', 'tokens': 140, 'prompt_tokens': 100, 'completion_tokens': 40}]
    assert client.get('/api/v1/teacher/usage?user_id=zero').json()['items'][0]['tokens'] == 0
    assert data['staff_daily'] == [{'user_id': 'teacher', 'date': '2026-09-15', 'tokens': 12, 'prompt_tokens': 10, 'completion_tokens': 2}]
    students_only = client.get('/api/v1/teacher/usage?audience=student').json()
    assert students_only['staff_items'] == [] and students_only['staff_daily'] == []
    assert students_only['totals'] == {'student': 140, 'zero': 0}
    staff_only = client.get('/api/v1/teacher/usage?audience=staff').json()
    assert staff_only['items'] == [] and staff_only['daily'] == [] and staff_only['totals'] == {}
    assert {item['user_id']: item['tokens'] for item in staff_only['staff_items']} == {'teacher': 12, 'admin': 0}
    assert staff_only['staff_daily'] == data['staff_daily']
    assert client.get('/api/v1/teacher/usage?audience=staff&user_id=student').json()['staff_items'] == []
    assert client.get('/api/v1/teacher/usage?audience=invalid').status_code == 422
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
    assert client.get('/api/v1/teacher/usage').status_code == 403


def test_tracks_hide_answers_and_multi_track_selection(client, monkeypatch):
    for track in ('AI 开发', 'Python 后端', '未选岗位'):
        for n in range(41):
            qid = f'{track}-{n}'
            main.store.put('question', qid, {'id': qid, 'job_track': track, 'question': f'问题{n}', 'answer': '完整答案' * 2000})
    assert client.get('/api/v1/teacher/question-bank?page=1&job_track=AI 开发').json()['total'] == 41
    edit = client.patch('/api/v1/teacher/question-bank/AI 开发-0/answer', json={'answer': '已修改', 'job_track': '新岗位'})
    assert edit.status_code == 200 and edit.json()['job_track'] == '新岗位'
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
    tracks = client.get('/api/v1/student/question-tracks').json()['items']
    assert {'job_track': 'AI 开发', 'question_count': 40} in tracks
    assert all(set(t) == {'job_track', 'question_count'} for t in tracks)
    assert client.get('/api/v1/teacher/question-bank').status_code == 403
    model = AsyncMock(return_value=graph.NextQuestion(question='请介绍项目'))
    monkeypatch.setattr(graph, 'deepseek_json', model)
    response = client.post('/api/v1/interviews', json={'knowledge_tracks': ['AI 开发', 'Python 后端', 'AI 开发'], 'target_question_count': 10})
    assert response.status_code == 201
    bank = model.call_args.args[1]['question_bank']
    assert {q['job_track'] for q in bank} == {'AI 开发', 'Python 后端'}
    assert len(bank) == len({q['id'] for q in bank}) == 20
    assert main.store.get('question', 'Python 后端-0')['answer'] == '完整答案' * 2000
    assert client.post('/api/v1/interviews', json={'knowledge_tracks': ['失效岗位']}).status_code == 422


@pytest.mark.asyncio
async def test_model_usage_records_failed_validation_retry(client, monkeypatch):
    monkeypatch.setattr(services.settings, 'deepseek_api_key', 'test')
    responses = iter(['{}', json.dumps({'question': '请介绍项目'})])
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {'content': next(responses)}}],
        'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}}))
    original = httpx.AsyncClient
    monkeypatch.setattr(services.httpx, 'AsyncClient', lambda **kwargs: original(transport=transport, **kwargs))
    token = services.usage_user.set('student')
    try:
        await services.deepseek_json('test', {}, graph.NextQuestion)
    finally:
        services.usage_user.reset(token)
    assert client.get('/api/v1/teacher/usage').json()['totals']['student'] == 60


@pytest.mark.skipif(not os.getenv('MIANMIAN_TEST_POSTGRES_DSN'), reason='PostgreSQL integration DSN not supplied')
def test_postgres_billing_and_class_persistence(monkeypatch):
    import psycopg
    from psycopg.conninfo import make_conninfo
    from psycopg import sql
    dsn = os.environ['MIANMIAN_TEST_POSTGRES_DSN']
    schema = 'test_mianmian_' + uuid4().hex
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        monkeypatch.setattr(services.settings, 'environment', 'production')
        monkeypatch.setattr(services.settings, 'database_url', make_conninfo(dsn, options=f'-c search_path={schema}'))
        monkeypatch.setattr(main, 'store', Store())
        for uid, role in [('pg-teacher', 'TEACHER'), ('pg-student', 'STUDENT')]:
            main.store.put('user', uid, {'user_id': uid, 'username': uid, 'display_name': uid, 'class_name': '', 'role': role})
        services.record_usage('pg-student', 'deepseek', {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30})
        services.record_usage('pg-teacher', 'deepseek', {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10})
        with psycopg.connect(services.settings.postgres_dsn) as db:
            db.execute("UPDATE token_usage SET created_at='2026-09-14 16:01:00+00'")
        with TestClient(main.app) as client:
            client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'pg-teacher'))
            data = client.get('/api/v1/teacher/usage').json()
            assert data['totals'] == {'pg-student': 30}
            assert data['daily'][0]['date'] == '2026-09-15'
            staff = client.get('/api/v1/teacher/usage?audience=staff').json()
            assert staff['items'] == [] and staff['daily'] == []
            assert staff['staff_items'][0]['tokens'] == 10
            assert staff['staff_daily'] == [{'user_id': 'pg-teacher', 'date': '2026-09-15', 'tokens': 10, 'prompt_tokens': 7, 'completion_tokens': 3}]
            assert client.get('/api/v1/teacher/usage?audience=student').json()['staff_items'] == []
            assert client.get('/api/v1/teacher/usage?user_id=pg-student').json()['totals'] == {'pg-student': 30}
            assert client.post('/api/v1/teacher/classes', json={'name': 'PG 班'}).status_code == 201
            assert client.patch('/api/v1/teacher/users/pg-student/class', json={'class_name': 'PG 班'}).status_code == 200
            assert Store().get('user', 'pg-student')['class_name'] == 'PG 班'
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
