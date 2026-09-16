import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import graph, main, services
from backend.app.storage import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'store', Store(tmp_path))
    monkeypatch.setattr(services.settings, 'environment', 'development')
    monkeypatch.setattr(services.settings, 'data_dir', tmp_path)
    for uid, role in [('student', 'STUDENT'), ('other', 'STUDENT'), ('teacher', 'TEACHER')]:
        main.store.put('user', uid, {'user_id': uid, 'role': role, 'username': uid, 'display_name': uid, 'class_name': ''})
    main.store.put('session', 'session', {'session_id': 'session', 'user_id': 'student', 'status': 'COMPLETED',
        'started_at': main.now(), 'job_track': 'AI 开发', 'question_bank': [{'question': '怎样评估 RAG？', 'answer': '分开评估检索和生成'}],
        'history': [{'turn': 1, 'question': '怎样评估 RAG？', 'answer': '看回答对不对', 'feedback': '还需评估召回',
                     'score': 60, 'dimensions': {'engineering_depth': 60}}]})
    with TestClient(main.app) as client:
        client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
        yield client


def review():
    return graph.QuestionReview(knowledge_points=['检索召回率与重排', '生成忠实度与业务验收'],
                                spoken_answer='我会先收集真实业务问题，把检索和生成分开评估，再检查端到端的业务通过率。')


def mark(client, session_id='session', turn=1):
    response = client.post('/api/v1/student/bookmarks', json={'session_id': session_id, 'turn': turn})
    assert response.status_code == 200
    return response.json()


def test_saved_review_persists_deduplicates_and_unmark_reuses_cache(client, monkeypatch):
    model = AsyncMock(return_value=review())
    monkeypatch.setattr(graph, 'deepseek_json', model)
    item = mark(client)
    assert item['status'] == 'pending'
    assert mark(client)['id'] == item['id']
    assert client.get('/api/v1/student/bookmarks').json()['total'] == 1
    for _ in range(2):
        response = client.post(f"/api/v1/student/bookmarks/{item['id']}/review")
        assert response.status_code == 200 and response.json()['review'] == review().model_dump()
    assert model.await_count == 1
    context = model.call_args.args[1]
    assert context['user_id'] == 'student'
    assert context['question'] == item['question'] and context['student_answer'] == '看回答对不对'
    assert context['question_bank'][0]['answer'] == '分开评估检索和生成'
    assert Store(main.store.path.parent).get('bookmark', item['id'])['review'] == review().model_dump()
    assert client.get('/api/v1/interviews/session/report').json()['turns'][0]['bookmark_id'] == item['id']
    for _ in range(2):
        assert client.delete(f"/api/v1/student/bookmarks/{item['id']}").status_code == 200
    assert client.get('/api/v1/student/bookmarks').json()['total'] == 0
    assert client.get('/api/v1/interviews/session/report').json()['turns'][0]['bookmark_id'] is None
    assert client.post(f"/api/v1/student/bookmarks/{item['id']}/review").status_code == 404
    assert mark(client)['review'] == review().model_dump()
    assert model.await_count == 1


def test_bookmarks_enforce_real_student_auth_ownership_and_completed_turn(client):
    item = mark(client)
    for uid, expected in [('other', 404), ('teacher', 403)]:
        client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', uid))
        assert client.post('/api/v1/student/bookmarks', json={'session_id': 'session', 'turn': 1}).status_code == expected
        assert client.delete(f"/api/v1/student/bookmarks/{item['id']}").status_code == expected
        assert client.post(f"/api/v1/student/bookmarks/{item['id']}/review").status_code == expected
        response = client.get('/api/v1/student/bookmarks')
        if uid == 'other':
            assert response.json()['items'] == []
        else:
            assert response.status_code == 403
    client.headers.clear()
    assert client.get('/api/v1/student/bookmarks').status_code == 401
    assert client.post('/api/v1/student/bookmarks', json={'session_id': 'session', 'turn': 1}).status_code == 401
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
    assert client.post('/api/v1/student/bookmarks', json={'session_id': 'session', 'turn': 99}).status_code == 404
    session = main.store.get('session', 'session'); session['status'] = 'IN_PROGRESS'
    main.store.put('session', 'session', session)
    assert client.post('/api/v1/student/bookmarks', json={'session_id': 'session', 'turn': 1}).status_code == 409
    session['status'] = 'COMPLETED'; session['user_id'] = 'development'; main.store.put('session', 'session', session)
    assert client.post('/api/v1/student/bookmarks', json={'session_id': 'session', 'turn': 1}).status_code == 404


def test_failed_generation_keeps_mark_and_retry_clears_failure(client, monkeypatch):
    monkeypatch.setattr(graph, 'deepseek_json', AsyncMock(side_effect=services.ServiceError('模型暂忙')))
    item = mark(client)
    path = f"/api/v1/student/bookmarks/{item['id']}/review"
    assert client.post(path).status_code == 502
    saved = client.get('/api/v1/student/bookmarks').json()['items'][0]
    assert saved['status'] == 'pending' and saved['review_error'] and not saved['review']
    monkeypatch.setattr(graph, 'deepseek_json', AsyncMock(return_value=review()))
    response = client.post(path)
    assert response.json()['status'] == 'ready' and response.json()['review_error'] is None


def test_pagination_has_ten_newest_questions_and_filters_owner(client):
    source = main.store.get('session', 'session')
    for i in range(12):
        session = deepcopy(source); session['session_id'] = f's{i}'
        main.store.put('session', f's{i}', session)
        item = mark(client, f's{i}')
        main.store.mutate('bookmark', item['id'], lambda row: row.update(created_at=f'2026-09-{i+1:02d}T00:00:00+00:00'))
    data = client.get('/api/v1/student/bookmarks').json()
    assert data['total'] == 12 and len(data['items']) == 10
    assert data['items'][0]['session_id'] == 's11'
    assert len(client.get('/api/v1/student/bookmarks?page=2').json()['items']) == 2
    assert client.get('/api/v1/student/bookmarks?page=0').status_code == 422
    assert not ({'user_id', 'review_lease', 'review_lease_until'} & set(data['items'][0]))


@pytest.mark.asyncio
async def test_concurrent_generation_is_claimed_once_and_unmark_stays_removed(client, monkeypatch):
    item = mark(client)
    started, release = asyncio.Event(), asyncio.Event()
    async def slow_model(*args):
        started.set(); await release.wait(); return review()
    model = AsyncMock(side_effect=slow_model)
    monkeypatch.setattr(graph, 'deepseek_json', model)
    first = asyncio.create_task(main.generate_bookmark_review(item['id'], client.headers['Authorization']))
    await started.wait()
    second = await main.generate_bookmark_review(item['id'], client.headers['Authorization'])
    assert second.status_code == 202
    main.remove_bookmark(item['id'], client.headers['Authorization'])
    release.set(); await first
    assert model.await_count == 1
    assert main.store.student_bookmarks('student')['total'] == 0
    assert mark(client)['status'] == 'ready'


def test_concurrent_mark_and_expired_generation_lease(client, monkeypatch):
    payload = main.BookmarkCreate(session_id='session', turn=1)
    with ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(lambda _: main.create_bookmark(payload, client.headers['Authorization']), range(8)))
    assert len({item['id'] for item in items}) == 1
    item = items[0]
    main.store.mutate('bookmark', item['id'], lambda row: row.update(review_lease='old-worker',
        review_lease_until=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()))
    monkeypatch.setattr(graph, 'deepseek_json', AsyncMock(return_value=review()))
    assert client.post(f"/api/v1/student/bookmarks/{item['id']}/review").json()['status'] == 'ready'


def test_actual_model_usage_belongs_to_student_and_cached_review_is_free(client, monkeypatch):
    monkeypatch.setattr(services.settings, 'deepseek_api_key', 'test')
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {'content': review().model_dump_json()}}],
        'usage': {'prompt_tokens': 50, 'completion_tokens': 20, 'total_tokens': 70}}))
    original = httpx.AsyncClient
    monkeypatch.setattr(services.httpx, 'AsyncClient', lambda **kwargs: original(transport=transport, **kwargs))
    item = mark(client)
    for _ in range(2):
        assert client.post(f"/api/v1/student/bookmarks/{item['id']}/review").status_code == 200
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'teacher'))
    assert client.get('/api/v1/teacher/usage').json()['totals']['student'] == 70


@pytest.mark.skipif(not os.getenv('MIANMIAN_TEST_POSTGRES_DSN'), reason='PostgreSQL integration DSN not supplied')
def test_postgres_bookmarks_are_atomic_and_persist_between_connections(monkeypatch):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    dsn = os.environ['MIANMIAN_TEST_POSTGRES_DSN']
    schema = 'test_mianmian_' + uuid4().hex
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        monkeypatch.setattr(services.settings, 'environment', 'production')
        monkeypatch.setattr(services.settings, 'database_url', make_conninfo(dsn, options=f'-c search_path={schema}'))
        monkeypatch.setattr(main, 'store', Store())
        monkeypatch.setattr(graph, 'deepseek_json', AsyncMock(return_value=review()))
        student = {'user_id': 'pg-student', 'role': 'STUDENT'}
        main.store.put('user', student['user_id'], student)
        main.store.put('session', 'pg-session', {'session_id': 'pg-session', 'user_id': student['user_id'],
            'status': 'COMPLETED', 'started_at': main.now(), 'job_track': 'AI 开发', 'question_bank': [],
            'history': [{'turn': 1, 'question': '怎样评估 RAG？', 'answer': '评估召回', 'feedback': '还需评估生成'}]})
        auth = 'Bearer ' + main.issue_token(student)
        payload = main.BookmarkCreate(session_id='pg-session', turn=1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(lambda _: main.create_bookmark(payload, auth), range(8)))
        assert len({item['id'] for item in items}) == 1
        assert Store().student_bookmarks(student['user_id'], page=1)['total'] == 1
        with TestClient(main.app) as client:
            client.headers['Authorization'] = auth
            assert client.post(f"/api/v1/student/bookmarks/{items[0]['id']}/review").json()['review'] == review().model_dump()
            assert Store().student_bookmarks(student['user_id'], session_id='pg-session')['items'][0]['review'] == review().model_dump()
            client.delete(f"/api/v1/student/bookmarks/{items[0]['id']}")
            assert Store().student_bookmarks(student['user_id'])['total'] == 0
            assert main.create_bookmark(payload, auth)['review'] == review().model_dump()
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
