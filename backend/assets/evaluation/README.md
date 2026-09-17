# 面试评价表资产

当前评价表由 `backend/app/evaluation_sheet.py` 根据教师配置绘制为单页 A4，
不再依赖背景 PDF 的固定八行文字。教师入口为 `/teacher/evaluation`。
配置模型、字数和条目数量上限位于 `evaluation_templates.py`；改动上限须同步检查最坏情况下的 PDF 排版。
4-8 项、权重合计 100%；每条观察要点最多 52 字，评分证据最多 55 字，摘要各最多 42 字。
学生姓名、岗位与班级按其现有最大长度完整换行，字号有下限，容纳失败时明确报错而不截字。

填入内容使用随项目部署的 Noto Sans SC Regular，许可见 `OFL.txt`。
最终 PDF、评价结构及模板快照缓存在数据库中，不依赖 worker 的本地文件。
模板内容变化会使旧缓存失效；重新生成时逐项匹配新条目并按新权重计算。

以下旧模板资产保留作为原始参考；不会被教师配置改写：

原稿：项目根目录 `AI应用开发工程师面试评价表.docx`。
SHA-256：`daabc30166824ad2de199f19fd7efdf86affab1e79fc831936a1c0e6c58b68e1`。

`first-page.pdf` 来自原稿的第一页，保留标题、表格、观察行为与权重，
仅去除待填写字段、原始副标题和双页页码。原 DOCX 未改动。
填入内容使用随项目部署的 Noto Sans SC Regular，许可见 `OFL.txt`。
背景中的 Noto Serif SC 为原文档指定字体，许可见 `Serif-OFL.txt`。

关键维度已经过教师确认：代码工程、大模型应用、效果评估、安全治理。
评分 1-5；N 表示未验证，有 N 不计算总分并给出待补面。
全部验证后按原表权重计算；关键项不足 3 分时不推荐。
结论仅用于模拟训练；没有人工签名，匹配职级需教师复核。

原 `first-page.pdf` 使用 Noto Serif SC，许可见 `Serif-OFL.txt`。
离线脚本 `backend/scripts/prepare_evaluation_template.py` 仍可复现旧模板背景，
但覆盖背景 PDF 或原始 DOCX 不会改变当前教师配置及下载版式。
