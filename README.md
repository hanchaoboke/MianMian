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

诊断页只保留一个主标题，返回与 PDF 下载合并在报告工具栏。逐题复盘支持题目跳转，宽屏左右对照回答与反馈，窄屏上下阅读；超过 360 字的回答可以展开全文。反馈按原有小标题、编号、换行排版，旧版连写的维度反馈也会分段，保持原文且不重新调用模型。格式化使用文本节点，反馈中的 HTML 不会被执行。

学生日历下方提供“标记题目回顾”（`/bookmarks`）。在报告的逐题复盘中点击“标记题目”，先保存题目，再由 DeepSeek 整理考查知识点与口语化标准回答。回顾页按最近标记排序，每页 10 题，支持取消标记、失败重试和返回原报告。答案为练习示范，涉及项目时应结合真实经历调整。

标记只允许当前登录学生操作自己的已完成面试；同一场面试同一轮自动去重，跨设备共享保存结果。首次生成计入该学生 Token 账单，后续读取或取消后再标记复用缓存。模型失败不会丢失题目，生成中的跨页面请求会读取进度；数据库原子更新与生成租约避免并发重复调用，服务中断留下的租约在 5 分钟后可重试。生产环境标记记录和内容保存在 PostgreSQL，无需手工建表。开发视觉样例增加 `#/bookmarks`，相关回归测试为 `backend/tests/test_bookmarks.py`、`frontend/tests/Bookmarks.spec.js`。

教师侧“班级管理”独立列出班级和成员，支持创建空班级、查看未分班学生及调整归属；原有学生的 `class_name` 会自动出现在列表。账号仍由管理员分配，创建学生账号时从已建班级中选择，并可填写用于首页称呼和账单展示的姓名。

教师侧新增“学生面试报告”（`/teacher/reports`）：按姓名、用户名和班级筛选已结束且有回答的面试，查看综合得分、维度、面试总结与逐题问答。教师和管理员可查看学生报告；学生端原有的本人报告权限保持独立。教师首次生成缺失的总结时，Token 归当前教师，成功后与学生端共用缓存。

报告每道题支持“加入题库”：DeepSeek 保留原考点与难度，将口语化问题改写为可独立使用的专业表达，教师可校对题目、分类、岗位、难度及选填参考答案，再确认入库。原题出处与来源轮次保留，学生回答不会直接作为参考答案入库。改写调用归当前教师计费，成功草稿持久缓存，同一面试同一轮原子去重；失败支持重试。已在回收箱的来源题目提示前往恢复。

题库以“在用题目 / 回收箱”切换，支持移入后撤销、从回收箱恢复，以及确认后永久删除。回收题目不会出现在学生岗位选项或新面试抽题中，也不能通过旧题目 ID 开启新面试。已有面试保存的题目快照和报告不受影响；旧题库数据默认在用。无需新增数据库表。相关测试见 `backend/tests/test_teacher_reports.py`、`frontend/tests/TeacherReports.spec.js`。

面试官左侧改为静态 M 身份标识；问题下方保留独立朗读按钮，支持暂停、继续、重播和播放时间。同一道题复用已合成语音，切题或开始录音时清理播放状态。

“学生 Token 消耗”按姓名、用户名、班级展示所有学生（包含零消耗账号），点击姓名展开北京时间每日输入、输出及总 Token。DeepSeek 返回的实际 `usage` 用于记账，包含面试和学生临时知识库解析；校验失败后的模型重试也计入实际消耗。未归属到学生或过去没有记录的消耗不会估算补记，语音服务不纳入此 Token 表。生产环境记账与查询均使用规范化后的 PostgreSQL 连接地址。

题目随导入时的“适用岗位”入库，教师可按岗位筛选并编辑题目的岗位和答案。学生在训练设置中多选岗位题库，后端从各选中岗位均衡抽取本场参考题（最多 20 道，长参考资料使用节选，原题库保留全文），避免把整个题库一次塞入提示词；临时知识库仍可独立选题。

管理功能回归测试：`python -m pytest backend/tests -q`；前端：`npx vitest run tests/Interview.spec.js tests/StudentHistory.spec.js tests/TeacherManagement.spec.js`。可通过 `MIANMIAN_TEST_POSTGRES_DSN` 指向测试 PostgreSQL 启用真实数据库集成测试，测试自动创建并清理独立 schema，不改业务表。

学生首页以面试记录替代旧回答区和快捷入口，按开始时间倒序展示，点击日期或“查看面试诊断”打开对应报告；进行中的记录可继续面试。左侧日历按北京时间标记有练习的日期，点击筛选当天记录，可切换月份或恢复全部记录。历史接口只返回当前登录账号的记录；旧数据中没有账号归属的记录不会自动分配给任何学生。

面试风格提供深挖型、引导型、业务型、天马行空型和全能型。天马行空型提出 AI 相关的非常规、跨领域问题，关注能力边界与推理；全能型以较高难度结合业务价值、技术实现与工程取舍。风格同时传入 LangGraph 的出题与评估上下文。

“简历与训练设置”中的“提问表达”使用五档滑杆，从非常口语化到严谨专业，默认自然专业，附同一主题的表达示例。`question_expression` 随面试保存并用于首题、后续追问和题库改写，只调整措辞，不改变工作年限与班级决定的难度或评分标准。旧会话默认第三档。

学生入口现为“面试与训练设置”，在目标岗位下选择“简历经历”或“企业业务”。简历经历沿用简历/项目经历流程；企业业务无需简历，填写至少 10 字的业务需求即可开始，交付约束与验收标准选填。切换模式保留当前页面内各自填写的内容，创建面试时只发送当前模式的材料。设置弹窗内部分区滚动，底部操作固定，参考资料与语音表达默认收起。

企业业务模式对应 `interview_mode=BUSINESS_SCENARIO`，`business_scenario` 包含 `requirement`（10-4000 字）、`constraints`、`success_criteria`（各最多 2000 字）；旧客户端和旧会话默认 `RESUME`。后端在企业业务模式下忽略简历 ID 和简历文本，并将业务题设保存到会话。首题直接进入业务场景，后续按回答追问需求、实现、成本、风险与验收；题设同样用于复盘总结、评价表和报告选题入库。原“业务型”仍是独立的提问风格，可以与任一模式组合。

企业业务报告保留原有四维数据结构，将 `star_structure` 展示为“方案表达”，关注目标、实施行动和验证方法；提示词明确不能因没有简历或过往交付经历而扣分，也不能将模拟方案当作真实成果。面试室与报告均可展开原始业务题设。新增回归测试为 `backend/tests/test_business_interview.py`，前端场景补充于 `frontend/tests/StudentHistory.spec.js`。

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

教师端的“评价表配置”（`/teacher/evaluation`）支持岗位通用模板及班级专属模板。
填写岗位后先匹配已有模板；新岗位调用 DeepSeek 生成 4-8 项专业评价条目，教师可修改名称（最多 12 字）、观察要点（最多 52 字）、权重、顺序及关键项，并填写训练重点。只有点击“保存并应用”后才生效；权重须合计 100%。切换岗位或班级时保留本页各自草稿。模板保存采用版本检查，避免多人编辑互相覆盖。

学生面试诊断自动按“面试开始时的班级 + 岗位”匹配班级专属模板，其次匹配岗位通用模板。
没有配置时，AI 应用开发岗位使用原八维度默认标准，其他岗位使用通用能力标准。
新面试保存班级快照，转班不改变旧面试归属；无班级快照的历史面试使用当前班级。
评价逐项依据本场回答，评分为 1-5；引用必须匹配真实学生回答，证据不足填 N，有 N 时不输出加权总分。
关键项低于 3 分时训练建议为“不推荐”，不代表真实录用决定。表格分数与诊断页逐题平均分口径不同。

PDF 使用固定单页 A4 版式、受限条目数量与字数、测量换行，完整保留评价要点和证据；不会分页或截断文字。
教师可下载未保存草稿的 PDF 预览，预览使用明确标注的占位内容，不调用模型。
生成条目的 Token 归教师，填写学生评价的 Token 归学生。同一内容复用数据库缓存；模板内容变化后旧 PDF 失效，下次打开诊断重新生成。
模型或排版失败可重试；成功的评估会保留，单纯 PDF 失败无需重复调用模型。只有所属学生登录后可以生成或下载其评价表。
部署使用 `reportlab`、`pypdf` 和随 `backend/assets/evaluation` 打包的中文字体，无需 Word；原始 DOCX 和旧背景 PDF 保留不变。

- 单文件最多 10 MB，提取文本最多 80000 字符，PDF 最多 200 页。支持可提取文本的 PDF；扫描件、加密 PDF 会提示先 OCR 或解密。DOCX 提取段落和表格文字。
- 上传文件保存在 `backend/uploads`，可通过 `DATA_DIR` 修改。生产环境业务记录（包括标记题目）存储在 PostgreSQL；开发及测试支持 SQLite，数据目录被 Git 忽略。
- 上传简历时在本地解析；面试时将简历文本及选定题目发送至 DeepSeek。教师导入文档时将提取文本发送至 DeepSeek。录音经后端发送至硅基流动，后端不保存录音。
- 确认入库是原子事务，重复确认同一导入不重复新增。模型或网络失败会显示错误，面试轮次不前进，可重试。

## 已实现接口

- `POST /api/v1/interviews`：创建面试会话
- `GET /api/v1/student/interviews?day=YYYY-MM-DD`：当前账号的面试记录及日历日期统计（日期筛选可选）
- `WS /ws/interviews/{session_id}`：提交回答、返回 LangGraph 评分与下一题
- `GET /api/v1/interviews/{session_id}/report`：获取复盘报告
- `GET /api/v1/teacher/evaluation-templates`：已保存的岗位/班级模板及班级选项
- `GET /api/v1/teacher/evaluation-templates/resolve?job_track=…&class_name=…`：匹配班级、岗位或默认模板
- `POST /api/v1/teacher/evaluation-templates/suggest`：按岗位、班级与训练重点生成建议条目
- `PUT /api/v1/teacher/evaluation-templates`：校验并保存模板，携带 `revision` 防止覆盖新版本
- `POST /api/v1/teacher/evaluation-templates/preview.pdf`：预览当前草稿的单页 PDF，不调用模型
- `POST /api/v1/interviews/{session_id}/evaluation-sheet`：自动生成或读取缓存的评价表；生成中返回 202
- `GET /api/v1/interviews/{session_id}/evaluation-sheet`：读取生成状态
- `GET /api/v1/interviews/{session_id}/evaluation-sheet.pdf`：下载填写后的单页 A4 PDF，需 Bearer 登录凭证
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

### SQLite → PostgreSQL 完整迁移

提供离线迁移工具 `backend/scripts/migrate_sqlite_to_postgres.py`。先停止全部后端写入，备份 SQLite（使用 SQLite backup API）、整个上传目录、后端 `.env` 及目标 PostgreSQL。工具只允许向空的 `records` / `token_usage` 表导入，不覆盖已有业务记录；未知 SQLite 表/列、缺失的引用文件、约束错误和内容校验失败均会阻止提交。

```bash
# connection.txt 为权限 600 的私有文件，内容是目标数据库 libpq DSN。
# 不要将密码放进命令行、日志或版本库。
python backend/scripts/migrate_sqlite_to_postgres.py \
  --sqlite /absolute/backup/mianmian.sqlite3 \
  --dsn-file /absolute/private/connection.txt \
  --report /absolute/backup/migration-report.json --apply
```

全部 `records` JSON（含账号密码哈希、撤销登录信息、报告/PDF 缓存、模板、标记与练习）及 `token_usage` 明细在单个 PostgreSQL 事务内迁移并逐条核对。SQLite 无时区时间按 UTC 转换，保留用量 ID 及自增高水位，避免后续账单主键冲突。成功时将校验摘要写入 `storage_migrations`。省略 `--apply` 可在开放写入之前再次执行全量内容核验；有新业务写入后不应再以旧 SQLite 校验或覆盖线上库。

确认校验通过后，将实际运行后端的 `backend/.env` 设置为 `ENVIRONMENT=production`，并配置可连接的 `DATABASE_URL`，重新启动单进程后端。宿主机后端连接 `127.0.0.1:5432`；容器内后端连接 Compose 的 `postgres:5432`。通过 `/api/health` 确认 `storage=postgresql`，再使用原账号检查题库、班级、学生历史、报告、评价表缓存和用量。管理员 **数据存储** 页面显示实时业务数量及迁移时的校验摘要。

上传原文件属于文件存储，保持原路径与内容并备份，引用记录完整进入 PostgreSQL；它们不转换为数据库 BLOB。PostgreSQL 模式下网页的目录设置仅调整上传文件，旧 SQLite 副本不再参与业务读写，也不会随上传目录变更复制。原 SQLite 留作迁移时点备份。

回退仅适用于切换后尚无新写入的情况：先停止新后端，保存 PostgreSQL 当前备份，恢复迁移前 `.env` 和原 SQLite/上传目录，再启动原配置。若 PostgreSQL 已产生新写入，不能直接切回旧 SQLite，否则会遗漏这些新增数据，应先由运维核对并反向迁移。

本机已于 2026-09-17 完成全量迁移：142 条业务记录、120 条用量明细（630,342 Token）、28 个引用文件逐项核验通过。私有备份及完整校验报告位于 `.local/backups/postgres-migration-20260917T020747Z/`，包括迁移前后 PostgreSQL dump、SQLite 快照、上传目录归档及原后端配置。当前宿主机后端使用 Docker 中的 PostgreSQL，上传文件保持宿主机原位置。开发测试请显式使用 `ENVIRONMENT=development` 和独立 `DATA_DIR`；PostgreSQL 集成测试通过 `MIANMIAN_TEST_POSTGRES_DSN` 自动创建和清理独立 schema。

## 管理员数据存储设置

管理员登录教师端后，侧栏 **数据存储**（`/teacher/storage`）显示实际数据库类型、当前应用读写目录及磁盘可用空间。教师、学生及未登录用户无法调用设置、检查和导出接口，开发模式也不例外。`/api/health` 的 `storage` 字段反映实际数据库类型：仅启动 PostgreSQL 容器并不代表后端已经使用它，需确认 `ENVIRONMENT=production` 和 `DATABASE_URL`。

- **应用数据目录**默认是 `backend/uploads`（Compose 中固定为 `/app/backend/uploads`），读写使用同一位置。SQLite 模式包括业务库、Token 账单和上传文件；PostgreSQL 模式只调整本地文件，业务库仍由 `DATABASE_URL` 决定。
- 支持填入默认位置、检查目录、保存确认、取消待生效变更和离开时未保存提醒。自定义目录必须为独立空目录；不能覆盖其他数据集、互相嵌套或直接读取另一套数据库。检查时会创建不存在的目录并实际验证读写权限。容器内只允许已挂载的目录。
- 保存后标记为 **待后端重启生效**，运行中的请求继续使用原目录。停止所有后端进程后，以单进程重新启动；启动期间复制完整目录，用 SQLite backup API 复制并检查数据库，完成后才提交新读写位置。原目录保留。普通复制失败继续使用原目录，并在页面显示原因；断电或强制终止可能留下目标副本，此时不会覆盖或自动接受该副本，应核对后另选空目录重试。新位置或 SQLite 文件缺失时阻止启动，避免生成空库。
- 设置保存在初始 `DATA_DIR/.storage-settings.json`，或显式 `STORAGE_CONFIG_FILE`。该文件是稳定入口，必须持久化保留，不能随切换删除原配置卷。切换后的设置优先于 `DATA_DIR`。迁移后原目录有保留副本，因此不能直接将它当作空目录切回；先备份并由运维整理副本和配置位置，或选择新的空目录。
- **Docker 宿主机存放位置**是单独的部署方案：PostgreSQL、Redis、上传文件分别默认使用 `pgdata`、`redisdata`、`mianmian_uploads` 命名卷。可填写宿主机绝对目录并保存、导出 `docker-compose.storage.yml`。该文件是兼容 YAML 的 JSON，不含数据库密码；非空宿主机路径导出为 bind mount，禁用自动创建宿主机目录。网页不控制 Docker，也不会声称宿主机目录已经验证或数据库已经搬迁。

应用导出的方案前，先备份、停止所有写入及数据库服务，再将原卷完整复制到目标目录并保留权限（PostgreSQL 数据目录归属尤其需要核对）。上传目录必须包括 `.storage-settings.json`。保持 PostgreSQL 大版本一致。确认数据已迁移后运行：

```bash
docker compose -f docker-compose.yml -f docker-compose.storage.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.storage.yml up -d
```

此后对这套部署的 Compose 操作应始终带上这两个配置文件，防止回到旧挂载。切换应用目录和宿主机挂载应分两次完成。验证账号、题库、报告和上传文件后再考虑清理保留副本；不要执行 `docker compose down -v`、删除数据卷或在数据库运行时直接复制 PostgreSQL 数据目录。默认卷实际名称带 Compose 项目前缀（如 `mianmian_pgdata`），更换项目名可能挂载到新的空卷。

Docker 命名卷独立于容器生命周期，普通重启、停止或保留原卷的重建不会删除数据。Redis 的数据卷只能保存已落盘的数据，默认快照策略下异常中断可能丢失最近写入；若将来用于重要数据，应先备份并按 Redis 官方流程启用 AOF，而不是直接修改启动参数后重建已有实例。目前业务记录尚未使用 Redis。数据卷不等同于备份，磁盘损坏或误删仍需从独立备份恢复。

存储功能验证：`python -m pytest backend/tests/test_storage_locations.py -q`；前端 `npx vitest run tests/AdminStorage.spec.js`。全部前端测试分别运行 `npx vitest run tests/*.spec.js` 与 `node --test tests/import.test.js`（后者使用 Node 测试框架）。
