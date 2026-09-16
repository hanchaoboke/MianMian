from typing import Annotated, TypedDict
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from .services import deepseek_json


class InterviewState(TypedDict, total=False):
    user_id: str
    job_track: str
    style: str
    experience_years: str
    difficulty: str
    question_expression: int
    resume_text: str
    question_bank: list[dict]
    history: list[dict]
    turn: int
    question: str
    answer: str
    target_question_count: int
    score: int
    dimensions: dict
    feedback: str
    next_question: str


class Dimensions(BaseModel):
    engineering_depth: int = Field(ge=0, le=100)
    system_design: int = Field(ge=0, le=100)
    star_structure: int = Field(ge=0, le=100)
    stress_handling: int = Field(ge=0, le=100)


class Evaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    dimensions: Dimensions
    feedback: str = Field(min_length=1, max_length=3000)


class NextQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=240)


SummaryText = Annotated[str, Field(min_length=1, max_length=600)]


class InterviewSummary(BaseModel):
    conclusion: str = Field(min_length=1, max_length=1000)
    strengths: list[SummaryText] = Field(max_length=3)
    priorities: list[SummaryText] = Field(min_length=1, max_length=3)
    next_steps: list[SummaryText] = Field(min_length=1, max_length=3)


class QuestionReview(BaseModel):
    knowledge_points: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=1, max_length=6)
    spoken_answer: str = Field(min_length=1, max_length=3500)


class ReferenceAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)


class RetryComparison(BaseModel):
    conclusion: str = Field(min_length=1, max_length=1000)
    improved: list[SummaryText] = Field(max_length=4)
    needs_improvement: list[SummaryText] = Field(max_length=4)
    next_practice: list[SummaryText] = Field(min_length=1, max_length=3)


async def compare_retry(session, question, previous, answer, reference):
    result = await deepseek_json(
        '你是 AI 应用开发面试教练，比较同一道题的上一次回答与本次重答。'
        'conclusion 概括本次相对上次的变化。improved 只列有实际证据的改善，'
        'needs_improvement 列出仍缺失、技术不准确或比上次退步的地方；两者每项需对照具体表述，'
        '不要空泛表扬，不要按字数判断。没有明确改善时 improved 为空；没有明显问题时也允许缺点为空。'
        'next_practice 给出下一次练习的具体动作和验收方式。首次重答的基准为原面试回答，'
        '之后基准为最近一次成功提交的重答，以输入 previous 为准。'
        '参考答案和旧反馈仅供参考，不是唯一正确答案；必要时纠正旧反馈的错误。'
        '不编造项目经历或效果数字；只评价回答内容，不能推断语速、声音、情绪或人格。',
        {'user_id': session['user_id'], 'job_track': session.get('job_track'),
         'experience_years': session.get('experience_years'), 'difficulty': session.get('difficulty'),
         'question': question, 'previous': previous, 'new_answer': answer, 'reference': reference}, RetryComparison)
    return result.model_dump()


async def generate_reference_answer(question, job_track, user_id):
    result = await deepseek_json(
        '你是面试题库教研老师。为下面这道中文面试题生成一份准确、可用于教师校对的参考答案。'
        '回答要覆盖题目考查的核心概念、实现思路、关键取舍和验证方式，适合 AI 应用开发岗位面试。'
        '使用自然中文，可直接粘贴到题库；不要编造特定公司的事实、学生经历或无法验证的效果数字。'
        '题目没有唯一答案时说明前提和合理方案，不要写“标准答案只有一种”。',
        {'user_id': user_id, 'job_track': job_track, 'question': question}, ReferenceAnswer)
    return result.answer


async def review_question(session, turn):
    result = await deepseek_json(
        '你是 AI 应用开发职业培训教练，为学生标记的面试题生成中文复习卡。'
        'knowledge_points 列出这道题真正考查的 2 到 6 个具体知识点，每项可以简要说明，不写空泛能力标签。'
        'spoken_answer 给出适合在面试中自然说出口的完整参考示范回答，建议 300 到 600 字。'
        '直接回答题目，先讲结论，再用连贯短段落说明原理、实现、取舍或验证方法；不用 Markdown 标题、'
        '表格和代码块，不堆砌术语，不重复学生的错误答案。根据题目选择内容，不能硬套所有步骤。'
        '仅将 question_bank 中与本题相关的资料作为参考，节选和学生回答不代表事实或唯一正确答案。'
        '问题含特定项目经历时，用“如果由我来设计”“可以这样验证”等条件式表达，'
        '不要伪造学生做过的项目、个人贡献或效果数字；必要的示例假设要说清楚。'
        '开放题说明前提、边界和合理取舍，不声称有唯一答案；未知事实如实说明。',
        {'user_id': session['user_id'], 'job_track': session.get('job_track'),
         'question': turn['question'], 'student_answer': turn['answer'], 'feedback': turn['feedback'],
         'question_bank': session.get('question_bank', [])}, QuestionReview)
    return result.model_dump()


async def summarize_interview(session):
    context = {key: session.get(key) for key in ('user_id', 'job_track', 'style', 'history')}
    result = await deepseek_json(
        '你是 AI 应用开发职业培训教练。根据这场已结束面试的全部问答与逐轮评估，用中文做跨题总结。'
        'conclusion 用一段话概括本次表现与当前能力；strengths 提炼已有优点，priorities 按重要性列出'
        '接下来需要重点提高的方面，next_steps 给出具体可执行的练习方法和验收标准。'
        '优点和待提升项必须有回答内容依据，可说明相关轮次，但不要简单复制逐题反馈。'
        '没有证据支持的优点不要编造，允许 strengths 为空；只评价本次表现，不推断人格或就业结果。'
        '只有文字和转写内容，没有录音指标，不推断语速、音色、情绪。表达温和直接，避免空泛鼓励。',
        context, InterviewSummary)
    return result.model_dump()


async def evaluate(state: InterviewState):
    result = await deepseek_json(
        '你是 AI 应用开发面试官。根据当前问题、候选人回答、简历及教师参考资料公正评分。'
        '不要仅按字数或关键词评分，不要把参考答案当作唯一正确答案。无参考答案时用专业知识评估。'
        '如提供 difficulty 和 experience_years，按目标难度与经验阶段评估；题库材料难度仅供参考。'
        'question_expression 仅表示考官提问的措辞正式程度，不影响候选人的评分标准或目标难度。'
        '标记 reference_is_excerpt 的资料仅为原题或答案节选，不可因节选遗漏而判候选人错误。'
        '四项维度为工程深度、系统设计、STAR 表达、临场应变。反馈指出具体证据和可执行改进；'
        'CREATIVE 天马行空型重视前提辨析、能力边界、推理依据和创造力，允许多种合理思路；'
        'ALL_ROUND 全能型以较高要求评估业务价值与技术取舍是否贯通、落地约束是否充分。'
        '文字回答的临场应变仅评估应答内容，不能推断声音或情绪。', state, Evaluation)
    return result.model_dump()


QUESTION_EXPRESSIONS = {
    1: '非常口语化：像面对面聊天一样，用日常词汇和短句提问，少用书面句式；必要术语可用通俗说法解释，但不能透露解题思路或答案。',
    2: '轻松自然：用自然对话的语序提问，保留必要技术术语，避免冗长定义、官腔和过度铺垫。',
    3: '自然专业：使用清晰自然的面试口吻，兼顾易懂表达和准确技术术语，不刻意口语化或书面化。',
    4: '专业表达：使用规范技术术语和明确约束，表述精确、逻辑紧凑，减少日常口语。',
    5: '严谨专业：采用正式技术面试的措辞，术语准确、边界清晰、句式严谨；不堆砌术语、不无故增加阅读负担。',
}


async def ask_next(state: InterviewState):
    if state.get('answer') and state['turn'] + 1 >= state['target_question_count']:
        return {'next_question': ''}
    context = dict(state)
    context['question_expression'] = state.get('question_expression', 3)
    expression = QUESTION_EXPRESSIONS.get(context['question_expression'], QUESTION_EXPRESSIONS[3])
    if state.get('answer'):
        context['turn'] = state['turn'] + 1
        context['history'] = state['history'] + [{'question': state['question'], 'answer': state['answer'], 'feedback': state['feedback']}]
    for key in ('feedback', 'score', 'dimensions'):
        context.pop(key, None)
    context['history'] = [{key: turn[key] for key in ('question', 'answer')} for turn in context.get('history', [])]
    result = await deepseek_json(
        '你是职业培训模拟面试官。结合目标岗位、简历真实项目和教师题库提出一个中文面试问题。'
        '除 CREATIVE 外第一轮优先简历项目，其后根据回答追问或换题。避免重复历史问题，不编造简历经历。'
        '每轮只问一个核心问题，建议80到160字，最多240字符。直接提问，不评价上一轮表现，'
        '如提供 difficulty 和 experience_years，应据此调整问题深度；参考题来自相近难度时应改写到目标水平。'
        '不说答对或答错、不表扬、不批评、不提供评分、答案或改进建议，不罗列多个步骤或子问题。'
        'HARDCORE 深挖工程细节，GUIDING 循序引导，BUSINESS 关注业务价值。'
        'CREATIVE 是天马行空型：提出 AI 相关的不常见、跨领域或反直觉问题，考查边界意识、'
        '概率推理和创造力，例如讨论大模型能否预测彩票开奖，但不要反复使用同一个例子，'
        '不把随机事件可预测当事实，也不提供投注建议；可脱离简历选题，始终与 AI 能力有关。'
        'ALL_ROUND 是全能型：难度偏高，将业务目标、价值与落地约束和技术实现深挖结合在同一核心问题中，'
        '围绕取舍追问，跨轮覆盖架构、评测、成本、可靠性及业务收益，避免只问概念。'
        '不要在问题中泄露参考答案。'
        '以下表达要求适用于本轮问题和后续追问，也适用于题库原题的改写；仅改变措辞，不改变由工作年限、'
        'difficulty 和面试风格决定的考查深度，不因口语化而降低难度或暗示答案，不因专业化而增加子问题。'
        + expression,
        context, NextQuestion)
    if result.question.strip() == state.get('question', '').strip():
        from .services import ServiceError
        raise ServiceError('考官生成了重复问题，请重新发送回答以重试')
    return {'next_question': result.question}


builder = StateGraph(InterviewState)
builder.add_node('evaluate', evaluate)
builder.add_node('ask_next', ask_next)
builder.set_conditional_entry_point(lambda state: 'evaluate' if state.get('answer') else 'ask_next')
builder.add_edge('evaluate', 'ask_next')
builder.add_edge('ask_next', END)
interview_graph = builder.compile()
