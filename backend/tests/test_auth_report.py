from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.app import main, graph, services
from backend.app.storage import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'store', Store(tmp_path))
    monkeypatch.setattr(services.settings, 'environment', 'production')
    main.locks.clear()
    for uid in ('student', 'other'):
        main.store.put('user', uid, {'user_id': uid, 'role': 'STUDENT'})
    main.store.put('session', 'session', {'session_id':'session', 'user_id':'student', 'job_track':'AI 开发',
        'style':'ALL_ROUND', 'status':'COMPLETED', 'question':'', 'turn':1, 'target_question_count':3,
        'resume_id':None, 'question_bank':[], 'started_at':main.now(), 'history':[
            {'turn':1, 'question':'怎么评估知识库？', 'answer':'用真实问题集评估召回率和延迟', 'score':75,
             'feedback':'提到了离线指标，但缺少业务验收方法', 'dimensions':{'engineering_depth':75}}]})
    with TestClient(main.app) as client:
        client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user', 'student'))
        yield client


def test_logout_revokes_only_this_token_and_new_login_works(client):
    token = client.headers['Authorization'][7:]
    second = main.issue_token(main.store.get('user', 'student'))
    assert second != token
    assert client.post('/api/v1/auth/logout').status_code == 200
    assert client.get('/api/v1/interviews/session/report').status_code == 401
    with client.websocket_connect('/ws/interviews/session?token=' + token) as ws:
        with pytest.raises(WebSocketDisconnect): ws.receive_json()
    client.headers['Authorization'] = 'Bearer ' + second
    assert client.get('/api/v1/interviews/session/report').status_code == 200
    with client.websocket_connect('/ws/interviews/session?token=' + second) as ws:
        assert ws.receive_json()['type'] == 'SESSION_STATE'
        assert client.post('/api/v1/auth/logout').status_code == 200
        ws.send_json({'event':'ANSWER','turn':1,'text':'新回答'})
        with pytest.raises(WebSocketDisconnect): ws.receive_json()


def summary():
    return graph.InterviewSummary(conclusion='能建立评估思路，仍需将指标与业务验收关联。',
        strengths=['能提出真实问题集、召回率和延迟指标。'], priorities=['需要补充业务验收标准。'],
        next_steps=['为知识库写一份验收表，明确准确率、延迟与业务通过条件。'])


def test_report_summary_uses_whole_interview_and_is_persisted(client, monkeypatch):
    model = AsyncMock(return_value=summary())
    monkeypatch.setattr(graph, 'deepseek_json', model)
    assert client.get('/api/v1/interviews/session/report').json()['interview_summary'] is None
    for _ in range(2):
        result = client.post('/api/v1/interviews/session/summary')
        assert result.status_code == 200
        assert result.json()['strengths'] == summary().strengths
    assert model.await_count == 1
    context = model.call_args.args[1]
    assert context['user_id'] == 'student'
    assert context['history'][0]['answer'] == '用真实问题集评估召回率和延迟'
    assert client.get('/api/v1/interviews/session/report').json()['interview_summary'] == summary().model_dump()
    assert Store(main.store.path.parent).get('session', 'session')['interview_summary'] == summary().model_dump()


def test_summary_failure_preserves_report_and_retry_and_access_checks(client, monkeypatch):
    monkeypatch.setattr(graph, 'deepseek_json', AsyncMock(side_effect=services.ServiceError('模型暂忙')))
    assert client.post('/api/v1/interviews/session/summary').status_code == 502
    assert client.get('/api/v1/interviews/session/report').status_code == 200
    assert not main.store.get('session', 'session').get('interview_summary')
    monkeypatch.setattr(graph, 'deepseek_json', AsyncMock(return_value=summary()))
    assert client.post('/api/v1/interviews/session/summary').status_code == 200
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user','other'))
    assert client.post('/api/v1/interviews/session/summary').status_code == 404
    client.headers['Authorization'] = 'Bearer ' + main.issue_token(main.store.get('user','student'))
    session = main.store.get('session','session');session['status'] = 'IN_PROGRESS';main.store.put('session','session',session)
    assert client.post('/api/v1/interviews/session/summary').status_code == 409
