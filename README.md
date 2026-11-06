# ReproAgent

基于上海人工智能实验室书生大模型与 LangGraph 的科研论文可复现性审计智能体。

## 核心能力

- PDF论文与复现材料解析
- InternLM实验要素结构化提取
- 可复现性问题初审与原文证据复核
- Python确定性数值核验
- InternLM Planner 动态生成数值核验、证据深度与反思策略
- LangGraph按规划执行条件路由、置信度门控与反思回环
- 计划—执行一致性对账与安全兜底记录
- 科学可复现性、资源开放性与审计置信度分离评价
- 中文PDF审计报告生成

## 技术架构

`InternLM Planner → 执行策略 → LangGraph → 工具注册表 → 提取/审计/数值核验/证据复核/PDF报告 → 计划执行对账`

Planner 会为每篇论文选择数值核验策略、证据检索深度和最大反思轮数。当实际文档中出现数值主张时，安全路由可覆盖不合理的“跳过核验”计划。结束后系统对计划工具与实际轨迹进行逐项对账。

## 本地运行

推荐 Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

填写 `.env` 中的 `INTERNLM_API_KEY` 后运行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

运行不调用模型的确定性验收：

```powershell
.\.venv\Scripts\python.exe scripts\preflight.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\run_numeric_benchmark.py
```

当前确定性数值工具 benchmark 为 8/8 状态判断正确；该结果不冒充完整智能体准确率。完整评测边界和人工标注方案见 [docs/评测报告.md](docs/评测报告.md)。

生成比赛技术文档 PDF：

```powershell
.\.venv\Scripts\python.exe scripts\generate_competition_pdf.py
```

## Streamlit Community Cloud 部署

1. 将本项目推送到 GitHub 仓库，确保 `.env` 未被提交。
2. 在 Streamlit Community Cloud 创建应用。
3. Repository选择该仓库，Branch选择主分支，Main file path填写 `app.py`。
4. Advanced settings中选择Python 3.12。
5. Secrets中填写：

```toml
INTERNLM_API_KEY = "你的书生API密钥"
INTERNLM_BASE_URL = "https://chat.intern-ai.org.cn/api/v1/"
INTERNLM_MODEL = "intern-s2"
DEMO_ACCESS_CODE = "提交文档中提供给评委的体验码"
```

6. 部署后使用平台生成的 `https://*.streamlit.app` 地址访问。

部署细节、Docker备用方案和比赛验收清单见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 安全说明

- 不执行用户上传的代码，仅进行静态文件清单检查。
- 公网部署可通过 `DEMO_ACCESS_CODE` 限制模型调用，防止API额度被滥用。
- 单个PDF最大50 MB，复现材料总大小最大20 MB。
- `.env`、虚拟环境、临时文件和Streamlit secrets均被 `.gitignore` 排除。
- 论文文本、提取结果和审计结果均按不可信输入处理，防止提示词注入。
- PDF最多500页、可提取文本最多200万字符，避免异常文档耗尽公网实例资源。
- 详细威胁边界与密钥轮换方法见 [SECURITY.md](SECURITY.md)。

## 主要入口

- `app.py`：Streamlit网页入口
- `core/langgraph_runner.py`：LangGraph编排与反思回环
- `core/internlm_client.py`：书生模型API客户端
- `core/tool_registry.py`：智能体工具注册表
- `core/report_generator.py`：PDF报告生成
