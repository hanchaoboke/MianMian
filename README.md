# MianMian · 面面俱道 AI 面试训练场

Vue 3 + FastAPI + LangGraph，面向 AI 应用开发方向的简历驱动模拟面试，生产部署使用 PostgreSQL。真实调用 `backend/.env` 配置的 DeepSeek 和硅基流动模型，不使用模拟评分或失败时伪造的模型回答。

## 启动后端

```bash
conda activate MianMian_py312
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --reload --port 8010
```

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

本机学员端：<http://127.0.0.1:5173/>；教师端：<http://127.0.0.1:5173/teacher>；API 文档：<http://127.0.0.1:8010/docs>。前端监听 `0.0.0.0:5173`，允许局域网访问；后端保持监听 `127.0.0.1:8010`，由 Vite 将 `/api` 和 `/ws` 代理到后端。

同一局域网的其他电脑请访问 `http://服务器局域网IP:5173/`（学生端）或 `http://服务器局域网IP:5173/teacher/login`（教师端）。这里的 IP 是运行项目的电脑在该网络中的地址，不能填写 `127.0.0.1`、`localhost` 或 `0.0.0.0`。前后端必须同时运行，客户端无需直接连接后端 8010 端口，也无需设置 `VITE_API_BASE`。多网卡时选择与客户端所在网络对应的 IP；如果仍无法连接，检查服务器防火墙是否允许 TCP 5173，以及路由器是否启用了访客网络或客户端隔离。

局域网 HTTP 地址可用于页面和接口联调，但浏览器麦克风录音需要 HTTPS；正式部署应使用 HTTPS 反向代理提供前端构建产物，并转发 `/api` 和 `/ws` 到后端，不能将 Vite 开发服务器作为生产服务。

项目提供 Caddy HTTPS 网关：安装 Caddy 后执行 `python deploy/https.py start --host 服务器IP`，通过 `https://服务器IP:8443/` 访问。使用内网 IP 时，每台客户端首次需要信任项目 CA；供学生安装的公开证书和 [安装步骤](doc/HTTPS证书安装说明.md)统一放在 `doc` 目录。

后端自动读取 `backend/.env`，与命令工作目录无关；配置项见 `backend/.env.example`。密钥只在后端使用，不进入前端构建。修改配置后重启后端。`TTS_VOICE` 可覆盖默认音色，音色需与模型匹配。

## 使用流程

前端采用统一自适应容器：主内容在侧栏之外的可用区域居中，最大阅读宽度 1680px，标题和卡片间距随窗口调整。960px 及以下导航移至顶部，学生日历可展开收起；650px 及以下表单和报告切为单列。登录页独立居中，训练设置和结束面试弹窗按实际可视高度滚动。

布局验证样例仅用于开发：启动前端后打开 `/tests/responsive.html#/`，可切换到 `#/teacher`、`#/teacher/classes`、`#/teacher/accounts`、`#/teacher/usage`、`#/report/visual`、`#/interview/visual`、`#/login`、`#/teacher/login`。样例使用独立模拟数据，不调用后端或模型，也不包含在生产构建入口中。已检查 320、390、768、960、1024、1366、1920、2560、3440、3840px 宽度，以及手机横屏弹窗、长班级名、长题目和展开账单。

学生和教师登录后，页面右上角提供“退出登录”，分别回到学生/教师登录页；退出会清理浏览器登录信息和历史缓存，并撤销当前登录凭证。面试室也提供退出入口，重新登录后可从历史记录继续未结束的面试，未发送回答不保存。

面试诊断在“逐题复盘”之前展示“面试总结”：由 DeepSeek 综合整场问答生成整体结论、优点、重点提升方向和练习建议。首次查看时生成并保存，后续查看复用，不重复消耗 Token；失败时保留逐题报告并支持重试。该模型调用同样计入学生 Token 账单。浏览器标签标题统一为“MianMian · AI 面试训练场”。

学生日历下方提供“标记题目回顾”（`/bookmarks`）。在报告的逐题复盘中点击“标记题目”，先保存题目，再由 DeepSeek 整理考查知识点与口语化标准回答。回顾页按最近标记排序，每页 10 题，支持取消标记、失败重试和返回原报告。答案为练习示范，涉及项目时应结合真实经历调整。

标记只允许当前登录学生操作自己的已完成面试；同一场面试同一轮自动去重，跨设备共享保存结果。首次生成计入该学生 Token 账单，后续读取或取消后再标记复用缓存。模型失败不会丢失题目，生成中的跨页面请求会读取进度；数据库原子更新与生成租约避免并发重复调用，服务中断留下的租约在 5 分钟后可重试。生产环境标记记录和内容保存在 PostgreSQL，无需手工建表。开发视觉样例增加 `#/bookmarks`，相关回归测试为 `backend/tests/test_bookmarks.py`、`frontend/tests/Bookmarks.spec.js`。

教师侧“班级管理”独立列出班级和成员，支持创建空班级、查看未分班学生及调整归属；原有学生的 `class_name` 会自动出现在列表。账号仍由管理员分配，创建学生账号时从已建班级中选择，并可填写用于首页称呼和账单展示的姓名。

“学生 Token 消耗”按姓名、用户名、班级展示所有学生（包含零消耗账号），点击姓名展开北京时间每日输入、输出及总 Token。DeepSeek 返回的实际 `usage` 用于记账，包含面试和学生临时知识库解析；校验失败后的模型重试也计入实际消耗。未归属到学生或过去没有记录的消耗不会估算补记，语音服务不纳入此 Token 表。生产环境记账与查询均使用规范化后的 PostgreSQL 连接地址。

题目随导入时的“适用岗位”入库，教师可按岗位筛选并编辑题目的岗位和答案。学生在训练设置中多选岗位题库，后端从各选中岗位均衡抽取本场参考题（最多 20 道，长参考资料使用节选，原题库保留全文），避免把整个题库一次塞入提示词；临时知识库仍可独立选题。

管理功能回归测试：`python -m pytest backend/tests -q`；前端：`npx vitest run tests/Interview.spec.js tests/StudentHistory.spec.js tests/TeacherManagement.spec.js`。可通过 `MIANMIAN_TEST_POSTGRES_DSN` 指向测试 PostgreSQL 启用真实数据库集成测试，测试自动创建并清理独立 schema，不改业务表。

学生首页以面试记录替代旧回答区和快捷入口，按开始时间倒序展示，点击日期或“查看面试诊断”打开对应报告；进行中的记录可继续面试。左侧日历按北京时间标记有练习的日期，点击筛选当天记录，可切换月份或恢复全部记录。历史接口只返回当前登录账号的记录；旧数据中没有账号归属的记录不会自动分配给任何学生。

面试风格提供深挖型、引导型、业务型、天马行空型和全能型。天马行空型提出 AI 相关的非常规、跨领域问题，关注能力边界与推理；全能型以较高难度结合业务价值、技术实现与工程取舍。风格同时传入 LangGraph 的出题与评估上下文。

“简历与训练设置”中的“提问表达”使用五档滑杆，从非常口语化到严谨专业，默认自然专业，附同一主题的表达示例。`question_expression` 随面试保存并用于首题、后续追问和题库改写，只调整措辞，不改变工作年限与班级决定的难度或评分标准。旧会话默认第三档。

学生首页和语音交互测试：在 `frontend` 下运行 `npx vitest run tests/StudentHistory.spec.js tests/Interview.spec.js`。

题库导入支持实时处理进度：格式清晰的连续编号题目按原文解析，保留完整参考答案；非结构化资料分批调用模型，不设置每批题目截断上限。文档声明题数时会检查实际数量。教师和管理员均可确认入库，提交期间显示等待进度，事务成功后显示完成数量；失败保留校对内容，重复提交同一草稿不会重复新增。

前端流式消息解析测试：在 `frontend` 下运行 `node --test tests/import.test.js`。

面试页使用独立布局，支持问题朗读、文字回答、每次最多 10 分钟录音、ASR 转写后确认发送、录音回听和转写失败重试。录音到时自动停止并转写，也可提前停止；浏览器请求 64 kbps 音频编码，音频上传最多 25 MB，每轮回答最多 6000 字符，超出时保留全文供精简。ASR 默认等待 300 秒，可在后端通过 `ASR_TIMEOUT_SECONDS` 调整。麦克风需要浏览器授权；部署时需 HTTPS，本机 localhost/127.0.0.1 可直接测试。面试过程中仅显示问答内容，后端内部评估用于后续提问；结束后在“面试诊断”中查看所有轮次的评分与反馈。新问题限制为单个核心问题、最多 240 字符。

前端录音及回答限制统一定义在 `frontend/src/interviewLimits.js`，后端回答与音频文件上限位于 `backend/app/services.py`，调整时需同步。文档上传仍为 10 MB。若使用反向代理，音频路由请求体应允许至少 26 MB（含 multipart 开销），读取超时应大于 ASR 等待时间（建议 360 秒）。[硅基流动官方音频接口规格](https://docs.siliconflow.cn/docs/api/audio-transcriptions-post)允许最长 1 小时、最大 50 MB，当前应用设置在其范围内。

语音交互组件测试：在 `frontend` 下运行 `npx vitest run tests/Interview.spec.js`，使用模拟浏览器音频设备，覆盖权限拒绝、取消授权、转写失败重试、长转写保留及离开时释放设备。

1. 教师上传 Markdown / PDF / DOCX，DeepSeek 分段提取题目、原文答案和出处，教师可编辑、删除，确认后入库。无答案的题目保留为空，不编造标准答案。
2. 学员在训练设置上传 PDF / DOCX 简历，检查提取文本，选择岗位、风格、轮数及题库参考题，也可以手动填写项目经历。
3. LangGraph 结合简历和选定题库提问，每次回答后先评估，再追问或换题。最后一轮仅评估。
4. 支持文字输入、录音后硅基流动 ASR 转写，以及硅基流动 TTS 合成考官问题。转写后由学生确认发送。
5. 报告包含逐题反馈、四维平均分和改进建议。刷新或重连恢复最近一次会话，未发送的文字不跨刷新保存。

## 文档与数据

面试诊断页加载后，会自动按 `AI应用开发工程师面试评价表.docx` 的第一页生成可下载 PDF。
按八个维度重新归纳本场问答证据，评分为 1-5；未验证填 N，有 N 时不输出最终加权总分。
四项关键维度为代码工程、大模型应用、效果评估、安全治理，均须达到 3 分才可推荐。
表格加权分与诊断页逐题平均分口径不同；未知职级和人工复核信息不会编造。
生成调用产生的 DeepSeek Token 归当前学生，同一场面试成功生成后复用数据库缓存。
页面关闭或失败后可再次打开诊断页重试；只有所属学生登录后可以生成或下载。
部署依赖已经包含 `reportlab`，模板和字体随 `backend/assets/evaluation` 打包，无需安装 Word。
更新模板的方法见该目录 README；原始 DOCX 保持不变。

- 单文件最多 10 MB，提取文本最多 80000 字符，PDF 最多 200 页。支持可提取文本的 PDF；扫描件、加密 PDF 会提示先 OCR 或解密。DOCX 提取段落和表格文字。
- 上传文件保存在 `backend/uploads`，可通过 `DATA_DIR` 修改。生产环境业务记录（包括标记题目）存储在 PostgreSQL；开发及测试支持 SQLite，数据目录被 Git 忽略。
- 上传简历时在本地解析；面试时将简历文本及选定题目发送至 DeepSeek。教师导入文档时将提取文本发送至 DeepSeek。录音经后端发送至硅基流动，后端不保存录音。
- 确认入库是原子事务，重复确认同一导入不重复新增。模型或网络失败会显示错误，面试轮次不前进，可重试。

## 已实现接口

- `POST /api/v1/interviews`：创建面试会话
- `GET /api/v1/student/interviews?day=YYYY-MM-DD`：当前账号的面试记录及日历日期统计（日期筛选可选）
- `WS /ws/interviews/{session_id}`：提交回答、返回 LangGraph 评分与下一题
- `GET /api/v1/interviews/{session_id}/report`：获取复盘报告
- `POST /api/v1/interviews/{session_id}/evaluation-sheet`：自动生成或读取缓存的评价表；生成中返回 202
- `GET /api/v1/interviews/{session_id}/evaluation-sheet`：读取生成状态
- `GET /api/v1/interviews/{session_id}/evaluation-sheet.pdf`：下载填写后的第一页 PDF，需 Bearer 登录凭证
- `GET /api/v1/student/bookmarks?page=1`：当前学生的标记题目，每页 10 道
- `POST /api/v1/student/bookmarks`：标记已完成报告中的题目，传入 `session_id`、`turn`
- `POST /api/v1/student/bookmarks/{id}/review`：生成或读取缓存的知识点及口语化回答；生成中返回 202
- `DELETE /api/v1/student/bookmarks/{id}`：取消标记
- `POST /api/v1/resumes`：上传并解析简历
- `POST /api/v1/teacher/question-bank/import`：提取题库草稿
- `POST /api/v1/teacher/question-bank/import/{id}/commit`：确认入库
- `GET /api/v1/teacher/question-bank`：题库列表
- `POST /api/v1/audio/asr` / `tts`：语音转写、合成
- `GET /api/health`：健康检查

## 当前范围与验证

这一版覆盖账号分配与登录、班级管理、学生 Token 账单、简历上传、题库整理、模型提问评分、语音输入输出、报告和标记题目回顾。尚未接入 pgvector 检索、Redis、VAD 实时语音和流式 TTS。

生产部署设置 `ENVIRONMENT=production` 并配置 `DATABASE_URL`、`JWT_SECRET` 及管理员信息。开发模式部分既有接口允许无登录调试，不能以开发模式对公网提供服务。现有面试会话使用进程内锁，后端仍按单进程运行；标记功能的原子写入与生成租约由数据库保护。

```bash
conda activate MianMian_py312
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
cd frontend
npm run build
```

自动测试使用临时存储和模拟模型响应，不消耗实际模型额度，覆盖格式与限制、题库确认、原文校验、面试流程、重连与失败恢复、报告和音频接口。实际接口需使用自己的 `.env` 联调。

`docker-compose.yml` 定义后端、PostgreSQL/pgvector 和 Redis 服务；启动它不会自动迁移已有 SQLite 数据。
