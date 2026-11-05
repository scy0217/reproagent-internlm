# ReproAgent

基于上海人工智能实验室书生大模型与 LangGraph 的科研论文可复现性审计智能体。

## 核心能力

- PDF论文与复现材料解析
- InternLM实验要素结构化提取
- 可复现性问题初审与原文证据复核
- Python确定性数值核验
- LangGraph条件路由、置信度门控与反思回环
- 科学可复现性、资源开放性与审计置信度分离评价
- 中文PDF审计报告生成

## 技术架构

`InternLM Planner → LangGraph → 工具注册表 → 提取/审计/数值核验/证据复核/PDF报告`

当证据核验置信度低于75分时，智能体自动扩大原文范围并重新复核，最多两轮。

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
```

6. 部署后使用平台生成的 `https://*.streamlit.app` 地址访问。

## 安全说明

- 不执行用户上传的代码，仅进行静态文件清单检查。
- `.env`、虚拟环境、临时文件和Streamlit secrets均被 `.gitignore` 排除。
- 论文文本、提取结果和审计结果均按不可信输入处理，防止提示词注入。

## 主要入口

- `app.py`：Streamlit网页入口
- `core/langgraph_runner.py`：LangGraph编排与反思回环
- `core/internlm_client.py`：书生模型API客户端
- `core/tool_registry.py`：智能体工具注册表
- `core/report_generator.py`：PDF报告生成
