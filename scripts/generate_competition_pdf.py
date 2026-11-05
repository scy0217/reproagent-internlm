"""Generate the polished competition technical document PDF."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.report_generator import BOLD, REGULAR, _register_fonts  # noqa: E402


OUTPUT = ROOT / "output" / "pdf" / "ReproAgent比赛技术文档.pdf"


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName=BOLD,
            fontSize=25, leading=36, alignment=TA_CENTER,
            textColor=colors.HexColor("#172554"), spaceAfter=12,
            wordWrap="CJK",
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["Normal"], fontName=REGULAR,
            fontSize=12, leading=20, alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"), wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName=BOLD,
            fontSize=16, leading=23, textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=10, spaceAfter=8, wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName=BOLD,
            fontSize=11.5, leading=18, textColor=colors.HexColor("#1E293B"),
            spaceBefore=7, spaceAfter=5, wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName=REGULAR,
            fontSize=9.5, leading=16, textColor=colors.HexColor("#334155"),
            spaceAfter=6, wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName=REGULAR,
            fontSize=7.8, leading=12, textColor=colors.HexColor("#64748B"),
            wordWrap="CJK",
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["BodyText"], fontName=BOLD,
            fontSize=8, leading=12, textColor=colors.white,
            alignment=TA_LEFT, wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "Table", parent=base["BodyText"], fontName=REGULAR,
            fontSize=7.8, leading=12, textColor=colors.HexColor("#334155"),
            wordWrap="CJK",
        ),
        "callout": ParagraphStyle(
            "Callout", parent=base["BodyText"], fontName=REGULAR,
            fontSize=9, leading=15, textColor=colors.HexColor("#1E3A8A"),
            leftIndent=8, rightIndent=8, spaceBefore=5, spaceAfter=5,
            wordWrap="CJK",
        ),
        "metric": ParagraphStyle(
            "Metric", parent=base["BodyText"], fontName=BOLD,
            fontSize=18, leading=22, alignment=TA_CENTER,
            textColor=colors.HexColor("#1D4ED8"),
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel", parent=base["BodyText"], fontName=REGULAR,
            fontSize=7.5, leading=11, alignment=TA_CENTER,
            textColor=colors.HexColor("#64748B"), wordWrap="CJK",
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def rich(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def section(number: str, title: str, st: dict) -> list:
    return [
        Spacer(1, 2 * mm),
        HRFlowable(
            width="100%", thickness=1.2, color=colors.HexColor("#BFDBFE"),
            spaceBefore=2, spaceAfter=7,
        ),
        p(f"{number}  {title}", st["h1"]),
    ]


def bullet_list(items: list[str], st: dict) -> list:
    return [p(f"• {item}", st["body"]) for item in items]


def data_table(headers: list[str], rows: list[list[str]], widths: list, st: dict) -> Table:
    data = [[p(value, st["table_head"]) for value in headers]]
    data.extend([[p(value, st["table"]) for value in row] for row in rows])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white, colors.HexColor("#F8FAFC")
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def callout(text: str, st: dict) -> Table:
    table = Table([[p(text, st["callout"]) ]], colWidths=[166 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#93C5FD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def flow_diagram(st: dict) -> Table:
    labels = [
        "论文与复现材料", "InternLM Planner", "实验要素提取",
        "可复现性初审", "数值条件路由", "证据复核",
        "置信度门控", "反思扩证", "PDF报告",
    ]
    rows = []
    for start in range(0, len(labels), 3):
        row_labels = labels[start:start + 3]
        row = []
        for index, label in enumerate(row_labels):
            row.append(p(label, st["metric_label"]))
            if index < len(row_labels) - 1:
                row.append(p("→", st["metric_label"]))
        while len(row) < 5:
            row.append("")
        rows.append(row)
    table = Table(rows, colWidths=[45 * mm, 7 * mm, 45 * mm, 7 * mm, 45 * mm])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for row_index in range(len(rows)):
        for column_index in (0, 2, 4):
            style.extend([
                ("BACKGROUND", (column_index, row_index), (column_index, row_index),
                 colors.HexColor("#EFF6FF")),
                ("BOX", (column_index, row_index), (column_index, row_index), 0.7,
                 colors.HexColor("#93C5FD")),
            ])
    table.setStyle(TableStyle(style))
    return table


def draw_page(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#DBEAFE"))
    canvas.line(18 * mm, height - 13 * mm, width - 18 * mm, height - 13 * mm)
    canvas.setFont(REGULAR, 7.2)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(18 * mm, 9 * mm, "ReproAgent 比赛技术文档")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def build() -> Path:
    _register_fonts()
    st = styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=17 * mm,
        title="ReproAgent比赛技术文档",
        author="ReproAgent参赛团队",
        subject="基于书生大模型与LangGraph的科研论文可复现性审计智能体",
    )
    story = []

    story.extend([
        Spacer(1, 36 * mm),
        p("ReproAgent", st["cover_title"]),
        p("基于书生大模型与 LangGraph 的科研论文可复现性审计智能体",
          st["cover_subtitle"]),
        Spacer(1, 12 * mm),
        HRFlowable(width="78%", thickness=2, color=colors.HexColor("#2563EB"),
                   hAlign="CENTER", spaceBefore=4, spaceAfter=15),
        p("参赛方向：开放赋能智能体", st["cover_subtitle"]),
        p("核心闭环：任务规划 - 工具调用 - 数值核验 - 证据回查 - 反思迭代 - 报告输出",
          st["cover_subtitle"]),
        Spacer(1, 40 * mm),
        callout(
            "应用体验链接：最终提交前填写固定 streamlit.app 地址；"
            "演示视频链接：录制后填写长期有效且免登录访问的网盘地址。",
            st,
        ),
        Spacer(1, 28 * mm),
        p(f"文档版本：v1.0  |  生成日期：{date.today().isoformat()}", st["cover_subtitle"]),
        PageBreak(),
    ])

    story += section("一", "项目摘要", st)
    story.append(p(
        "科研论文复现需要人工查找数据来源、实验参数、软件环境、代码入口和结果证据，"
        "并重新核算关键数值。该过程耗时长、标准不统一，通用大模型还可能把资源开放性"
        "不足误判为科学结论不可信。ReproAgent 以书生 Intern-S2 为模型底座，以 LangGraph "
        "为智能体 harness，把语义理解、工具核验、证据回查和正式报告编排成可追溯闭环。",
        st["body"],
    ))
    metrics = Table([
        [p("Intern-S2", st["metric"]), p("LangGraph", st["metric"]),
         p("8/8", st["metric"]), p("PDF", st["metric"])],
        [p("书生模型底座", st["metric_label"]), p("智能体 Harness", st["metric_label"]),
         p("数值工具 benchmark", st["metric_label"]), p("可下载审计报告", st["metric_label"])],
    ], colWidths=[41.5 * mm] * 4)
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([Spacer(1, 4 * mm), metrics])

    story += section("二", "真实痛点与目标用户", st)
    story.append(p("目标用户", st["h2"]))
    story += bullet_list([
        "科研团队：投稿前检查实验描述和结果一致性。",
        "期刊编辑与审稿人：快速定位复现风险和证据页码。",
        "高校科研管理人员：形成规范化审计线索。",
        "复现研究者：建立复现实验准备清单。",
    ], st)
    story.append(p("核心痛点", st["h2"]))
    story += bullet_list([
        "论文信息分散在正文、表格、公式和附录中，人工整理成本高。",
        "百分比和变化率容易出现基准混乱，语言模型心算不稳定。",
        "代码未公开不等于科学结果错误，单一总分容易混淆评价维度。",
        "大模型结论可能缺少原文证据，难以审计和追溯。",
        "通用对话无法呈现任务规划、条件路由、工具调用和失败恢复过程。",
    ], st)
    story.append(PageBreak())

    story += section("三", "解决方案与智能体闭环", st)
    story.append(p(
        "输入为科研论文 PDF，可选上传代码、README、依赖清单或 ZIP 复现材料；输出包括"
        "实验要素、确认问题、过滤误报、页码证据、确定性数值核验、三维评分和正式 PDF 报告。",
        st["body"],
    ))
    story.extend([Spacer(1, 3 * mm), flow_diagram(st), Spacer(1, 4 * mm)])
    story.append(callout(
        "置信度低于 75 分时，智能体自动扩大原文范围并重新复核，最多两轮；"
        "没有数值主张时跳过 Python 数值核验，避免不必要调用。",
        st,
    ))
    story.append(p("工具编排", st["h2"]))
    story.append(data_table(
        ["工具", "职责", "性质"],
        [
            ["experiment_extractor", "提取目标、数据、方法、参数、指标和证据", "模型推理"],
            ["reproducibility_auditor", "发现缺失项、矛盾和证据风险", "模型推理"],
            ["numeric_verifier", "重新计算比例、差值、变化率和比值", "Python确定性"],
            ["evidence_verifier", "回查原文、过滤误报并合并重复问题", "模型 + 规则"],
            ["pdf_report_generator", "生成正式中文审计报告", "确定性"],
        ],
        [43 * mm, 89 * mm, 34 * mm], st,
    ))

    story += section("四", "关键技术创新", st)
    innovations = [
        ("4.1 混合智能核验", "语言模型负责语义理解和候选问题发现，Python 工具负责数值计算；计算结果再次进入证据复核节点。"),
        ("4.2 置信度门控与反思", "根据问题覆盖率和证据质量触发扩证回环，并设置最大两轮上限，兼顾质量与成本。"),
        ("4.3 三分制评价", "分别报告科学可复现性、资源开放性和审计置信度，避免未上传代码无条件拉低科学分。"),
        ("4.4 不可信输入边界", "论文中的命令和提示词只作为待分析内容；复现材料只读目录，不执行上传代码。"),
    ]
    for title, body in innovations:
        story.append(KeepTogether([p(title, st["h2"]), p(body, st["body"])]))
    story.append(PageBreak())

    story += section("五", "工程实现与安全设计", st)
    story.append(data_table(
        ["层次", "采用技术", "说明"],
        [
            ["模型底座", "上海人工智能实验室书生 Intern-S2", "完成结构化提取、审计与证据复核"],
            ["Harness", "LangGraph", "条件路由、共享状态、反思回环和执行轨迹"],
            ["工具层", "Python Tool Registry", "统一输入输出契约与工具白名单"],
            ["应用层", "Streamlit", "网页交互、过程可视化和报告下载"],
            ["文档层", "PyMuPDF + ReportLab", "论文解析与跨平台中文 PDF"],
            ["交付层", "Docker + GitHub Actions", "固定依赖、健康检查和自动验收"],
        ],
        [32 * mm, 59 * mm, 75 * mm], st,
    ))
    story.append(p("公网安全边界", st["h2"]))
    story += bullet_list([
        "PDF 最大 50 MB、最多 500 页、可提取文本最多 200 万字符。",
        "复现材料总大小最大 20 MB；ZIP 最多检查前 5000 个目录项。",
        "复现材料不解压到磁盘、不导入、不执行，仅静态读取文件清单。",
        "API 密钥仅通过云端 Secrets 注入，不进入代码、日志、报告或下载文件。",
        "可设置演示体验码，降低公开模型额度被滥用的风险。",
    ], st)
    story.append(callout(
        "风险声明：本系统输出的是复现风险线索，不替代领域专家审稿、科研诚信调查或最终学术判断。",
        st,
    ))

    story += section("六", "评测结果与验证边界", st)
    story.append(p("已完成的确定性验证", st["h2"]))
    story.append(data_table(
        ["验证项", "样本/覆盖", "结果"],
        [
            ["数值工具 benchmark", "8 个案例，覆盖 6 类运算与异常输入", "8/8，状态准确率 100%"],
            ["核心回归测试", "数值、评分、上传安全、科学记数法", "9 项通过"],
            ["部署预检", "Python语法、密钥扫描、忽略规则、部署文件", "通过"],
            ["公网健康检查", "首页与 Streamlit health endpoint", "HTTP 200"],
        ],
        [51 * mm, 73 * mm, 42 * mm], st,
    ))
    story.append(p(
        "边界说明：8/8 只评价 Python 数值工具在已支持操作上的确定性行为，不代表完整智能体"
        "的提取、问题发现或证据定位准确率。完整系统需要人工标注公开论文进行评测。",
        st["small"],
    ))
    story.append(PageBreak())
    story.append(p("完整智能体评测计划", st["h2"]))
    story.append(data_table(
        ["能力", "指标", "验证方式"],
        [
            ["实验要素提取", "字段准确率、页码准确率", "与双人标注金标准比较"],
            ["问题发现", "Precision、Recall、F1", "逐条比对确认问题"],
            ["误报过滤", "误报下降率", "初审与复核后对比"],
            ["稳定性", "三次运行字段一致率", "同一输入独立运行三次"],
            ["效率", "相对人工耗时降低率", "记录人工与智能体完成时间"],
            ["可靠性", "端到端成功率", "完整生成报告次数/总次数"],
        ],
        [46 * mm, 52 * mm, 68 * mm], st,
    ))

    story += section("七", "可复现交付与部署", st)
    story += bullet_list([
        "完整源代码与固定依赖 requirements.txt。",
        "环境变量模板、Streamlit 配置和密钥忽略规则。",
        "Dockerfile、健康检查、部署预检和 GitHub Actions。",
        "自动化测试、数值 benchmark、评测协议与失败边界。",
        "安全说明、部署说明、技术文档和五分钟演示脚本。",
    ], st)
    story.append(p("部署验收顺序", st["h2"]))
    story += bullet_list([
        "执行部署预检和自动化测试。",
        "推送 GitHub 并在 Streamlit Community Cloud 选择 Python 3.12。",
        "在 Secrets 中写入新书生 API 密钥、模型名称和体验码。",
        "从外部网络验证固定链接、上传入口和健康接口。",
        "使用公开论文完成解析、智能审计和 PDF 下载端到端验收。",
    ], st)

    story += section("八", "局限性与后续路线", st)
    story += bullet_list([
        "扫描型 PDF 暂未集成 OCR，文本为空时提供可读性警告。",
        "确定性工具当前覆盖比例、差值、变化率和比值，不执行论文代码。",
        "下一阶段增加 InternVL 图表解析、引用级证据定位和批量评测集。",
        "引入人工反馈闭环，对误报和证据不足样例进行版本化回归测试。",
    ], st)
    story.append(callout(
        "项目价值：把通用大模型从一次性问答转变为可规划、可调用工具、可验证、"
        "可反思、可追溯的轻量化科研审计智能体。",
        st,
    ))

    story.append(PageBreak())
    story += section("附录", "五分钟演示提纲", st)
    story.append(data_table(
        ["时间", "演示内容", "重点"],
        [
            ["0:00-0:30", "科研复现痛点", "人工耗时、心算错误、证据不可追溯"],
            ["0:30-1:00", "架构与运行状态", "Intern-S2、LangGraph、工具路由"],
            ["1:00-1:30", "上传论文与复现材料", "静态检查，不执行代码"],
            ["1:30-3:20", "启动智能审计", "计划、节点进度、数值核验、反思"],
            ["3:20-4:20", "三维评分与证据", "确认问题、过滤误报、页码和计算过程"],
            ["4:20-4:50", "下载 PDF 报告", "中文、科学记数法、正式交付"],
            ["4:50-5:00", "总结与体验链接", "模型理解 + 工具核验 + 证据回查"],
        ],
        [28 * mm, 57 * mm, 81 * mm], st,
    ))
    story.append(p("演示与提交前检查", st["h2"]))
    story += bullet_list([
        "提前准备一篇公开论文和一组带明确数值关系的演示样例，避免现场等待。",
        "视频中完整展示 Planner 计划、LangGraph 节点、工具轨迹、反思次数和 PDF 下载。",
        "固定公网链接使用无登录浏览器验证，体验码与视频链接写入最终技术文档。",
        "撤销所有曾暴露的旧 API 密钥，新密钥只保存在部署平台 Secrets。",
        "最终提交包重新运行预检、自动化测试和数值 benchmark，并保存终端结果截图。",
    ], st)
    story.append(callout(
        "答辩表达重点：ReproAgent 不是论文摘要工具，而是具有自主规划、条件路由、"
        "确定性工具核验、证据反思和工程化交付能力的科研智能体。",
        st,
    ))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return OUTPUT


if __name__ == "__main__":
    print(build())
