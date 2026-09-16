import asyncio
import json
import hashlib
import sqlite3
import base64
import hmac
import logging
import random
from contextlib import suppress
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool

from .graph import interview_graph, summarize_interview, review_question, generate_reference_answer, compare_retry
from .services import (MAX_UPLOAD, MAX_AUDIO_UPLOAD, MAX_ANSWER_CHARACTERS, ServiceError, ExtractedQuestion, settings, usage_user, deepseek_extract_questions,
                       extract_document_text, save_upload, siliconflow_asr, siliconflow_tts)
from .storage import store
from . import evaluation_sheet

app = FastAPI(title='MianMian 面面俱道', version='0.2.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['*'], allow_headers=['*'])
# Run one worker for this local MVP. Persisted state is protected for concurrent WS/REST writes.
locks: dict[str, asyncio.Lock] = {}

def now():
    return datetime.now(timezone.utc).isoformat()


def require(kind, id):
    value = store.get(kind, id)
    if value is None:
        raise HTTPException(404, '记录不存在')
    return value

def password_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

if not store.get('user', 'admin-default'):
    store.put('user', 'admin-default', {'user_id':'admin-default','username':settings.admin_username,'display_name':'系统管理员','role':'ADMIN','class_name':'','password_hash':password_hash(settings.admin_password),'created_at':now()})

JWT_SECRET = settings.jwt_secret
def issue_token(user):
    raw = json.dumps({'sub': user['user_id'], 'role': user['role'], 'jti': str(uuid4()), 'exp': int(datetime.now(timezone.utc).timestamp()) + 86400}, separators=(',',':')).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    sig = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return body + '.' + base64.urlsafe_b64encode(sig).decode().rstrip('=')
def current_user(authorization: str | None = None, role: str | None = None):
    if settings.environment != 'production' and not authorization:
        return {'user_id':'development','role':role or 'TEACHER'}
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401, '请先登录')
    try:
        body, sig = authorization[7:].split('.', 1)
        expected = base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip('=')
        if not hmac.compare_digest(sig, expected): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if payload['exp'] < int(datetime.now(timezone.utc).timestamp()): raise ValueError
        if store.get('revoked_token', hashlib.sha256(authorization[7:].encode()).hexdigest()): raise ValueError
        user = store.get('user', payload['sub'])
        if not user or (role and user['role'] not in role.split(',')): raise HTTPException(403, '没有访问权限')
        return user
    except HTTPException: raise
    except Exception as exc: raise HTTPException(401, '登录已失效，请重新登录') from exc

class LoginPayload(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)

class TeacherUserPayload(LoginPayload):
    display_name: str = Field(default='', max_length=80)
    class_name: str = Field(default='', max_length=100)
    role: Literal['STUDENT','TEACHER'] = 'STUDENT'

@app.post('/api/v1/auth/login')
def login(payload: LoginPayload):
    users = store.list('user')
    user = next((u for u in users if u['username'] == payload.username), None)
    if not user or user['password_hash'] != password_hash(payload.password):
        raise HTTPException(401, '用户名或密码错误')
    return {'access_token': issue_token(user), 'token_type':'bearer', **{k: user[k] for k in ('user_id', 'username', 'display_name', 'role', 'class_name')}}


@app.post('/api/v1/auth/logout')
def logout(authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(401, '请先登录')
    user = current_user(authorization)
    store.put('revoked_token', hashlib.sha256(authorization[7:].encode()).hexdigest(), {'user_id': user['user_id'], 'revoked_at': now()})
    return {'ok': True}

@app.post('/api/v1/auth/password')
def change_password(payload: dict):
    username, old, new = payload.get('username',''), payload.get('old_password',''), payload.get('new_password','')
    if len(new) < 6: raise HTTPException(422, '新密码至少 6 位')
    user = next((u for u in store.list('user') if u['username'] == username), None)
    if not user or user['password_hash'] != password_hash(old): raise HTTPException(401, '原密码错误')
    user['password_hash'] = password_hash(new); store.put('user', user['user_id'], user)
    return {'ok': True}

@app.post('/api/v1/teacher/users', status_code=201)
def create_student(payload: TeacherUserPayload, authorization: str | None = Header(default=None)):
    actor = current_user(authorization, 'TEACHER,ADMIN')
    if actor['role'] != 'ADMIN' and payload.role != 'STUDENT':
        raise HTTPException(403, '非管理员只能创建学生账号')
    if any(u['username'] == payload.username for u in store.list('user')): raise HTTPException(409, '用户名已存在')
    if payload.role == 'STUDENT' and payload.class_name and not any(c['name'] == payload.class_name for c in class_roster()['items']):
        raise HTTPException(422, '请先在班级管理中创建班级')
    uid = str(uuid4()); user = {'user_id':uid, 'username':payload.username, 'display_name':payload.display_name or payload.username,
        'role':payload.role, 'class_name':payload.class_name if payload.role == 'STUDENT' else '', 'password_hash':password_hash(payload.password), 'created_at':now()}
    store.put('user', uid, user)
    return {k:user[k] for k in ('user_id','username','display_name','role','class_name')}

@app.get('/api/v1/teacher/users')
def list_students(authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    users = [{k:u[k] for k in ('user_id','username','display_name','role','class_name')} for u in store.list('user')]
    return {'items': users}


def class_roster():
    students = [u for u in store.list('user') if u.get('role') == 'STUDENT']
    names = {c['name'] for c in store.list('class')} | {u['class_name'] for u in students if u.get('class_name')}
    def public(u):
        return {k: u.get(k, '') for k in ('user_id', 'username', 'display_name', 'class_name')}
    return {'items': [{'name': name, 'difficulty_by_experience': (store.get('class', name) or {}).get('difficulty_by_experience', {'1':'EASY','1-3':'MEDIUM','3-5':'HARD','5-7':'HARD','7+':'HARD'}), 'students': [public(u) for u in students if u.get('class_name') == name]} for name in sorted(names)],
            'unassigned': [public(u) for u in students if not u.get('class_name')]}


@app.get('/api/v1/teacher/classes')
def list_classes(authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    return class_roster()


class ClassPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


@app.post('/api/v1/teacher/classes', status_code=201)
def create_class(payload: ClassPayload, authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    if any(c['name'] == payload.name for c in class_roster()['items']):
        raise HTTPException(409, '班级已存在')
    record = {'name': payload.name, 'created_at': now(), 'difficulty_by_experience': {'1':'EASY','1-3':'MEDIUM','3-5':'HARD','5-7':'HARD','7+':'HARD'}}
    store.put('class', payload.name, record)
    return record


class AssignClass(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    class_name: str = Field(max_length=100)

class ClassDifficultyPayload(BaseModel):
    difficulty_by_experience: dict[str, Literal['EASY','MEDIUM','HARD']]

@app.patch('/api/v1/teacher/classes/{name}/difficulty')
def update_class_difficulty(name: str, payload: ClassDifficultyPayload, authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    if set(payload.difficulty_by_experience) != {'1','1-3','3-5','5-7','7+'}:
        raise HTTPException(422, '请为所有工作年限设置难度')
    record = store.get('class', name)
    if not record: raise HTTPException(404, '班级不存在')
    record['difficulty_by_experience'] = payload.difficulty_by_experience; store.put('class', name, record)
    return record


@app.patch('/api/v1/teacher/users/{id}/class')
def assign_class(id: str, payload: AssignClass, authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    user = require('user', id)
    if user['role'] != 'STUDENT':
        raise HTTPException(422, '只能为学生分配班级')
    if payload.class_name and not any(c['name'] == payload.class_name for c in class_roster()['items']):
        raise HTTPException(422, '请先创建班级')
    # Preserve legacy classes represented only by students' class_name fields.
    for name in (user.get('class_name'), payload.class_name):
        if name and not store.get('class', name):
            store.put('class', name, {'name': name, 'created_at': now()})
    user['class_name'] = payload.class_name
    store.put('user', id, user)
    return {'user_id': id, 'class_name': payload.class_name}

@app.get('/api/v1/teacher/usage')
def usage_summary(user_id: str | None = None, audience: Literal['all', 'student', 'staff'] = 'all', authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    if settings.environment == 'production':
        import psycopg
        with psycopg.connect(settings.postgres_dsn) as db:
            db.execute('CREATE TABLE IF NOT EXISTS token_usage (id BIGSERIAL PRIMARY KEY,user_id TEXT NOT NULL,provider TEXT NOT NULL,prompt_tokens INTEGER NOT NULL,completion_tokens INTEGER NOT NULL,total_tokens INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT now())')
            rows = db.execute("SELECT user_id, (created_at AT TIME ZONE 'Asia/Shanghai')::date, sum(total_tokens),sum(prompt_tokens),sum(completion_tokens) FROM token_usage WHERE (%s::text IS NULL OR user_id=%s) GROUP BY user_id,(created_at AT TIME ZONE 'Asia/Shanghai')::date ORDER BY 2 DESC", (user_id,user_id)).fetchall()
    else:
        with sqlite3.connect(settings.data_dir / 'mianmian.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS token_usage (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,provider TEXT,prompt_tokens INTEGER,completion_tokens INTEGER,total_tokens INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            rows = db.execute("SELECT user_id, date(created_at,'+8 hours'), sum(total_tokens),sum(prompt_tokens),sum(completion_tokens) FROM token_usage WHERE (? IS NULL OR user_id=?) GROUP BY user_id,date(created_at,'+8 hours') ORDER BY 2 DESC", (user_id,user_id)).fetchall()
    users = store.list('user')
    students = [u for u in users if audience != 'staff' and u.get('role') == 'STUDENT' and (not user_id or u['user_id'] == user_id)]
    ids = {u['user_id'] for u in students}
    daily = [{'user_id':r[0],'date':str(r[1]),'tokens':int(r[2]),'prompt_tokens':int(r[3]),'completion_tokens':int(r[4])} for r in rows if r[0] in ids]
    totals = {uid: 0 for uid in ids}
    for item in daily: totals[item['user_id']] = totals.get(item['user_id'],0)+item['tokens']
    items = [{**{k: u.get(k, '') for k in ('user_id', 'username', 'display_name', 'class_name')}, 'tokens': totals[u['user_id']]} for u in students]
    staff = [u for u in users if audience != 'student' and u.get('role') in ('TEACHER','ADMIN') and (not user_id or u['user_id'] == user_id)]
    staff_totals = {u['user_id']: 0 for u in staff}
    for row in rows:
        if row[0] in staff_totals:
            staff_totals[row[0]] += int(row[2])
    staff_items = [{**{k: u.get(k, '') for k in ('user_id','username','display_name','role')}, 'tokens': staff_totals[u['user_id']]} for u in staff]
    items.sort(key=lambda u: (-u['tokens'], u['username']))
    staff_items.sort(key=lambda u: (-u['tokens'], u['username']))
    staff_daily = [{'user_id': r[0], 'date': str(r[1]), 'tokens': int(r[2]), 'prompt_tokens': int(r[3]),
                    'completion_tokens': int(r[4])} for r in rows if r[0] in staff_totals]
    return {'items': items, 'staff_items': staff_items, 'totals': totals, 'daily': daily,
            'staff_daily': staff_daily, 'timezone': 'Asia/Shanghai',
            'as_of_date': datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}


@app.exception_handler(ServiceError)
async def service_error(_, exc):
    return JSONResponse(status_code=502, content={'detail': str(exc)})


async def read_upload(file, allowed, max_bytes=MAX_UPLOAD):
    filename = Path((file.filename or '').replace('\\', '/')).name
    if Path(filename).suffix.lower() not in allowed:
        await file.close()
        raise HTTPException(415, '文件格式不支持，请按提示选择文件')
    try:
        content = await file.read(max_bytes + 1)
    finally:
        await file.close()
    if len(content) > max_bytes:
        raise HTTPException(413, f'文件不得超过 {max_bytes // (1024 * 1024)} MB')
    if not content:
        raise HTTPException(422, '文件不能为空')
    return content, filename


async def document_upload(file, resume=False):
    allowed = {'.pdf', '.docx'} if resume else {'.pdf', '.docx', '.md', '.markdown'}
    content, filename = await read_upload(file, allowed)
    try:
        text = await run_in_threadpool(extract_document_text, content, filename, resume)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return content, filename, text


@app.get('/api/health')
def health():
    return {'status': 'ok', 'service': 'mianmian-backend', 'storage': 'sqlite',
            'llm': settings.deepseek_model, 'asr': settings.asr_model, 'tts': settings.tts_model,
            'llm_configured': bool(settings.deepseek_api_key), 'audio_configured': bool(settings.siliconflow_api_key)}


@app.post('/api/v1/resumes', status_code=201)
async def upload_resume(file: UploadFile = File(...)):
    content, filename, text = await document_upload(file, resume=True)
    id = str(uuid4())
    path = save_upload(content, filename, 'resumes')
    record = {'resume_id': id, 'filename': filename, 'text': text, 'text_length': len(text), 'created_at': now()}
    store.put('resume', id, {**record, 'path': str(path)})
    return record


@app.get('/api/v1/resumes/{id}')
def get_resume(id: str):
    return {k:v for k,v in require('resume', id).items() if k != 'path'}


@app.post('/api/v1/teacher/question-bank/import', status_code=201)
async def import_questions(file: UploadFile = File(...), job_track: str = Form('AI 应用开发工程师', max_length=100), authorization: str | None = Header(default=None), stream: bool = False):
    current_user(authorization, 'TEACHER,ADMIN')
    job_track = job_track.strip()
    if not job_track:
        raise HTTPException(422, '请填写适用岗位')
    content, filename, text = await document_upload(file)
    if stream:
        return StreamingResponse(import_events(content, filename, text, job_track),
                                 media_type='application/x-ndjson',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
    try:
        questions = await deepseek_extract_questions(text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    id = str(uuid4())
    path = save_upload(content, filename, 'question-bank')
    record = {'import_id': id, 'filename': filename, 'job_track': job_track, 'questions': questions,
              'source_text': text, 'committed': False, 'created_at': now()}
    store.put('import', id, {**record, 'path': str(path)})
    return record


async def import_events(content, filename, source_text, job_track):
    queue = asyncio.Queue()

    async def progress(payload):
        await queue.put({'type': 'progress', **payload})

    async def process():
        try:
            questions = await deepseek_extract_questions(source_text, progress=progress)
            id = str(uuid4())
            record = {'import_id': id, 'filename': filename, 'job_track': job_track,
                      'questions': questions, 'source_text': source_text,
                      'committed': False, 'created_at': now()}
            path = await run_in_threadpool(save_upload, content, filename, 'question-bank')
            await run_in_threadpool(store.put, 'import', id, {**record, 'path': str(path)})
            await queue.put({'type': 'complete', 'draft': record})
        except (ServiceError, ValueError) as exc:
            await queue.put({'type': 'error', 'message': str(exc)})
        except Exception:
            logging.exception('Question import failed')
            await queue.put({'type': 'error', 'message': '导入失败，资料未入库，请重试'})

    task = asyncio.create_task(process())
    try:
        yield json.dumps({'type': 'progress', 'completed': 0, 'total': 0, 'questions': 0}) + '\n'
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=10)
            except TimeoutError:
                yield json.dumps({'type': 'heartbeat'}) + '\n'
                continue
            yield json.dumps(event, ensure_ascii=False) + '\n'
            if event['type'] in {'complete', 'error'}:
                break
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

@app.post('/api/v1/student/knowledge/import', status_code=201)
async def import_student_knowledge(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    user = current_user(authorization, 'STUDENT')
    content, filename, text = await document_upload(file)
    usage_context = usage_user.set(user['user_id'])
    try:
        questions = await deepseek_extract_questions(text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        usage_user.reset(usage_context)
    return {'knowledge_id': str(uuid4()), 'filename': filename, 'text': text, 'questions': questions}


class CommitQuestions(BaseModel):
    questions: list[ExtractedQuestion] = Field(min_length=1, max_length=500)


@app.post('/api/v1/teacher/question-bank/import/{id}/commit')
def commit_questions(id: str, payload: CommitQuestions, authorization: str | None = Header(default=None)):
    current_user(authorization, 'TEACHER,ADMIN')
    require('import', id)
    result = store.commit_import(id, [q.model_dump() for q in payload.questions])
    return {k:v for k,v in result.items() if k not in {'path', 'source_text'}}


@app.get('/api/v1/teacher/question-bank')
def list_questions(authorization: str | None = Header(default=None), page: int | None = Query(default=None, ge=1), job_track: str | None = None):
    current_user(authorization, 'TEACHER,ADMIN')
    items = store.list('question')
    tracks = sorted({question_track(q) for q in items})
    if job_track is not None:
        items = [q for q in items if question_track(q) == job_track]
    total = len(items)
    if page is not None:
        return {'items': items[(page - 1) * 10:page * 10], 'total': total, 'page': page, 'page_size': 10, 'tracks': tracks}
    return {'items': items, 'total': total, 'tracks': tracks}


def question_track(question):
    return (question.get('job_track') or '').strip() or '通用岗位'


@app.get('/api/v1/student/question-tracks')
def student_question_tracks(authorization: str | None = Header(default=None)):
    current_user(authorization)
    tracks = {}
    for q in store.list('question'):
        track = question_track(q)
        tracks[track] = tracks.get(track, 0) + 1
    return {'items': [{'job_track': name, 'question_count': count} for name, count in sorted(tracks.items())]}


def choose_track_questions(tracks, count, difficulty=None):
    groups = {track: [] for track in dict.fromkeys(tracks)}
    for q in store.list('question'):
        if question_track(q) in groups:
            groups[question_track(q)].append(q)
    if any(not questions for questions in groups.values()):
        raise HTTPException(422, '所选岗位已没有题目，请刷新题库选项')
    levels = {'EASY': 0, 'MEDIUM': 1, 'HARD': 2}
    def distance(question):
        level = (question.get('difficulty') or '').upper()
        if level == difficulty:
            return 0
        if level not in levels:
            return 0.5
        return abs(levels[level] - levels.get(difficulty, 1))
    for questions in groups.values():
        random.SystemRandom().shuffle(questions)
        if difficulty:
            # pop() selects the nearest difficulty first; never discard an otherwise valid track.
            questions.sort(key=distance, reverse=True)
    chosen = []
    # Round-robin sampling covers every selected track before taking additional questions.
    while len(chosen) < max(len(groups), min(20, count * 2)) and any(groups.values()):
        for questions in groups.values():
            if questions and len(chosen) < max(len(groups), min(20, count * 2)):
                q = questions.pop()
                chosen.append({'id': q['id'], 'job_track': question_track(q), 'question': q['question'][:1300],
                               'answer': q.get('answer', '')[:1300], 'category': q.get('category', '综合'), 'difficulty': q.get('difficulty'),
                               'reference_is_excerpt': len(q['question']) > 1300 or len(q.get('answer', '')) > 1300})
    return chosen


class UpdateAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    answer: str = Field(max_length=12000)
    job_track: str | None = Field(default=None, min_length=1, max_length=100)

@app.post('/api/v1/teacher/question-bank/{id}/suggest-answer')
async def suggest_question_answer(id: str, authorization: str | None = Header(default=None)):
    actor = current_user(authorization, 'TEACHER,ADMIN')
    question = require('question', id)
    answer = await generate_reference_answer(question['question'], question_track(question), actor['user_id'])
    return {'question_id': id, 'answer': answer}


@app.patch('/api/v1/teacher/question-bank/{id}/answer')
def update_question_answer(id: str, payload: UpdateAnswer, authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(401, '请先登录')
    user = current_user(authorization, 'TEACHER,ADMIN')
    question = store.update_answer(id, payload.answer.strip(), now(), user['user_id'], payload.job_track)
    if question is None:
        raise HTTPException(404, '题目不存在')
    return question


@app.post('/api/v1/audio/asr')
async def asr(file: UploadFile = File(...)):
    mime = file.content_type or 'application/octet-stream'
    content, filename = await read_upload(file, {'.wav', '.mp3', '.m4a', '.webm', '.ogg', '.mp4'}, MAX_AUDIO_UPLOAD)
    return {'text': await siliconflow_asr(content, filename, mime)}


@app.post('/api/v1/audio/tts')
async def tts(text: str = Form(..., min_length=1, max_length=2000), voice: str = Form('', max_length=100), tone: str = Form('professional', max_length=30)):
    return Response(await siliconflow_tts(text, voice=voice, tone=tone), media_type='audio/mpeg', headers={'Cache-Control': 'no-store'})


class InterviewCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    job_track: str = Field(default='AI 应用开发工程师', min_length=1, max_length=100)
    interviewer_style: Literal['HARDCORE', 'GUIDING', 'BUSINESS', 'CREATIVE', 'ALL_ROUND'] = 'HARDCORE'
    resume_id: str | None = None
    resume_text: str = Field(default='', max_length=80000)
    target_question_count: int = Field(default=5, ge=1, le=10)
    question_ids: list[str] = Field(default_factory=list, max_length=20)
    knowledge_tracks: list[str] = Field(default_factory=list, max_length=10)
    experience_years: Literal['1','1-3','3-5','5-7','7+'] = '1-3'
    interviewer_voice: str = Field(default='', max_length=100)
    interviewer_tone: Literal['professional','friendly','pressing','concise'] = 'professional'
    question_expression: int = Field(default=3, ge=1, le=5, strict=True)
    user_id: str | None = None
    temporary_questions: list[ExtractedQuestion] = Field(default_factory=list, max_length=150)


@app.post('/api/v1/interviews', status_code=201)
async def create_interview(payload: InterviewCreate, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    resume_text = require('resume', payload.resume_id)['text'] if payload.resume_id else payload.resume_text
    questions = [require('question', id) for id in dict.fromkeys(payload.question_ids) if not id.startswith('temp-')]
    defaults = {'1':'EASY','1-3':'MEDIUM','3-5':'HARD','5-7':'HARD','7+':'HARD'}
    class_record = store.get('class', user.get('class_name')) if user.get('class_name') else None
    difficulty = (class_record or {}).get('difficulty_by_experience', defaults).get(payload.experience_years, defaults[payload.experience_years])
    if payload.knowledge_tracks:
        questions.extend(choose_track_questions(payload.knowledge_tracks, payload.target_question_count, difficulty))
        questions = list({q['id']: q for q in questions}.values())
    questions.extend([q.model_dump() | {'id': f'temp-{i}'} for i, q in enumerate(payload.temporary_questions)])
    if sum(len(json.dumps(q, ensure_ascii=False)) for q in questions) > 60000:
        raise HTTPException(422, '选择的题目内容过多，请减少题目数量')
    state = {'job_track': payload.job_track, 'style': payload.interviewer_style, 'experience_years': payload.experience_years, 'difficulty': difficulty, 'interviewer_voice': payload.interviewer_voice, 'interviewer_tone': payload.interviewer_tone, 'resume_text': resume_text, 'user_id': user['user_id'],
             'question_expression': payload.question_expression,
             'question_bank': questions, 'turn': 0, 'answer': '', 'history': [],
             'target_question_count': payload.target_question_count}
    result = await interview_graph.ainvoke(state)
    id = str(uuid4())
    session = {**state, 'session_id': id, 'knowledge_tracks': list(dict.fromkeys(payload.knowledge_tracks)), 'resume_id': payload.resume_id, 'question': result['next_question'],
               'status': 'IN_PROGRESS', 'started_at': now()}
    store.put('session', id, session)
    return public_session(session)


def public_session(s):
    return {**{k:s[k] for k in ['session_id', 'question', 'turn', 'target_question_count', 'status', 'started_at', 'job_track', 'style', 'resume_id']}, 'interviewer_voice': s.get('interviewer_voice', ''), 'interviewer_tone': s.get('interviewer_tone', 'professional'),
            'question_expression': s.get('question_expression', 3),
            'history': [{k: t[k] for k in ('turn', 'question', 'answer')} for t in s['history']],
            'question_ids': [q['id'] for q in s['question_bank']]}


@app.get('/api/v1/student/interviews')
def student_interviews(day: date | None = None, authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(401, '请先登录')
    user = current_user(authorization)
    items = []
    dates = {}
    for session in store.list('session'):
        if session.get('user_id') != user['user_id']:
            continue
        timestamp = datetime.fromisoformat(session['started_at'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        session_day = timestamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
        dates[session_day] = dates.get(session_day, 0) + 1
        if day and session_day != day.isoformat():
            continue
        items.append({**{key: session[key] for key in ('session_id', 'job_track', 'style', 'started_at', 'status', 'turn', 'target_question_count')},
                      'ended_at': session.get('ended_at'), 'date': session_day,
                      'has_report': session['status'] == 'COMPLETED' and bool(session['history'])})
    items.sort(key=lambda item: (datetime.fromisoformat(item['started_at'].replace('Z', '+00:00')).timestamp(), item['session_id']), reverse=True)
    return {'items': items, 'dates': dates, 'total': len(items), 'timezone': 'Asia/Shanghai'}


def accessible_session(id, authorization):
    session = require('session', id)
    owner = session.get('user_id')
    if owner and owner != 'development':
        if not authorization:
            raise HTTPException(401, '请先登录')
        if current_user(authorization)['user_id'] != owner:
            raise HTTPException(404, '记录不存在')
    return session


def signed_in_student(authorization):
    if not authorization:
        raise HTTPException(401, '请先登录')
    return current_user(authorization, 'STUDENT')


def public_bookmark(bookmark):
    data = {key: bookmark.get(key) for key in (
        'id', 'session_id', 'turn', 'question', 'job_track', 'interview_started_at',
        'created_at', 'review', 'review_error')}
    data['status'] = 'ready' if bookmark.get('review') else (
        'generating' if bookmark.get('review_lease_until', '') > now() else 'pending')
    return data


class BookmarkCreate(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    turn: int = Field(ge=0, le=100)


@app.get('/api/v1/student/bookmarks')
def list_bookmarks(page: int = Query(default=1, ge=1), authorization: str | None = Header(default=None)):
    user = signed_in_student(authorization)
    result = store.student_bookmarks(user['user_id'], page=page)
    result['items'] = [public_bookmark(item) for item in result['items']]
    return result


@app.post('/api/v1/student/bookmarks')
def create_bookmark(payload: BookmarkCreate, authorization: str | None = Header(default=None)):
    user = signed_in_student(authorization)
    session = require('session', payload.session_id)
    if session.get('user_id') != user['user_id']:
        raise HTTPException(404, '记录不存在')
    if session['status'] != 'COMPLETED':
        raise HTTPException(409, '请在面试结束后的报告中标记题目')
    turn = next((t for t in session['history'] if t['turn'] == payload.turn), None)
    if turn is None:
        raise HTTPException(404, '题目不存在')
    id = hashlib.sha256(json.dumps([user['user_id'], payload.session_id, payload.turn]).encode()).hexdigest()
    initial = {'id': id, 'user_id': user['user_id'], 'session_id': payload.session_id,
               'turn': turn['turn'], 'question': turn['question'], 'job_track': session.get('job_track', ''),
               'interview_started_at': session.get('started_at'), 'created_at': now(), 'active': True, 'review': None}
    def mark(record):
        if not record['active']:
            record['created_at'] = now()
        record['active'] = True
    return public_bookmark(store.mutate('bookmark', id, mark, initial))


def owned_bookmark(id, user):
    bookmark = require('bookmark', id)
    if bookmark['user_id'] != user['user_id'] or not bookmark['active']:
        raise HTTPException(404, '标记题目不存在')
    return bookmark


class RetryAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_CHARACTERS)
    request_id: UUID
    previous_attempt_id: UUID | None


def practice_source(bookmark, user):
    session = require('session', bookmark['session_id'])
    if session.get('user_id') != user['user_id']:
        raise HTTPException(404, '记录不存在')
    turn = next((t for t in session['history'] if t['turn'] == bookmark['turn']), None)
    if session['status'] != 'COMPLETED' or not turn:
        raise HTTPException(409, '原面试报告暂不可用')
    return session, turn


def practice_baseline(practice, session, turn):
    attempts = practice.get('attempts', [])
    if attempts:
        last = attempts[-1]
        return {'attempt_id': last['id'], 'label': f"第 {last['number']} 次重答", 'answer': last['answer'],
                'feedback': last['comparison'], 'created_at': last['created_at']}
    return {'attempt_id': None, 'label': '原面试回答', 'answer': turn['answer'], 'feedback': turn['feedback'],
            'created_at': session.get('ended_at') or session['started_at']}


@app.get('/api/v1/student/bookmarks/{id}/practice')
def get_practice(id: str, authorization: str | None = Header(default=None)):
    user = signed_in_student(authorization)
    bookmark = owned_bookmark(id, user)
    session, turn = practice_source(bookmark, user)
    practice = store.get('practice', id) or {'attempts': []}
    return {'bookmark': public_bookmark(bookmark), 'previous': practice_baseline(practice, session, turn),
            'attempts': list(reversed(practice['attempts'][-20:])), 'total': len(practice['attempts']),
            'in_progress': practice.get('lease_until', '') > now()}


@app.post('/api/v1/student/bookmarks/{id}/practice')
async def submit_practice(id: str, payload: RetryAnswer, authorization: str | None = Header(default=None)):
    user = signed_in_student(authorization)
    bookmark = owned_bookmark(id, user)
    session, turn = practice_source(bookmark, user)
    request_id = str(payload.request_id)
    baseline_id = str(payload.previous_attempt_id) if payload.previous_attempt_id else None
    lease = str(uuid4())
    def claim(record):
        cached = next((a for a in record['attempts'] if a['id'] == request_id), None)
        if cached:
            if cached['answer'] != payload.answer or cached['previous']['attempt_id'] != baseline_id:
                raise HTTPException(409, '此提交编号已用于其他回答，请重新提交')
            return
        if record.get('lease_until', '') > now():
            raise HTTPException(409, '这道题的上一份回答正在评估，请稍后刷新')
        if practice_baseline(record, session, turn)['attempt_id'] != baseline_id:
            raise HTTPException(409, '其他页面已完成新的重答，请刷新对比基准后再提交')
        record.update(lease=lease, lease_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
    practice = store.mutate('practice', id, claim, {'user_id': user['user_id'], 'bookmark_id': id, 'attempts': []})
    cached = next((a for a in practice['attempts'] if a['id'] == request_id), None)
    if cached:
        return cached
    previous = practice_baseline(practice, session, turn)
    try:
        comparison = await asyncio.wait_for(compare_retry(session, turn['question'], previous, payload.answer,
                            bookmark.get('review') or session.get('question_bank', [])), timeout=240)
        # Store a compact baseline; do not recursively copy earlier comparisons into each attempt.
        result = {'id': request_id, 'number': len(practice['attempts']) + 1, 'answer': payload.answer,
                  'previous': {k: previous[k] for k in ('attempt_id', 'label', 'answer', 'created_at')},
                  'comparison': comparison, 'created_at': now()}
        def complete(record):
            if record.get('lease') != lease:
                raise HTTPException(409, '本次评估已过期，请刷新后重试')
            record['attempts'].append(result)
            record.update(lease=None, lease_until='')
        store.mutate('practice', id, complete)
        return result
    except BaseException as exc:
        def release(record):
            if record.get('lease') == lease:
                record.update(lease=None, lease_until='')
        store.mutate('practice', id, release)
        if isinstance(exc, TimeoutError):
            raise ServiceError('重答评估超时，回答尚未保存，请重试') from exc
        raise


@app.delete('/api/v1/student/bookmarks/{id}')
def remove_bookmark(id: str, authorization: str | None = Header(default=None)):
    user = signed_in_student(authorization)
    bookmark = require('bookmark', id)
    if bookmark['user_id'] != user['user_id']:
        raise HTTPException(404, '标记题目不存在')
    # Keep the generated review cached so marking again does not charge for another answer.
    store.mutate('bookmark', id, lambda record: record.update(active=False))
    return {'ok': True}


@app.post('/api/v1/student/bookmarks/{id}/review')
async def generate_bookmark_review(id: str, authorization: str | None = Header(default=None)):
    user = signed_in_student(authorization)
    owned_bookmark(id, user)
    lease = str(uuid4())
    def claim(record):
        if not record['active']:
            raise HTTPException(404, '标记题目不存在')
        if not record.get('review') and record.get('review_lease_until', '') <= now():
            record.update(review_lease=lease, review_lease_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), review_error=None)
    bookmark = store.mutate('bookmark', id, claim)
    if bookmark.get('review'):
        return public_bookmark(bookmark)
    if bookmark.get('review_lease') != lease:
        return JSONResponse(public_bookmark(bookmark), status_code=202)
    try:
        session = require('session', bookmark['session_id'])
        turn = next(t for t in session['history'] if t['turn'] == bookmark['turn'])
        # Bound the call below the lease duration, so a replacement worker cannot overlap it.
        review = await asyncio.wait_for(review_question(session, turn), timeout=240)
        def complete(record):
            if record.get('review_lease') == lease:
                record.update(review=review, review_error=None, review_lease_until='', review_lease=None)
        return public_bookmark(store.mutate('bookmark', id, complete))
    except BaseException as exc:
        def release(record):
            if record.get('review_lease') == lease:
                record.update(review_lease_until='', review_lease=None, review_error='复习内容暂未生成，请重试。')
        store.mutate('bookmark', id, release)
        if isinstance(exc, TimeoutError):
            raise ServiceError('复习内容生成超时，请重试') from exc
        raise


@app.get('/api/v1/interviews/{id}')
def get_interview(id: str, authorization: str | None = Header(default=None)):
    return public_session(accessible_session(id, authorization))


@app.post('/api/v1/interviews/{id}/finish')
async def finish_interview(id: str, authorization: str | None = Header(default=None)):
    async with locks.setdefault(id, asyncio.Lock()):
        session = accessible_session(id, authorization)
        session.update(status='COMPLETED', ended_at=now())
        store.put('session', id, session)
    return public_session(session)


@app.get('/api/v1/interviews/{id}/report')
def report(id: str, authorization: str | None = Header(default=None)):
    s = accessible_session(id, authorization)
    if s['status'] != 'COMPLETED':
        raise HTTPException(409, '面试结束后可查看诊断报告')
    if not s['history']:
        raise HTTPException(409, '至少完成一次回答后才能查看报告')
    bookmarks = store.student_bookmarks(s.get('user_id', ''), session_id=id)['items']
    marked = {item['turn']: item['id'] for item in bookmarks}
    turns = [{**t, 'bookmark_id': marked.get(t['turn'])} for t in s['history']]
    dimensions = {key: round(sum(t['dimensions'][key] for t in turns) / len(turns)) for key in turns[0]['dimensions']}
    return {'session_id': id, 'overall_score': round(sum(t['score'] for t in turns)/len(turns)),
            'dimensions': dimensions, 'summary': f'已完成 {len(turns)} 轮回答，以下为 DeepSeek 逐轮评估汇总。',
            'recommendations': [t['feedback'] for t in sorted(turns, key=lambda t: t['score'])[:3]], 'turns': turns,
            'interview_summary': s.get('interview_summary')}


@app.post('/api/v1/interviews/{id}/summary')
async def create_interview_summary(id: str, authorization: str | None = Header(default=None)):
    async with locks.setdefault(id, asyncio.Lock()):
        session = accessible_session(id, authorization)
        if session['status'] != 'COMPLETED' or not session['history']:
            raise HTTPException(409, '至少完成一次回答并结束面试后才能生成总结')
        if not session.get('interview_summary'):
            summary = await summarize_interview(session)
            session['interview_summary'] = summary
            store.put('session', id, session)
        return session['interview_summary']


def evaluation_source(id, authorization):
    user = signed_in_student(authorization)
    session = require('session', id)
    if session.get('user_id') != user['user_id']:
        raise HTTPException(404, '记录不存在')
    if session['status'] != 'COMPLETED' or not session.get('history'):
        raise HTTPException(409, '至少完成一次回答并结束面试后才能生成评价表')
    return session, user


def sheet_status(record):
    if not record or record.get('version') != evaluation_sheet.VERSION:
        return {'status': 'pending'}
    if record.get('pdf'):
        return {'status': 'ready', 'generated_at': record['generated_at'],
                **evaluation_sheet.conclusion(record['assessment'])}
    if record.get('lease_until', '') > now():
        return {'status': 'generating'}
    return {'status': 'failed' if record.get('error') else 'pending', 'error': record.get('error')}


@app.get('/api/v1/interviews/{id}/evaluation-sheet')
def get_evaluation_sheet(id: str, authorization: str | None = Header(default=None)):
    evaluation_source(id, authorization)
    return sheet_status(store.get('evaluation_sheet', id))


@app.post('/api/v1/interviews/{id}/evaluation-sheet')
async def create_evaluation_sheet(id: str, authorization: str | None = Header(default=None)):
    session, user = evaluation_source(id, authorization)
    lease = uuid4().hex

    def claim(record):
        if record.get('version') != evaluation_sheet.VERSION:
            record.clear()
            record.update(version=evaluation_sheet.VERSION, user_id=user['user_id'])
        if record.get('pdf') or record.get('lease_until', '') > now():
            return
        record.update(lease=lease, lease_until=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(), error=None)

    record = store.mutate('evaluation_sheet', id, claim, {})
    if record.get('pdf'):
        return sheet_status(record)
    if record.get('lease') != lease:
        return JSONResponse(sheet_status(record), status_code=202)
    try:
        assessment = record.get('assessment')
        if not assessment:
            assessment = await asyncio.wait_for(evaluation_sheet.assess(session), timeout=240)
            def save_assessment(row):
                if row.get('lease') != lease:
                    raise HTTPException(409, '评价表生成状态已更新，请刷新重试')
                row['assessment'] = assessment
            store.mutate('evaluation_sheet', id, save_assessment)
        details = record.get('details') or evaluation_sheet.metadata(session, user)
        pdf = await run_in_threadpool(evaluation_sheet.render_pdf, assessment, details)
        def complete(row):
            if row.get('lease') != lease:
                raise HTTPException(409, '评价表生成状态已更新，请刷新重试')
            row.update(pdf=base64.b64encode(pdf).decode('ascii'), details=details,
                       generated_at=now(), lease=None, lease_until='', error=None)
        return sheet_status(store.mutate('evaluation_sheet', id, complete))
    except BaseException as exc:
        message = str(exc) if isinstance(exc, ServiceError) else '评价表暂未生成，请重试。'
        def release(row):
            if row.get('lease') == lease:
                row.update(lease=None, lease_until='', error=message)
        store.mutate('evaluation_sheet', id, release)
        if isinstance(exc, TimeoutError):
            raise ServiceError('评价表生成超时，请重试') from exc
        if isinstance(exc, Exception) and not isinstance(exc, (HTTPException, ServiceError)):
            logging.exception('Evaluation PDF generation failed for session %s', id)
            raise ServiceError(message) from exc
        raise


@app.get('/api/v1/interviews/{id}/evaluation-sheet.pdf')
def download_evaluation_sheet(id: str, authorization: str | None = Header(default=None)):
    evaluation_source(id, authorization)
    record = store.get('evaluation_sheet', id)
    if sheet_status(record)['status'] != 'ready':
        raise HTTPException(409, '评价表尚未生成，请在诊断页等待生成或重试')
    filename = quote(f"面试评价表_{record['details']['name']}_{record['details']['date']}.pdf", safe='')
    return Response(base64.b64decode(record['pdf']), media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="interview-evaluation.pdf"; filename*=UTF-8\'\'{filename}',
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


class Answer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    event: Literal['ANSWER']
    text: str = Field(min_length=1, max_length=MAX_ANSWER_CHARACTERS)
    turn: int = Field(ge=0)


@app.websocket('/ws/interviews/{id}')
async def interview_socket(ws: WebSocket, id: str):
    await ws.accept()
    session = store.get('session', id)
    if session and session.get('user_id') not in (None, 'development'):
        try:
            accessible_session(id, 'Bearer ' + (ws.query_params.get('token') or ''))
        except HTTPException:
            await ws.close(code=1008)
            return
    if not session:
        await ws.send_json({'type': 'ERROR', 'message': '面试不存在'})
        await ws.close(code=1008)
        return
    await ws.send_json({'type': 'SESSION_STATE', 'payload': public_session(session)})
    try:
        while True:
            try:
                message = await ws.receive_text()
                if session.get('user_id') not in (None, 'development'):
                    try:
                        accessible_session(id, 'Bearer ' + (ws.query_params.get('token') or ''))
                    except HTTPException:
                        await ws.close(code=1008)
                        return
                event = Answer.model_validate_json(message)
            except (ValidationError, ValueError):
                await ws.send_json({'type': 'ERROR', 'message': f'回答格式不正确或超过 {MAX_ANSWER_CHARACTERS} 字符'})
                continue
            async with locks.setdefault(id, asyncio.Lock()):
                session = store.get('session', id)
                if session['status'] != 'IN_PROGRESS' or event.turn != session['turn']:
                    await ws.send_json({'type': 'ERROR', 'message': '轮次已变更或面试已结束，请重新连接'})
                    await ws.send_json({'type': 'SESSION_STATE', 'payload': public_session(session)})
                    continue
                await ws.send_json({'type': 'PROCESSING'})
                try:
                    state = {k:session[k] for k in ['job_track', 'style', 'resume_text', 'question_bank', 'history', 'turn', 'question', 'target_question_count', 'interviewer_voice', 'interviewer_tone'] if k in session}
                    state['user_id'] = session.get('user_id')
                    state['question_expression'] = session.get('question_expression', 3)
                    state.update({k: session[k] for k in ('experience_years', 'difficulty') if k in session})
                    result = await interview_graph.ainvoke({**state, 'answer': event.text})
                except ServiceError as exc:
                    await ws.send_json({'type': 'ERROR', 'message': str(exc)})
                    continue
                turn = {'turn':session['turn']+1, 'question':session['question'], 'answer':event.text,
                        'score':result['score'], 'dimensions':result['dimensions'], 'feedback':result['feedback']}
                session['history'].append(turn)
                session['turn'] += 1
                session['question'] = result['next_question']
                if session['turn'] >= session['target_question_count']:
                    session.update(status='COMPLETED', ended_at=now())
                store.put('session', id, session)
                await ws.send_json({'type':'ANSWER_ACCEPTED', 'payload':{'turn': turn['turn']}})
                await ws.send_json({'type':'SESSION_STATE', 'payload':public_session(session)})
    except WebSocketDisconnect:
        return
