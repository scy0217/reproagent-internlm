# 部署与验收

## 部署前

```powershell
python scripts/preflight.py
python -m unittest discover -s tests -v
```

预检不会调用书生模型，也不会打印 API 密钥。

## Streamlit Community Cloud

1. 把仓库推送到 GitHub，确认 `.env` 和 `.streamlit/secrets.toml` 未提交。
2. 在 Streamlit Community Cloud 新建应用，入口文件选择 `app.py`，Python 选择 3.12。
3. 在 Secrets 中设置：

```toml
INTERNLM_API_KEY = "新创建的书生API密钥"
INTERNLM_BASE_URL = "https://chat.intern-ai.org.cn/api/v1/"
INTERNLM_MODEL = "intern-s2"
DEMO_ACCESS_CODE = "提供给评委的体验码"
```

4. 部署后执行外部健康检查：

```powershell
python scripts/smoke_http.py https://你的应用.streamlit.app
```

5. 使用一篇公开 PDF 完成“解析 → 智能审计 → PDF 下载”的端到端验收。

## Docker（备用部署）

```powershell
docker build -t reproagent .
docker run --rm -p 8501:8501 `
  -e INTERNLM_API_KEY="你的新密钥" `
  -e DEMO_ACCESS_CODE="体验码" `
  reproagent
```

访问 `http://localhost:8501`。生产环境应使用平台密钥管理，不要把密钥写进镜像或命令历史。

## 比赛提交前验收清单

- 固定公网链接可从无登录浏览器打开。
- 评委体验码已写入技术文档，且未写入公开代码仓库。
- InternLM 模型名称、LangGraph 流程图和工具调用轨迹可在界面中看到。
- 至少准备一篇演示论文和一组带明确数值矛盾的测试样例。
- PDF 报告可以下载，中文、公式数量级和页码证据显示正常。
- 旧 API 密钥已撤销，新密钥仅存在于平台 Secrets。
