# 面试评价表第一页

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

运行时只需 `reportlab` 和已有的 `pypdf`，无需 LibreOffice。
部署时 `COPY backend` 会包含模板与字体。最终 PDF 和结构化评估缓存在
数据库 `evaluation_sheet` 记录中，不依赖某个 worker 的本地文件。

替换模板时，先用正确的中文字体将 DOCX 渲染成 PDF，再使用
`backend/scripts/prepare_evaluation_template.py`，传入 `--pdf`、
`--font`（Noto Sans SC TTF）、`--license` 和 `--output`。
这个离线准备脚本需要 PyMuPDF 和 fonttools；线上服务不需要这两项。
若布局改变，须同步校准准备脚本的清除区域及 `evaluation_sheet.py` 的填入坐标，
更新 VERSION，并验证导出只有一页且全部字段可读。单纯覆盖 DOCX 不会自动修改模板。
