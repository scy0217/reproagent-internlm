from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from core.text_normalizer import (
    normalize_structure,
    quarantine_broken_symbol_issues,
)
from core.scoring_profiles import (
    calculate_scientific_score,
    infer_document_type,
)


REGULAR = "ReproAgentCJK"
# Use one embedded CJK face for every style. Registering the same large CJK
# face twice under different aliases can produce conflicting PDF subsets.
# Heading hierarchy is still expressed through size, spacing and colour.
BOLD = REGULAR

REQUIRED_CJK_CHARS = "科研论文可复现性审计报告确认问题证据页码主要结果研究目标对象方法"


def _register_first_supported_font(
    font_name: str,
    candidates: list[str],
) -> None:
    """Register the first existing font that ReportLab can embed.

    Some Linux Noto CJK collections use PostScript/CFF outlines. They exist on
    disk but are not supported by ReportLab's ``TTFont`` implementation, so a
    successful path lookup alone is not enough.
    """

    errors: list[str] = []
    for candidate in candidates:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            font = TTFont(font_name, str(path))
            char_map = getattr(font.face, "charToGlyph", {})
            missing = [
                char for char in REQUIRED_CJK_CHARS
                if ord(char) not in char_map
            ]
            if missing:
                errors.append(
                    f"{path.name}: 缺少字形{''.join(missing[:8])}"
                )
                continue
            pdfmetrics.registerFont(font)
            return
        except Exception as exc:  # Continue to a compatible fallback font.
            errors.append(f"{path.name}: {exc}")

    details = "; ".join(errors[-2:]) if errors else "未发现候选字体文件"
    raise RuntimeError(
        "未找到ReportLab可嵌入的中文TrueType字体。"
        "Linux请安装fonts-wqy-microhei；"
        f"字体探测结果：{details}"
    )


def _register_fonts() -> None:
    regular_candidates = [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyh.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    if REGULAR not in pdfmetrics.getRegisteredFontNames():
        _register_first_supported_font(REGULAR, regular_candidates)
    pdfmetrics.registerFontFamily(
        REGULAR,
        normal=REGULAR,
        bold=BOLD,
        italic=REGULAR,
        boldItalic=BOLD,
    )


def _safe(value) -> str:
    if value in (None, ""):
        return "未提供"
    return escape(str(value)).replace("\n", "<br/>")


def _page_text(pages: list) -> str:
    values = [str(page) for page in pages if page not in (None, 0, "")]
    return "、".join(values) if values else "未标注"


def _make_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CNTitle", parent=base["Title"], fontName=BOLD, fontSize=22,
            leading=30, alignment=TA_CENTER, textColor=colors.HexColor("#172554"),
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "CNSubtitle", parent=base["Normal"], fontName=REGULAR, fontSize=10,
            leading=15, alignment=TA_CENTER, textColor=colors.HexColor("#64748B"),
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "CNH1", parent=base["Heading1"], fontName=BOLD, fontSize=15,
            leading=21, textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=13, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "CNH2", parent=base["Heading2"], fontName=BOLD, fontSize=11.5,
            leading=17, textColor=colors.HexColor("#1E293B"),
            spaceBefore=8, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "CNBody", parent=base["BodyText"], fontName=REGULAR, fontSize=9.5,
            leading=16, textColor=colors.HexColor("#334155"),
            spaceAfter=6, wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "CNSmall", parent=base["BodyText"], fontName=REGULAR, fontSize=8,
            leading=12, textColor=colors.HexColor("#64748B"), wordWrap="CJK",
        ),
        "metric": ParagraphStyle(
            "CNMetric", parent=base["BodyText"], fontName=BOLD, fontSize=15,
            leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#0F172A"),
        ),
        "metric_label": ParagraphStyle(
            "CNMetricLabel", parent=base["BodyText"], fontName=REGULAR, fontSize=8,
            leading=12, alignment=TA_CENTER, textColor=colors.HexColor("#64748B"),
        ),
    }


def _bullets(story: list, items: list, styles: dict) -> None:
    if not items:
        story.append(Paragraph("暂无相关信息。", styles["small"]))
        return
    for item in items:
        text = item.get("name") or item.get("title") or str(item) if isinstance(item, dict) else str(item)
        story.append(Paragraph(f"• {_safe(text)}", styles["body"]))


def _draw_page(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#DBEAFE"))
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont(REGULAR, 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(18 * mm, 9 * mm, "ReproAgent 科研论文可复现性审计报告")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def generate_pdf_report(
    extraction_result: dict,
    verified_result: dict,
    source_filename: str = "",
) -> bytes:
    """生成正式中文PDF审计报告。"""
    extraction_result = normalize_structure(extraction_result)
    verified_result = quarantine_broken_symbol_issues(verified_result)
    profile_key = verified_result.get("score_breakdown", {}).get(
        "profile",
        infer_document_type(extraction_result),
    )
    scientific_score, scientific_dimensions = calculate_scientific_score(
        verified_result,
        profile_key,
    )
    verified_result["reproducibility_score"] = scientific_score
    if verified_result.get("score_breakdown"):
        verified_result["score_breakdown"][
            "scientific_reproducibility"
        ] = scientific_score
        verified_result["score_breakdown"][
            "scientific_dimensions"
        ] = scientific_dimensions
    _register_fonts()
    styles = _make_styles()
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=17 * mm,
        title="ReproAgent 科研论文可复现性审计报告", author="ReproAgent",
    )

    breakdown = verified_result.get("score_breakdown", {}) or {}
    score = int(
        breakdown.get(
            "scientific_reproducibility",
            verified_result.get("reproducibility_score", 0),
        )
    )
    openness_score = int(
        breakdown.get(
            "resource_openness",
            verified_result.get("resource_openness_score", 0),
        )
    )
    confidence_score = int(
        breakdown.get(
            "audit_confidence",
            verified_result.get("audit_confidence_score", 0),
        )
    )
    issues = verified_result.get("verified_issues", [])
    rejected = verified_result.get("rejected_issues", [])
    strengths = verified_result.get("verified_strengths", [])
    risk = "较低" if score >= 85 else "中等" if score >= 70 else "较高"
    paper_title = extraction_result.get("title") or source_filename or "未识别论文标题"

    story = [
        Spacer(1, 7 * mm),
        Paragraph("ReproAgent", styles["title"]),
        Paragraph("科研论文可复现性审计报告", styles["subtitle"]),
        Paragraph(_safe(paper_title), styles["h1"]),
        Paragraph(
            f"来源文件：{_safe(source_filename or '未记录')}　　"
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["small"],
        ),
        Spacer(1, 5 * mm),
    ]

    metric_table = Table(
        [
            [Paragraph(str(score), styles["metric"]), Paragraph(str(openness_score), styles["metric"]),
             Paragraph(str(confidence_score), styles["metric"]), Paragraph(str(len(issues)), styles["metric"])],
            [Paragraph("科学可复现性", styles["metric_label"]), Paragraph("资源开放性", styles["metric_label"]),
             Paragraph("审计置信度", styles["metric_label"]), Paragraph("确认问题", styles["metric_label"])],
        ],
        colWidths=[42 * mm] * 4,
    )
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), .4, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([metric_table, Spacer(1, 5 * mm)])

    profile_label = breakdown.get("profile_label", "通用科研论文")
    story.append(Paragraph(
        f"评分口径：{_safe(profile_label)}；科学风险：{risk}。"
        "未公开代码仅降低资源开放性；只有关键方法必须依赖缺失代码、"
        "且无法依据论文重建时，才降低科学可复现性。",
        styles["small"],
    ))

    score_rows = [[
        Paragraph("评分域", styles["metric_label"]),
        Paragraph("分项", styles["metric_label"]),
        Paragraph("得分", styles["metric_label"]),
    ]]
    for item in breakdown.get("scientific_dimensions", {}).values():
        score_rows.append([
            Paragraph("科学可复现性", styles["small"]),
            Paragraph(_safe(item.get("label")), styles["small"]),
            Paragraph(
                f"{item.get('score', 0)}/{item.get('max_score', 0)}",
                styles["small"],
            ),
        ])
    for item in breakdown.get("openness_dimensions", {}).values():
        score_rows.append([
            Paragraph("资源开放性", styles["small"]),
            Paragraph(_safe(item.get("label")), styles["small"]),
            Paragraph(
                f"{item.get('score', 0)}/{item.get('max_score', 0)}",
                styles["small"],
            ),
        ])
    for item in breakdown.get("confidence_dimensions", {}).values():
        score_rows.append([
            Paragraph("审计置信度", styles["small"]),
            Paragraph(_safe(item.get("label")), styles["small"]),
            Paragraph(
                f"{item.get('score', 0)}/{item.get('max_score', 0)}",
                styles["small"],
            ),
        ])
    if len(score_rows) > 1:
        score_table = Table(score_rows, colWidths=[54 * mm, 72 * mm, 42 * mm])
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([
            Paragraph("评分明细", styles["h2"]),
            score_table,
            Spacer(1, 3 * mm),
        ])

    summary = verified_result.get("verification_summary")
    if summary:
        box = Table(
            [[Paragraph(f"<b>审计摘要</b><br/>{_safe(summary)}", styles["body"])]],
            colWidths=[168 * mm],
        )
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ("BOX", (0, 0), (-1, -1), .7, colors.HexColor("#BFDBFE")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.extend([box, Spacer(1, 3 * mm)])

    story.append(Paragraph("一、研究信息概览", styles["h1"]))
    story.append(Paragraph(f"<b>研究目标：</b>{_safe(extraction_result.get('research_goal'))}", styles["body"]))
    story.append(Paragraph(f"<b>研究对象：</b>{_safe(extraction_result.get('research_object'))}", styles["body"]))
    story.append(Paragraph("主要研究方法", styles["h2"]))
    _bullets(story, extraction_result.get("methods", []), styles)
    story.append(Paragraph("主要研究结果", styles["h2"]))
    _bullets(story, extraction_result.get("main_results", []), styles)

    story.append(Paragraph("二、确认的可复现性问题", styles["h1"]))
    if not issues:
        story.append(Paragraph("未发现经过证据验证的可复现性问题。", styles["body"]))
    severity_style = {
        "high": ("高风险", "#FEE2E2", "#B91C1C"),
        "medium": ("中风险", "#FEF3C7", "#92400E"),
        "low": ("低风险", "#DBEAFE", "#1D4ED8"),
    }
    for index, issue in enumerate(issues, start=1):
        label, background, foreground = severity_style.get(
            issue.get("severity", "low"), severity_style["low"]
        )
        title = issue.get("title") or issue.get("description") or f"问题 {index}"
        header = Table(
            [[Paragraph(f"<b>{index}. [{label}] {_safe(title)}</b>", styles["body"])]],
            colWidths=[168 * mm],
        )
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(foreground)),
            ("BOX", (0, 0), (-1, -1), .5, colors.HexColor(foreground)),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([
            header,
            Paragraph(f"<b>证据页码：</b>{_page_text(issue.get('pages', []))}", styles["small"]),
            Paragraph(
                "<b>影响范围：</b>" + _safe({
                    "scientific_reproducibility": "科学可复现性",
                    "resource_openness": "资源开放性",
                    "both": "科学可复现性与资源开放性",
                }.get(issue.get("impact_scope"), "未分类")),
                styles["small"],
            ),
            Paragraph(f"<b>判断依据：</b>{_safe(issue.get('reason'))}", styles["body"]),
        ])
        if issue.get("calculation"):
            story.append(Paragraph(f"<b>核算过程：</b>{_safe(issue['calculation'])}", styles["body"]))
        evidence = issue.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if evidence:
            story.append(Paragraph("<b>原文证据：</b>", styles["body"]))
            _bullets(story, evidence, styles)
        if issue.get("suggestion"):
            story.append(Paragraph(f"<b>改进建议：</b>{_safe(issue['suggestion'])}", styles["body"]))
        story.append(Spacer(1, 3 * mm))

    numeric_result = verified_result.get("numeric_verification_result", {}) or {}
    story.append(Paragraph("三、确定性数值核验", styles["h1"]))
    numeric_items = numeric_result.get("results", [])
    if not numeric_items:
        story.append(Paragraph("未识别到可由Python确定性核验的数值主张。", styles["body"]))
    else:
        numeric_rows = [[
            Paragraph("编号", styles["metric_label"]),
            Paragraph("主张", styles["metric_label"]),
            Paragraph("计算值 / 论文值", styles["metric_label"]),
            Paragraph("结论", styles["metric_label"]),
        ]]
        status_labels = {
            "consistent": "一致",
            "inconsistent": "不一致",
            "error": "计算失败",
        }
        for item in numeric_items:
            numeric_rows.append([
                Paragraph(_safe(item.get("claim_id")), styles["small"]),
                Paragraph(_safe(item.get("claim")), styles["small"]),
                Paragraph(
                    f"{_safe(item.get('calculated_value'))} / "
                    f"{_safe(item.get('claimed_value'))}",
                    styles["small"],
                ),
                Paragraph(
                    status_labels.get(item.get("status"), "未知"),
                    styles["small"],
                ),
            ])
        numeric_table = Table(
            numeric_rows,
            colWidths=[18 * mm, 75 * mm, 48 * mm, 27 * mm],
            repeatRows=1,
        )
        numeric_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(numeric_table)

    story.append(Paragraph("四、过滤的误报", styles["h1"]))
    if not rejected:
        story.append(Paragraph("本次审计没有需要过滤的误报。", styles["body"]))
    for index, item in enumerate(rejected, start=1):
        story.append(Paragraph(f"<b>{index}. {_safe(item.get('title'))}</b>", styles["h2"]))
        story.append(Paragraph(_safe(item.get("reason")), styles["body"]))

    story.append(Paragraph("五、研究优点", styles["h1"]))
    _bullets(story, strengths, styles)
    story.extend([
        Spacer(1, 5 * mm),
        HRFlowable(width="100%", thickness=.6, color=colors.HexColor("#CBD5E1")),
        Spacer(1, 2 * mm),
        Paragraph(
            "说明：本报告由 ReproAgent 基于论文文本、模型审计和证据复核自动生成。"
            "审计结论用于辅助科研质量检查，不替代领域专家评审。",
            styles["small"],
        ),
    ])

    document.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return output.getvalue()
