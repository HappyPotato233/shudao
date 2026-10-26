"""隐患详情 PDF 导出服务。"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image as PdfImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings


pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _detail_table(detail: dict) -> list[list[str]]:
    rows = [
        ["隐患编号", _text(detail.get("hazard_id"))],
        ["隐患标题", _text(detail.get("title"))],
        ["隐患等级", _text(detail.get("level"))],
        ["当前状态", _text(detail.get("status"))],
        ["隐患类别", _text(detail.get("category"))],
        ["发生位置", _text(detail.get("location"))],
        ["GPS 坐标", _text(detail.get("location_coords"))],
        ["所属项目", _text(detail.get("project"))],
        ["上报人", _text((detail.get("reporter") or {}).get("name"))],
        ["发生时间", _text(detail.get("occurred_at"))],
        ["上报时间", _text(detail.get("created_at"))],
        ["详细描述", _text(detail.get("description"))],
    ]
    return rows


def build_hazard_pdf(detail: dict) -> bytes:
    """根据 H03 详情数据生成 PDF 字节流。"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="隐患详情单",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CJKTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "CJKHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=14,
        leading=18,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "CJKBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
    )

    elements = [
        Paragraph("蜀道安全助手 - 隐患详情单", title_style),
        Spacer(1, 4 * mm),
    ]

    table = Table(
        _detail_table(detail),
        colWidths=[32 * mm, 138 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f6f8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9d9d9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)

    timeline = detail.get("timeline") or []
    if timeline:
        elements.append(Paragraph("处理时间线", heading_style))
        for item in timeline:
            line = (
                f"{_text(item.get('time'))}  "
                f"{_text(item.get('node'))}  "
                f"{_text(item.get('operator'))}  "
                f"{_text(item.get('note'))}"
            )
            elements.append(Paragraph(line, body_style))

    assignment = detail.get("assignment")
    if assignment:
        elements.append(Paragraph("派单信息", heading_style))
        elements.append(
            Paragraph(
                "责任人："
                + _text((assignment.get("assignee") or {}).get("name"))
                + "；整改要求："
                + _text(assignment.get("requirements"))
                + "；截止时间："
                + _text(assignment.get("deadline"))
                + "；优先级："
                + _text(assignment.get("priority")),
                body_style,
            )
        )

    rectification = detail.get("rectification")
    if rectification:
        elements.append(Paragraph("整改反馈", heading_style))
        elements.append(
            Paragraph(
                "整改措施："
                + _text(rectification.get("measures"))
                + "；完成时间："
                + _text(rectification.get("completed_at"))
                + "；轮次："
                + _text(rectification.get("round")),
                body_style,
            )
        )

    review = detail.get("review")
    if review:
        elements.append(Paragraph("验收结果", heading_style))
        elements.append(
            Paragraph(
                "结论："
                + _text(review.get("result"))
                + "；意见："
                + _text(review.get("comment")),
                body_style,
            )
        )

    media = detail.get("media") or {}
    image_urls = (media.get("images") or []) + (media.get("annotated_images") or [])
    if image_urls:
        elements.append(Paragraph("现场图片", heading_style))
        for url in image_urls[:9]:
            rel = str(url or "").removeprefix("/uploads/")
            if not rel:
                continue
            image_path = Path(settings.UPLOAD_DIR) / rel
            if not image_path.is_file():
                continue
            try:
                from PIL import Image as PilImage

                with PilImage.open(image_path) as probe:
                    probe.verify()
                elements.append(PdfImage(str(image_path), width=160 * mm, height=90 * mm))
                elements.append(Spacer(1, 2 * mm))
            except Exception:
                continue

    detections = media.get("detections") or []
    if detections:
        elements.append(Paragraph("AI 识别结果", heading_style))
        for item in detections:
            elements.append(
                Paragraph(
                    "标签："
                    + _text(item.get("label"))
                    + "；风险："
                    + _text(item.get("risk"))
                    + "；置信度："
                    + _text(item.get("conf"))
                    + "；整改建议："
                    + _text(item.get("fix")),
                    body_style,
                )
            )

    doc.build(elements)
    return buffer.getvalue()


def build_exam_score_report_pdf(result: dict) -> bytes:
    """根据考试结果生成成绩单 PDF 字节流。"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="考试成绩单",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExamPdfTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "ExamPdfHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=14,
        leading=18,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ExamPdfBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
    )

    summary = [
        ["试卷", _text(result.get("paper_title"))],
        ["答卷人", _text(result.get("user_name"))],
        ["总分", _text(result.get("total_score"))],
        ["及格分", _text(result.get("pass_score"))],
        ["是否通过", "通过" if result.get("passed") else "未通过"],
        ["提交时间", _text(result.get("submitted_at"))],
    ]
    table = Table(summary, colWidths=[30 * mm, 140 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f6f8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9d9d9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    elements = [
        Paragraph("蜀道安全助手 - 考试成绩单", title_style),
        Spacer(1, 4 * mm),
        table,
        Paragraph("答题详情", heading_style),
    ]

    for item in result.get("details", []) or []:
        line = (
            f"第{item.get('index')}题：{_text(item.get('content'))} "
            f"得分 {_text(item.get('score'))}/{_text(item.get('max_score'))}；"
            f"答卷人答案：{_text(item.get('user_answer'))}；"
            f"正确答案：{_text(item.get('correct_answer'))}"
        )
        elements.append(Paragraph(line, body_style))

    doc.build(elements)
    return buffer.getvalue()
