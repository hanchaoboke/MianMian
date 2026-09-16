"""Evidence-based assessment and deterministic filling of the supplied first-page form."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import threading
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from .services import ServiceError, deepseek_json

VERSION = 1
ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'evaluation'
RUBRIC = (
    ('business', '业务理解', 10, False),
    ('code', '代码工程', 20, True),
    ('llm', '大模型应用', 15, True),
    ('retrieval', '知识检索', 15, False),
    ('evaluation', '效果评估', 15, True),
    ('operations', '上线运维', 10, False),
    ('security', '安全治理', 10, True),
    ('collaboration', '协作学习', 5, False),
)
OBSERVATIONS = (
    '拆解需求与验收指标；判断是否需要 AI，权衡收益、成本与限制。',
    '编码、API 与数据处理；能调试，处理异步、异常、测试与可维护性。',
    '模型与提示设计、结构化输出；工具调用及 Agent 流程的约束与容错。',
    'RAG 数据清洗、切分、检索与重排；引用溯源、更新和检索失败定位。',
    '构建代表性测试集与基线；分析错误，用实验验证质量改进。',
    '部署、监控与回滚；处理限流、超时、重试，优化时延与调用成本。',
    '识别提示注入与数据泄露；控制权限、敏感数据及工具执行风险。',
    '讲清个人贡献与方案取舍；主动澄清问题，吸收反馈并复盘改进。',
)
_render_lock = threading.Lock()
ShortText = Annotated[str, Field(min_length=1, max_length=42)]


class Evidence(BaseModel):
    turn: int = Field(ge=1, le=100, strict=True)
    quote: str = Field(min_length=3, max_length=160)


class Criterion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    score: Annotated[int, Field(ge=1, le=5, strict=True)] | None
    evidence: str = Field(min_length=1, max_length=55)
    sources: list[Evidence] = Field(max_length=2)


class Criteria(BaseModel):
    model_config = ConfigDict(extra='forbid')
    business: Criterion
    code: Criterion
    llm: Criterion
    retrieval: Criterion
    evaluation: Criterion
    operations: Criterion
    security: Criterion
    collaboration: Criterion


class SheetAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    criteria: Criteria
    project: ShortText
    strengths: ShortText
    risks: ShortText
    follow_up: ShortText


async def assess(session):
    result = await deepseek_json(
        '根据本次模拟面试的真实问答，填写 AI 应用开发工程师面试评价表。不要把原报告的四项百分制'
        '评分转换成这张表的八项评分，要逐项寻找对应证据。每项 score 为 1-5 的整数或 null（N）。'
        '1=基础或核心任务明显错误；2=只能解释部分概念、方案不完整；3=常规任务方案可行，'
        '能解释关键选择、异常与验证；4=处理复杂边界并有证据比较方案；5=可核验复杂成果与可复用方法。'
        '每个非空评分必须在 sources 引用 1-2 条真实学生回答原文（quote 必须逐字匹配 answer，'
        'turn 必须是实际轮次），evidence 写简短具体的事实、问题或待验证事项，最多 55 字。'
        '未提问或证据不足填 null，不能按 0 分处理，不能从题目、简历、参考答案推测学生能力。'
        '代码工程必须有实际代码或具体编码调试细节，只有框架名或架构讨论不足以验证；'
        '协作学习只评价学生已说明的贡献、取舍与复盘，不能推断人格。不能声称做过现场编码或听到声音。'
        '四项关键维度是代码工程、大模型应用、效果评估、安全治理。'
        'project 简述本场明确提及的项目和本人职责，未说明则写“本场未说明项目及本人职责”。'
        'strengths、risks、follow_up 各最多 42 字，简明具体、对应本场证据；'
        '无优势证据就明确说明。follow_up 写最重要的补面问题或练习建议。'
        '不推断真实职级、录用结果，不编造签名、日期和成果。返回 JSON，不含 Markdown。',
        {'user_id': session['user_id'], 'job_track': session.get('job_track'),
         'experience_years': session.get('experience_years'), 'difficulty': session.get('difficulty'),
         'rubric': [{'key': k, 'name': n, 'weight': w, 'critical': c, 'observation': observation}
                    for (k, n, w, c), observation in zip(RUBRIC, OBSERVATIONS)],
         'history': [{k: turn.get(k) for k in ('turn', 'question', 'answer', 'feedback')}
                     for turn in session['history']]}, SheetAssessment)
    data = result.model_dump()
    answers = {t['turn']: t['answer'] for t in session['history']}
    for row in data['criteria'].values():
        if row['score'] is not None and (not row['sources'] or any(
            len(source['quote'].strip()) < 3 or source['quote'] not in answers.get(source['turn'], '')
            for source in row['sources']
        )):
            # Invalid citations cannot be presented as verified evidence or a scored skill.
            row.update(score=None, evidence='评分依据未能对应本场回答，需补充验证。', sources=[])
    return data


def conclusion(data):
    rows = data['criteria']
    verified = all(rows[key]['score'] is not None for key, *_ in RUBRIC)
    critical_scores = [rows[key]['score'] for key, _, _, critical in RUBRIC if critical]
    critical_pass = False if any(s is not None and s < 3 for s in critical_scores) else (
        None if any(s is None for s in critical_scores) else True)
    total = round(sum(rows[key]['score'] * weight / 5 for key, _, weight, _ in RUBRIC), 1) if verified else None
    recommendation = '待补面' if not verified else (
        '不推荐' if not critical_pass or total < 60 else '优先推荐' if total >= 80 else '推荐')
    return {'total': total, 'critical_pass': critical_pass, 'verified': verified, 'recommendation': recommendation}


def metadata(session, user):
    date, duration = '未记录', '未记录'
    try:
        start = datetime.fromisoformat(session['started_at'])
        if start.tzinfo:
            date = start.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
            end = datetime.fromisoformat(session['ended_at'])
            if end.tzinfo and end >= start:
                duration = f'{(end-start).total_seconds()/60:.1f}'
    except (KeyError, ValueError, TypeError):
        pass
    return {'name': user.get('display_name') or user.get('username') or '未设置姓名',
            'date': date, 'duration': duration, 'rounds': len(session['history']),
            'target_level': session.get('target_level') or '未设置', 'matched_level': '待教师复核'}


def _text(canvas, value, x, top, width, height, size=9, minimum=7.5, center=False):
    """Wrap within measured template slots; fail rather than silently crop evidence."""
    text = ' '.join(str(value).split())
    while size >= minimum:
        lines, line = [], ''
        for ch in text:
            if line and pdfmetrics.stringWidth(line + ch, 'EvaluationText', size) > width:
                lines.append(line); line = ''
            line += ch
        if line:
            lines.append(line)
        leading = size * 1.18
        if len(lines) * leading <= height:
            canvas.setFont('EvaluationText', size)
            y = 792 - top - (height-len(lines)*leading)/2 - size
            for line in lines:
                if center:
                    canvas.drawCentredString(x+width/2, y, line)
                else:
                    canvas.drawString(x, y, line)
                y -= leading
            return
        size -= .25
    raise ServiceError('评价表内容超出单页容量，请稍后重试或联系教师检查姓名及评价文本。')


def render_pdf(data, details):
    with _render_lock:
        if 'EvaluationText' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('EvaluationText', str(ASSETS / 'NotoSansSC-Regular.ttf')))
        output = BytesIO()
        canvas = Canvas(output, pagesize=(612, 792), invariant=1)
        canvas.setFillColorRGB(0.1, 0.1, 0.1)
        _text(canvas, 'MianMian 模拟面试训练评价 · 根据本场回答生成，待教师复核', 45.45, 75, 521, 14)
        _text(canvas, f"候选人：{details['name']}", 45.45, 95, 175, 22, size=9, minimum=6)
        _text(canvas, f"目标职级：{details['target_level']}", 225, 95, 165, 22)
        _text(canvas, f"面试轮次：{details['rounds']} 轮问答", 397, 95, 170, 22)
        _text(canvas, '面试官：MianMian AI', 45.45, 118, 175, 16)
        _text(canvas, f"面试日期：{details['date']}", 225, 118, 165, 16)
        _text(canvas, f"时长：{details['duration']} 分钟", 397, 118, 170, 16)
        _text(canvas, f"代表项目及本人职责：{data['project']}", 45.45, 139, 521, 20, size=8.5)
        for i, (key, _, _, critical) in enumerate(RUBRIC):
            row, top = data['criteria'][key], 203.35+i*37
            _text(canvas, 'N' if row['score'] is None else row['score'], 350, top+4, 30, 29, size=11, center=True)
            turns = sorted({s['turn'] for s in row['sources']}) if row['score'] is not None else []
            evidence = (f"第{'、'.join(map(str, turns))}轮：" if turns else '') + row['evidence']
            _text(canvas, evidence, 389, top+3, 173, 31, size=8, minimum=7.5)
            if critical:
                _text(canvas, '*', 48, top+10, 8, 16, size=9)
        result = conclusion(data)
        total = f"{result['total']:.1f} / 100" if result['total'] is not None else '暂不计算（存在 N）'
        critical = '是' if result['critical_pass'] else '待验证' if result['critical_pass'] is None else '否'
        _text(canvas, f"加权总分：{total}", 45.45, 552, 197, 17)
        _text(canvas, f'关键维度均 ≥ 3：{critical}', 246, 552, 172, 17)
        _text(canvas, f"全部已验证：{'是' if result['verified'] else '否'}", 427, 552, 139, 17)
        _text(canvas, f"建议：{result['recommendation']}（训练参考）", 45.45, 574, 275, 17)
        _text(canvas, f"匹配职级：{details['matched_level']}", 326, 574, 240, 17)
        for label, key, top in [('主要优势及依据', 'strengths', 596), ('主要短板或风险', 'risks', 619),
                                ('补面内容或录用建议', 'follow_up', 642)]:
            _text(canvas, f'{label}：{data[key]}', 45.45, top, 521, 19, size=8.5)
        _text(canvas, '面试官签名：AI 自动生成，无人工签名', 45.45, 665, 262, 18, size=8.5)
        _text(canvas, '复核人或复核日期：待教师复核', 314, 665, 252, 18, size=8.5)
        _text(canvas, '注：加权分依据八维度 1-5 分计算，与诊断页逐题平均分采用不同口径。', 45.45, 702, 521, 16, size=8)
        _text(canvas, 'MianMian · 面试评价表（第一页） · 1 / 1', 340, 761, 226, 16, size=8, center=True)
        canvas.showPage(); canvas.save()
        writer = PdfWriter()
        writer.add_page(PdfReader(ASSETS / 'first-page.pdf').pages[0])
        writer.pages[0].merge_page(PdfReader(BytesIO(output.getvalue())).pages[0])
        writer.add_metadata({'/Title': 'AI应用开发工程师面试评价表', '/Author': 'MianMian', '/Subject': '模拟面试训练评价'})
        final = BytesIO(); writer.write(final)
        return final.getvalue()
