import asyncio
import base64
import os
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from pypdf import PdfReader
import pytest

from backend.app import evaluation_sheet as sheet, main, services
from backend.app.storage import Store


def assessment(score=3):
    return {'criteria': {key: {'score': score, 'evidence': '说明了检索与生成分别评估，但缺少验收阈值。' if score else '本场未考查，需补充验证。',
            'sources': [{'turn': 1, 'quote': '检索与生成分别评估'}] if score else []} for key, *_ in sheet.RUBRIC},
            'project': '企业知识库；负责评测设计。', 'strengths': '能区分检索和生成的评估指标。',
            'risks': '尚缺少业务验收标准和异常场景。', 'follow_up': '补充现场代码及安全边界验证。'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'store', Store(tmp_path))
    monkeypatch.setattr(services.settings, 'environment', 'development')
    monkeypatch.setattr(services.settings, 'data_dir', tmp_path)
    for uid, role in [('student', 'STUDENT'), ('other', 'STUDENT'), ('teacher', 'TEACHER')]:
        main.store.put('user', uid, {'user_id': uid, 'display_name': '小明', 'username': uid, 'role': role})
    main.store.put('session', 'session', {'session_id': 'session', 'user_id': 'student', 'status': 'COMPLETED',
        'job_track': 'AI 应用开发', 'started_at': '2026-09-15T16:01:00+00:00', 'ended_at': '2026-09-15T16:13:30+00:00',
        'history': [{'turn': 1, 'question': '怎么评估？', 'answer': '检索与生成分别评估，需要业务验收。', 'feedback': '需要阈值'}]})
    with TestClient(main.app) as client:
        client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
        yield client


PATH = '/api/v1/interviews/session/evaluation-sheet'


@pytest.mark.parametrize('score,total,recommendation', [(1, 20, '不推荐'), (3, 60, '推荐'), (4, 80, '优先推荐'), (5, 100, '优先推荐'), (None, None, '待补面')])
def test_template_scoring_rules(score, total, recommendation):
    result = sheet.conclusion(assessment(score))
    assert result['total'] == total and result['recommendation'] == recommendation


def test_critical_failure_overrides_high_total_and_n_never_becomes_zero():
    data = assessment(5); data['criteria']['security']['score'] = 2
    assert sheet.conclusion(data) == {'total': 94.0, 'critical_pass': False, 'verified': True, 'recommendation': '不推荐'}
    data['criteria']['collaboration']['score'] = None
    result = sheet.conclusion(data)
    assert result['total'] is None and result['recommendation'] == '待补面' and result['critical_pass'] is False


def test_generation_is_cached_and_download_is_owned_single_page(client, monkeypatch):
    model = AsyncMock(return_value=sheet.SheetAssessment.model_validate(assessment()))
    monkeypatch.setattr(sheet, 'deepseek_json', model)
    assert client.get(PATH).json()['status'] == 'pending'
    assert client.get(PATH + '.pdf').status_code == 409
    for _ in range(2):
        response = client.post(PATH)
        assert response.status_code == 200 and response.json()['status'] == 'ready'
    assert model.await_count == 1
    assert model.call_args.args[1]['user_id'] == 'student'
    assert client.get(PATH).json()['total'] == 60
    pdf = client.get(PATH + '.pdf')
    assert pdf.status_code == 200 and pdf.headers['content-type'] == 'application/pdf'
    assert 'attachment;' in pdf.headers['content-disposition'] and 'no-store' in pdf.headers['cache-control']
    reader = PdfReader(BytesIO(pdf.content)); assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for expected in ['小明', '2026-09-16', '12.5', '60.0', '企业知识库', '第1轮', '待教师复核', '1 / 1']:
        assert expected in text
    assert '面试评价表使用说明' not in text and '1 / 2' not in text
    assert all(name in text for _, name, *_ in sheet.RUBRIC)
    cached = Store(main.store.path.parent).get('evaluation_sheet', 'session')
    assert base64.b64decode(cached['pdf']) == pdf.content
    assert client.get(PATH + '.pdf').content == pdf.content


def test_auth_ownership_and_completion_checks(client):
    for uid, code in [('other', 404), ('teacher', 403)]:
        client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', uid))
        assert client.post(PATH).status_code == code
        assert client.get(PATH).status_code == code
        assert client.get(PATH + '.pdf').status_code == code
    client.headers.clear()
    assert client.post(PATH).status_code == 401
    assert client.get(PATH + '.pdf').status_code == 401
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
    main.store.mutate('session', 'session', lambda s: s.update(status='IN_PROGRESS'))
    assert client.post(PATH).status_code == 409
    main.store.mutate('session', 'session', lambda s: s.update(status='COMPLETED', history=[]))
    assert client.post(PATH).status_code == 409


def test_model_failure_and_pdf_failure_are_retryable_without_rebilling(client, monkeypatch):
    model = AsyncMock(side_effect=services.ServiceError('模型暂忙'))
    monkeypatch.setattr(sheet, 'deepseek_json', model)
    assert client.post(PATH).status_code == 502
    assert client.get(PATH).json()['status'] == 'failed'
    model.side_effect = None; model.return_value = sheet.SheetAssessment.model_validate(assessment())
    renderer = sheet.render_pdf
    monkeypatch.setattr(sheet, 'render_pdf', lambda *args: (_ for _ in ()).throw(services.ServiceError('PDF 暂忙')))
    assert client.post(PATH).status_code == 502
    monkeypatch.setattr(sheet, 'render_pdf', renderer)
    assert client.post(PATH).json()['status'] == 'ready'
    assert model.await_count == 2


@pytest.mark.asyncio
async def test_invalid_model_citations_become_unverified(client, monkeypatch):
    data = assessment(); data['criteria']['code']['sources'][0]['quote'] = '编造的代码实现'
    monkeypatch.setattr(sheet, 'deepseek_json', AsyncMock(return_value=sheet.SheetAssessment.model_validate(data)))
    result = await sheet.assess(main.store.get('session', 'session'))
    assert result['criteria']['code']['score'] is None
    assert sheet.conclusion(result)['total'] is None
    assert sheet.conclusion(result)['recommendation'] == '待补面'


@pytest.mark.asyncio
async def test_concurrent_calls_claim_once_and_expired_claim_recovers(client, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    async def slow(*args):
        started.set(); await release.wait(); return assessment()
    model = AsyncMock(side_effect=slow); monkeypatch.setattr(sheet, 'assess', model)
    main.store.put('evaluation_sheet', 'session', {'version': sheet.VERSION, 'lease': 'dead', 'lease_until': '2000-01-01T00:00:00+00:00'})
    first = asyncio.create_task(main.create_evaluation_sheet('session', client.headers['Authorization']))
    await started.wait()
    second = await main.create_evaluation_sheet('session', client.headers['Authorization'])
    assert second.status_code == 202
    release.set(); assert (await first)['status'] == 'ready'
    assert model.await_count == 1


def test_long_text_all_n_and_missing_times_render_in_one_page():
    data = assessment(None)
    for row in data['criteria'].values(): row['evidence'] = '待验证安全边界与代码实现的具体做法。' * 2
    for key in ('project', 'strengths', 'risks', 'follow_up'): data[key] = '评' * 42
    details = sheet.metadata({'history': [], 'started_at': 'bad'}, {'display_name': '名' * 80})
    pdf = sheet.render_pdf(data, details)
    reader = PdfReader(BytesIO(pdf)); text = reader.pages[0].extract_text()
    assert len(reader.pages) == 1 and '暂不计算' in text and '待补面' in text
    assert '未记录' in text and '未分班' in text


def test_usage_is_attributed_to_student_and_cached_downloads_are_free(client, monkeypatch):
    monkeypatch.setattr(services.settings, 'deepseek_api_key', 'test')
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {'content': sheet.SheetAssessment.model_validate(assessment()).model_dump_json()}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}}))
    original = httpx.AsyncClient
    monkeypatch.setattr(services.httpx, 'AsyncClient', lambda **kwargs: original(transport=transport, **kwargs))
    for _ in range(2):
        assert client.post(PATH).json()['status'] == 'ready'
        assert client.get(PATH + '.pdf').status_code == 200
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'teacher'))
    assert client.get('/api/v1/teacher/usage').json()['totals']['student'] == 150


@pytest.mark.skipif(not os.getenv('MIANMIAN_TEST_POSTGRES_DSN'), reason='PostgreSQL test DSN not supplied')
def test_postgres_pdf_cache_persists_across_connections(client, monkeypatch):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    dsn = os.environ['MIANMIAN_TEST_POSTGRES_DSN']; schema = 'test_sheet_' + uuid4().hex
    users = main.store.list('user'); session = main.store.get('session', 'session')
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        monkeypatch.setattr(services.settings, 'environment', 'production')
        monkeypatch.setattr(services.settings, 'database_url', make_conninfo(dsn, options=f'-c search_path={schema}'))
        monkeypatch.setattr(main, 'store', Store())
        for user in users: main.store.put('user', user['user_id'], user)
        main.store.put('session', 'session', session)
        model = AsyncMock(return_value=sheet.SheetAssessment.model_validate(assessment()))
        monkeypatch.setattr(sheet, 'deepseek_json', model)
        assert client.post(PATH).json()['status'] == 'ready'
        persisted = Store().get('evaluation_sheet', 'session')
        assert persisted['user_id'] == 'student'
        assert base64.b64decode(persisted['pdf']) == client.get(PATH + '.pdf').content
        monkeypatch.setattr(main, 'store', Store())
        assert client.post(PATH).json()['status'] == 'ready'
        assert model.await_count == 1
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
