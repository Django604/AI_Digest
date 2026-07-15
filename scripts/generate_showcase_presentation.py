from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_JSON = ROOT / "docs" / "data" / "dashboard.json"
SUMMARY_JSON = ROOT / "docs" / "data" / "dashboard.summary.json"
DEFAULT_OUT = ROOT / "reports" / "AI_Digest_Effect_Showcase_2026-04-17.pptx"
DEFAULT_TEMPLATE = Path(r"C:\Program Files\Microsoft Office\root\Office16\2052\PREVIEWTEMPLATE.POTX")

SLIDE_W = 12_192_000
SLIDE_H = 6_858_000
EMU_PER_INCH = 914_400

NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

COLORS = {
    "bg": "F6F3EE",
    "surface": "FFFDF9",
    "surface_alt": "F1ECE3",
    "navy": "132238",
    "navy_soft": "2B3B53",
    "red": "C1193C",
    "red_soft": "F3D6DD",
    "green": "2E7D5A",
    "green_soft": "DCEFE7",
    "amber": "A66E1E",
    "amber_soft": "F4E7D0",
    "text": "17202C",
    "muted": "636B78",
    "border": "D8D1C6",
    "white": "FFFFFF",
}

XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


@dataclass
class ParagraphSpec:
    text: str
    size: int = 18
    color: str = COLORS["text"]
    bold: bool = False
    align: str = "l"
    italic: bool = False


@dataclass
class BoxSpec:
    x: float
    y: float
    w: float
    h: float
    paragraphs: list[ParagraphSpec]
    fill: str | None = None
    line: str | None = None
    rounded: bool = False
    tx_box: bool = True
    margin_left: float = 0.16
    margin_right: float = 0.16
    margin_top: float = 0.10
    margin_bottom: float = 0.08
    anchor: str = "t"


@dataclass
class SlideSpec:
    title: str
    elements: list[str] = field(default_factory=list)


def inches(value: float) -> int:
    return int(round(value * EMU_PER_INCH))


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def fmt_dt(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%Y-%m-%d %H:%M")


def load_context() -> dict[str, object]:
    payload = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    brief_sections = payload["dashboards"]["brief"]["briefing"]["sections"]
    return {
        "payload": payload,
        "summary": summary,
        "report_date": payload["meta"]["reportDateLabel"],
        "data_start": payload["meta"]["dataRangeStart"],
        "data_end": payload["meta"]["dataRangeEnd"],
        "dashboard_count": summary["stats"]["dashboardCount"],
        "section_counts": summary["stats"]["sectionCounts"],
        "dashboard_status": summary["outputs"]["dashboardStatus"],
        "brief_sections": brief_sections,
        "lead_summary": payload["dashboards"]["lead-control"]["sections"][0]["trend"]["summary"]["items"],
        "nev_summary": payload["dashboards"]["nev"]["sections"][0]["trend"]["summary"]["items"],
        "ice_summary": payload["dashboards"]["ice"]["sections"][0]["trend"]["summary"]["items"],
        "arrival_summary": payload["dashboards"]["arrival"]["sections"][0]["trend"]["summary"]["items"],
        "nev_sections": [section["title"] for section in payload["dashboards"]["nev"]["sections"]],
        "ice_sections": [section["title"] for section in payload["dashboards"]["ice"]["sections"]],
    }


def para(
    text: str,
    *,
    size: int = 18,
    color: str = COLORS["text"],
    bold: bool = False,
    align: str = "l",
    italic: bool = False,
) -> ParagraphSpec:
    return ParagraphSpec(text=text, size=size, color=color, bold=bold, align=align, italic=italic)


def build_shape(shape_id: int, name: str, box: BoxSpec) -> str:
    geom = "roundRect" if box.rounded else "rect"
    line_xml = (
        f"<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"{box.line}\"/></a:solidFill></a:ln>"
        if box.line
        else "<a:ln><a:noFill/></a:ln>"
    )
    fill_xml = (
        f"<a:solidFill><a:srgbClr val=\"{box.fill}\"/></a:solidFill>"
        if box.fill
        else "<a:noFill/>"
    )
    c_nv_sp_pr = '<p:cNvSpPr txBox="1"/>' if box.tx_box else "<p:cNvSpPr/>"
    tx_body = ""
    if box.tx_box:
        paragraphs_xml = "".join(build_paragraph_xml(item) for item in box.paragraphs)
        tx_body = (
            f"<p:txBody>"
            f"<a:bodyPr wrap=\"square\" anchor=\"{box.anchor}\" "
            f"lIns=\"{inches(box.margin_left)}\" rIns=\"{inches(box.margin_right)}\" "
            f"tIns=\"{inches(box.margin_top)}\" bIns=\"{inches(box.margin_bottom)}\"/>"
            f"<a:lstStyle/>{paragraphs_xml}</p:txBody>"
        )
    return (
        f"<p:sp>"
        f"<p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"{escape(name)}\"/>{c_nv_sp_pr}<p:nvPr/></p:nvSpPr>"
        f"<p:spPr><a:xfrm><a:off x=\"{inches(box.x)}\" y=\"{inches(box.y)}\"/>"
        f"<a:ext cx=\"{inches(box.w)}\" cy=\"{inches(box.h)}\"/></a:xfrm>"
        f"<a:prstGeom prst=\"{geom}\"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}</p:spPr>"
        f"{tx_body}"
        f"</p:sp>"
    )


def build_paragraph_xml(spec: ParagraphSpec) -> str:
    align_map = {"l": "l", "ctr": "ctr", "r": "r"}
    font_size = spec.size * 100
    flags = []
    if spec.bold:
        flags.append(' b="1"')
    if spec.italic:
        flags.append(' i="1"')
    return (
        f"<a:p>"
        f"<a:pPr algn=\"{align_map.get(spec.align, 'l')}\" marL=\"0\" indent=\"0\"/>"
        f"<a:r>"
        f"<a:rPr lang=\"zh-CN\" altLang=\"en-US\" sz=\"{font_size}\"{''.join(flags)}>"
        f"<a:solidFill><a:srgbClr val=\"{spec.color}\"/></a:solidFill>"
        f"</a:rPr>"
        f"<a:t>{escape(spec.text)}</a:t>"
        f"</a:r>"
        f"<a:endParaRPr lang=\"zh-CN\" altLang=\"en-US\" sz=\"{font_size}\"/>"
        f"</a:p>"
    )


def make_slide_xml(body_shapes: list[str]) -> str:
    shapes = "".join(body_shapes)
    return (
        f"{XML_DECL}"
        f"<p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        f"xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        f"xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
        f"<p:cSld><p:spTree>"
        f"<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        f"<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
        f"<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        f"{shapes}"
        f"</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def make_slide_rels(layout_target: str = "../slideLayouts/slideLayout7.xml") -> str:
    return (
        f"{XML_DECL}"
        f"<Relationships xmlns=\"{NS_REL}\">"
        f"<Relationship Id=\"rId1\" "
        f"Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" "
        f"Target=\"{layout_target}\"/>"
        f"</Relationships>"
    )


def base_slide(slide_no: int, total: int, section: str, title: str, subtitle: str = "") -> tuple[list[str], int]:
    elements: list[str] = []
    shape_id = 2
    elements.append(
        build_shape(
            shape_id,
            "Background",
            BoxSpec(0, 0, SLIDE_W / EMU_PER_INCH, SLIDE_H / EMU_PER_INCH, [], fill=COLORS["bg"], line=None, tx_box=False),
        )
    )
    shape_id += 1
    elements.append(
        build_shape(
            shape_id,
            "Top Bar",
            BoxSpec(0, 0, 13.333, 0.22, [], fill=COLORS["navy"], line=None, tx_box=False),
        )
    )
    shape_id += 1
    elements.append(
        build_shape(
            shape_id,
            "Section Label",
            BoxSpec(0.72, 0.38, 2.6, 0.36, [para(section, size=14, color=COLORS["red"], bold=True)], fill=None, line=None),
        )
    )
    shape_id += 1
    elements.append(
        build_shape(
            shape_id,
            "Title",
            BoxSpec(0.72, 0.72, 10.0, 0.62, [para(title, size=28, color=COLORS["navy"], bold=True)], fill=None, line=None),
        )
    )
    shape_id += 1
    if subtitle:
        elements.append(
            build_shape(
                shape_id,
                "Subtitle",
                BoxSpec(0.72, 1.24, 11.0, 0.34, [para(subtitle, size=13, color=COLORS["muted"])], fill=None, line=None),
            )
        )
        shape_id += 1
    elements.append(
        build_shape(
            shape_id,
            "Slide Number",
            BoxSpec(11.8, 7.02, 0.75, 0.24, [para(f"{slide_no}/{total}", size=12, color=COLORS["muted"], align="r")], fill=None, line=None),
        )
    )
    shape_id += 1
    return elements, shape_id


def card(
    shape_id: int,
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: list[str],
    *,
    fill: str = COLORS["surface"],
    line: str = COLORS["border"],
    title_color: str = COLORS["navy"],
    body_color: str = COLORS["muted"],
) -> str:
    paragraphs = [para(title, size=18, color=title_color, bold=True)]
    paragraphs.extend(para(item, size=14, color=body_color) for item in lines)
    return build_shape(shape_id, name, BoxSpec(x, y, w, h, paragraphs, fill=fill, line=line, rounded=True))


def metric_card(
    shape_id: int,
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    note: str,
    *,
    accent: str = COLORS["red"],
) -> str:
    paragraphs = [
        para(label, size=14, color=COLORS["muted"], bold=True),
        para(value, size=28, color=accent, bold=True),
        para(note, size=12, color=COLORS["navy_soft"]),
    ]
    return build_shape(shape_id, name, BoxSpec(x, y, w, h, paragraphs, fill=COLORS["surface"], line=COLORS["border"], rounded=True))


def build_slides(context: dict[str, object]) -> list[SlideSpec]:
    total = 8
    slides: list[SlideSpec] = []

    report_date = str(context["report_date"])
    lead_summary = context["lead_summary"]
    nev_summary = context["nev_summary"]
    ice_summary = context["ice_summary"]
    arrival_summary = context["arrival_summary"]
    section_counts = context["section_counts"]
    brief_sections = context["brief_sections"]
    summary = context["summary"]

    lead_total = str(lead_summary[0]["displayValue"])
    lead_delta = str(lead_summary[2]["displayValue"])
    lead_day = str(lead_summary[3]["displayValue"])
    nev_total = str(nev_summary[1]["displayValue"])
    nev_achieve = str(nev_summary[2]["displayValue"])
    nev_day = str(nev_summary[4]["displayValue"])
    ice_total = str(ice_summary[1]["displayValue"])
    ice_note = str(ice_summary[2].get("note") or "累计环比待补充")
    ice_day = str(ice_summary[4]["displayValue"])
    arrival_total = str(arrival_summary[0]["displayValue"])
    arrival_yoy = str(arrival_summary[2]["displayValue"])
    arrival_day = str(arrival_summary[3]["displayValue"])

    generated_at = fmt_dt(str(summary["generatedAt"]))
    workbook_modified = fmt_dt(str(summary["inputs"]["workbookModifiedAt"]))
    arrival_modified = fmt_dt(str(summary["inputs"]["arrivalWorkbookModifiedAt"]))
    dashboard_status = str(context["dashboard_status"])

    nev_brief = str(brief_sections[1]["lines"][0])
    sylphy_brief = str(brief_sections[2]["lines"][0])
    arrival_brief = str(brief_sections[3]["lines"][0])

    quality_line_one = "线索简报改为按底层数据重建"
    quality_line_two = "来店简报改为按 4 张底表聚合"

    # Slide 1
    elements, sid = base_slide(1, total, "AI DIGEST / 效果呈现", "AI Digest Dashboard 项目效果呈现", "把 Excel 线索与来店日报，变成可直接分享的 Web 看板")
    elements.append(build_shape(sid, "Hero Accent", BoxSpec(0.72, 1.84, 0.12, 2.7, [], fill=COLORS["red"], line=None, tx_box=False)))
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Hero Copy",
            BoxSpec(
                0.98,
                1.86,
                6.18,
                2.75,
                [
                    para("项目真正的价值，不是把日报做得更花，而是把“看数据”这件事从文件搬运改成浏览器直达。", size=24, color=COLORS["navy"], bold=True),
                    para("当前版本已经把 NEV / ICE 线索和全国来店日报收束成 5 个 dashboard，适合晨会、日报和经营复盘直接使用。", size=16, color=COLORS["navy_soft"]),
                    para(f"以下内容基于 {report_date} 的最新报表快照整理。", size=14, color=COLORS["muted"]),
                ],
                fill=None,
                line=None,
            ),
        )
    )
    sid += 1
    elements.append(
        card(
            sid,
            "Cover Right",
            7.38,
            1.8,
            5.14,
            2.92,
            "这套产物现在能直接带来的变化",
            [
                "日报查看从 Excel 文件切换成浏览器链接。",
                "领导、运营和区域团队看到的是同一套口径。",
                "线索、车型、来店不再分散在多张表里来回翻。",
                "更新动作被压缩成固定流程，传播成本更低。",
            ],
            fill=COLORS["surface"],
            line=COLORS["border"],
        )
    )
    sid += 1
    elements.append(metric_card(sid, "Cover Stat 1", 0.72, 5.42, 2.66, 1.15, "Dashboard", f"{context['dashboard_count']} 个", "简报 / 线索 / 来店一屏收口", accent=COLORS["red"]))
    sid += 1
    elements.append(metric_card(sid, "Cover Stat 2", 3.54, 5.42, 2.66, 1.15, "累计线索", lead_total, f"累计环比 {lead_delta}", accent=COLORS["navy"]))
    sid += 1
    elements.append(metric_card(sid, "Cover Stat 3", 6.36, 5.42, 2.66, 1.15, "累计来店", arrival_total, f"同比 {arrival_yoy}", accent=COLORS["green"]))
    sid += 1
    elements.append(metric_card(sid, "Cover Stat 4", 9.18, 5.42, 3.34, 1.15, "最新报表", report_date, f"数据范围 {context['data_start']} 至 {context['data_end']}", accent=COLORS["amber"]))
    slides.append(SlideSpec("封面", elements))

    # Slide 2
    elements, sid = base_slide(2, total, "01 / 价值变化", "从日报搬运，到一屏看懂", "别拿 PPT 说空话，先把使用前后的差别摆在桌面上")
    elements.append(card(sid, "Before", 0.72, 1.92, 5.2, 2.72, "过去：数据在文件里，信息在人脑里", [
        "晨会前要在多张 Excel 之间来回切换。",
        "线索、车型、来店分散在不同页签，解释成本高。",
        "分享给别人时，通常只能截屏、复制文案或口头转述。",
        "同一份日报，看的人越多，重复搬运越多。",
    ], fill=COLORS["red_soft"], title_color=COLORS["red"], body_color=COLORS["navy_soft"]))
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Transition",
            BoxSpec(5.98, 2.78, 1.08, 0.52, [para("转成浏览器视图", size=13, color=COLORS["white"], bold=True, align="ctr")], fill=COLORS["navy"], line=None, rounded=True),
        )
    )
    sid += 1
    elements.append(card(sid, "After", 7.32, 1.92, 5.2, 2.72, "现在：信息在页面里，结论在眼前", [
        "打开链接就能看到简报、线索总控、NEV、ICE、来店 5 类视图。",
        "累计值、当日值、同比 / 环比与车型拆分可以同步对照。",
        "同一份内容适合领导查阅、运营复盘和区域同步。",
        "页面本身就是展示物，不需要再额外做一次“汇报版”。",
    ], fill=COLORS["green_soft"], title_color=COLORS["green"], body_color=COLORS["navy_soft"]))
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Value Band",
            BoxSpec(0.72, 4.98, 11.8, 0.76, [para("这不是重做系统，而是把日报的展示链路跑顺，让“数据可看、可讲、可分享”变成默认状态。", size=16, color=COLORS["white"], bold=True, align="ctr")], fill=COLORS["navy"], line=None, rounded=True),
        )
    )
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Share",
            BoxSpec(
                0.72,
                5.94,
                3.72,
                0.78,
                [para("分享方式", size=14, color=COLORS["navy"], bold=True, align="ctr"), para("浏览器链接替代截图转发", size=12, color=COLORS["muted"], align="ctr")],
                fill=COLORS["surface"],
                line=COLORS["border"],
                rounded=True,
            ),
        )
    )
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Consistency",
            BoxSpec(
                4.76,
                5.94,
                3.72,
                0.78,
                [para("口径统一", size=14, color=COLORS["navy"], bold=True, align="ctr"), para("简报、看板和来店来自同一批数据", size=12, color=COLORS["muted"], align="ctr")],
                fill=COLORS["surface_alt"],
                line=COLORS["border"],
                rounded=True,
            ),
        )
    )
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Audience",
            BoxSpec(
                8.8,
                5.94,
                3.72,
                0.78,
                [para("适用对象", size=14, color=COLORS["navy"], bold=True, align="ctr"), para("领导晨会、运营复盘、跨部门同步", size=12, color=COLORS["muted"], align="ctr")],
                fill=COLORS["surface"],
                line=COLORS["border"],
                rounded=True,
            ),
        )
    )
    slides.append(SlideSpec("价值变化", elements))

    # Slide 3
    elements, sid = base_slide(3, total, "02 / 页面观感", "页面效果长这样：像个真能用的仪表盘", "这页不讲代码，直接讲使用者第一次打开页面会看到什么")
    elements.append(build_shape(sid, "Browser Frame", BoxSpec(0.72, 1.78, 11.8, 4.92, [], fill=COLORS["surface"], line=COLORS["border"], tx_box=False)))
    sid += 1
    elements.append(build_shape(sid, "Browser Top", BoxSpec(0.72, 1.78, 11.8, 0.44, [], fill=COLORS["surface_alt"], line=None, tx_box=False)))
    sid += 1
    for idx, x in enumerate([0.96, 1.18, 1.40]):
        color = [COLORS["red"], COLORS["amber"], COLORS["green"]][idx]
        elements.append(build_shape(sid, f"Dot {idx}", BoxSpec(x, 1.93, 0.12, 0.12, [], fill=color, line=None, rounded=True, tx_box=False)))
        sid += 1
    elements.append(
        build_shape(
            sid,
            "Address",
            BoxSpec(1.78, 1.88, 3.62, 0.22, [para("AI Digest Dashboard / 2026-04-14", size=11, color=COLORS["muted"], align="ctr")], fill=COLORS["white"], line=COLORS["border"], rounded=True),
        )
    )
    sid += 1
    elements.append(build_shape(sid, "Sidebar", BoxSpec(0.98, 2.38, 2.14, 3.98, [], fill=COLORS["surface_alt"], line=None, tx_box=False)))
    sid += 1
    elements.append(build_shape(sid, "Sidebar Title", BoxSpec(1.16, 2.58, 1.78, 0.34, [para("Dashboard", size=13, color=COLORS["navy"], bold=True)], fill=None, line=None)))
    sid += 1
    for text, y, active in [
        ("每日简报", 2.98, False),
        ("线索总控", 3.46, False),
        ("NEV 线索", 3.94, True),
        ("ICE 线索", 4.42, False),
        ("全国来店", 4.90, False),
    ]:
        fill = COLORS["navy"] if active else COLORS["surface"]
        text_color = COLORS["white"] if active else COLORS["navy"]
        elements.append(
            build_shape(
                sid,
                f"Tab {text}",
                BoxSpec(1.16, y, 1.78, 0.28, [para(text, size=12, color=text_color, bold=active, align="ctr")], fill=fill, line=None, rounded=True),
            )
        )
        sid += 1
    elements.append(
        build_shape(
            sid,
            "Main Header",
            BoxSpec(3.42, 2.42, 4.9, 0.5, [para("NEV 线索看板", size=20, color=COLORS["navy"], bold=True), para("总盘 + 分车型趋势 + 指标卡一屏可读", size=12, color=COLORS["muted"])], fill=None, line=None),
        )
    )
    sid += 1
    elements.append(metric_card(sid, "Mock Stat 1", 3.42, 2.98, 2.32, 0.96, "累计线索", lead_total, f"环比 {lead_delta}", accent=COLORS["red"]))
    sid += 1
    elements.append(metric_card(sid, "Mock Stat 2", 5.92, 2.98, 2.32, 0.96, "NEV 累计实绩", nev_total, f"达成 {nev_achieve}", accent=COLORS["navy"]))
    sid += 1
    elements.append(metric_card(sid, "Mock Stat 3", 8.42, 2.98, 2.32, 0.96, "累计来店", arrival_total, f"同比 {arrival_yoy}", accent=COLORS["green"]))
    sid += 1
    elements.append(card(sid, "Chart Shell", 3.42, 4.16, 5.06, 2.08, "趋势图区域", [
        "红色柱形代表本期实绩",
        "浅色参照代表目标 / 同期",
        "点击图表可放大查看月度走势",
    ], fill=COLORS["white"]))
    sid += 1
    for idx, (x, y, w, h, fill) in enumerate([
        (3.74, 5.66, 0.32, 0.30, COLORS["surface_alt"]),
        (4.18, 5.28, 0.32, 0.68, COLORS["red"]),
        (4.62, 5.0, 0.32, 0.96, COLORS["surface_alt"]),
        (5.06, 4.72, 0.32, 1.24, COLORS["red"]),
        (5.50, 5.12, 0.32, 0.84, COLORS["surface_alt"]),
        (5.94, 4.54, 0.32, 1.42, COLORS["red"]),
    ]):
        elements.append(build_shape(sid, f"Bar {idx}", BoxSpec(x, y, w, h, [], fill=fill, line=None, tx_box=False)))
        sid += 1
    elements.append(card(sid, "Table Shell", 8.72, 4.16, 2.9, 2.08, "车型拆分", [
        "NX8：79,641",
        "N7：31,777",
        "N6：30,495",
        "天籁·鸿蒙：38,993",
    ], fill=COLORS["surface_alt"], title_color=COLORS["navy"]))
    sid += 1
    slides.append(SlideSpec("页面观感", elements))

    # Slide 4
    elements, sid = base_slide(4, total, "03 / 看板矩阵", "一套数据，拆成 5 个决策视角", "页面不是一张大拼图，而是围绕不同使用场景拆出来的 5 类视图")
    for (title, lines, fill), (x, y, w, h) in zip(
        [
            ("每日简报", ["适合晨会口播", "自动整理 NEV / 轩逸 / 来店摘要"], COLORS["surface"]),
            ("全车线索总控", ["累计值、当日值、环比同屏", "先看总盘，再决定追哪块"], COLORS["surface_alt"]),
            ("NEV 看板", [f"覆盖 {' / '.join(context['nev_sections'])}", "总盘 + 车型分段追达成"], COLORS["surface"]),
            ("ICE 看板", [f"覆盖 {' / '.join(context['ice_sections'])}", "总盘外加十五代轩逸重点看"], COLORS["surface_alt"]),
            ("全国来店", ["累计 / 当日 / NEV vs ICE 结构", "适合看门店流量和结构变化"], COLORS["surface"]),
        ],
        [
            (0.72, 1.96, 3.48, 1.86),
            (4.46, 1.96, 3.48, 1.86),
            (8.2, 1.96, 4.32, 1.86),
            (0.72, 4.2, 5.78, 1.92),
            (6.74, 4.2, 5.78, 1.92),
        ],
    ):
        elements.append(card(sid, title, x, y, w, h, title, lines, fill=fill))
        sid += 1
    elements.append(
        build_shape(
            sid,
            "Matrix Footer",
            BoxSpec(0.72, 6.34, 11.8, 0.44, [para(f"当前覆盖 {context['dashboard_count']} 个 dashboard；NEV {section_counts['nev']} 段，ICE {section_counts['ice']} 段，来店 {section_counts['arrival']} 段。", size=15, color=COLORS["white"], bold=True, align="ctr")], fill=COLORS["navy"], line=None, rounded=True),
        )
    )
    slides.append(SlideSpec("看板矩阵", elements))

    # Slide 5
    elements, sid = base_slide(5, total, "04 / 最新快照", "以 2026-04-14 报表为例，页面能直接交付什么", "这页就是成果物本身，数字、摘要和新鲜度都能直接拿去汇报")
    elements.append(metric_card(sid, "Snapshot 1", 0.72, 1.92, 2.74, 1.58, "全车有效线索", lead_total, f"累计环比 {lead_delta}；当日 {lead_day}", accent=COLORS["red"]))
    sid += 1
    elements.append(metric_card(sid, "Snapshot 2", 3.64, 1.92, 2.74, 1.58, "NEV 累计实绩", nev_total, f"累计达成 {nev_achieve}；当日 {nev_day}", accent=COLORS["navy"]))
    sid += 1
    elements.append(metric_card(sid, "Snapshot 3", 6.56, 1.92, 2.74, 1.58, "ICE 累计实绩", ice_total, f"{ice_note}；当日 {ice_day}", accent=COLORS["amber"]))
    sid += 1
    elements.append(metric_card(sid, "Snapshot 4", 9.48, 1.92, 3.04, 1.58, "累计来店", arrival_total, f"同比 {arrival_yoy}；当日 {arrival_day}", accent=COLORS["green"]))
    sid += 1
    elements.append(card(sid, "Brief Snapshot", 0.72, 3.86, 7.16, 2.22, "今日简报摘录", [nev_brief, sylphy_brief, arrival_brief], fill=COLORS["surface"]))
    sid += 1
    elements.append(card(sid, "Freshness", 8.12, 3.86, 4.4, 1.14, "数据新鲜度", [
        f"线索源文件更新时间：{workbook_modified}",
        f"来店源文件更新时间：{arrival_modified}",
    ], fill=COLORS["surface_alt"]))
    sid += 1
    elements.append(card(sid, "Delivery State", 8.12, 5.12, 4.4, 1.14, "交付状态", [
        f"最近一次生成：{generated_at}",
        f"当前产物状态：{dashboard_status}",
    ], fill=COLORS["surface"]))
    slides.append(SlideSpec("最新快照", elements))

    # Slide 6
    elements, sid = base_slide(6, total, "05 / 使用效果", "对使用者来说，价值不在技术，而在决策速度", "真正有用的地方，是把“看到数据”和“理解重点”之间那层摩擦砍掉")
    for (title, lines, fill), (x, y) in zip(
        [
            ("领导看得快", ["关键指标先上卡片", "不需要先听人解释再看数字"], COLORS["surface"]),
            ("晨会讲得顺", ["简报文案可直接复用", "减少临场拼句子的尴尬"], COLORS["surface_alt"]),
            ("区域拆得开", ["NEV / ICE / 车型 / 来店分层可看", "适合快速定位问题位置"], COLORS["surface"]),
            ("分享成本低", ["链接就能传，不必重复截图", "跨部门同步时更像正式产物"], COLORS["surface_alt"]),
            ("口径更统一", [quality_line_one, quality_line_two], COLORS["surface"]),
            ("移动端也能看", ["页面支持图表放大查看", "窄屏场景仍能横向浏览"], COLORS["surface_alt"]),
        ],
        [
            (0.72, 1.94),
            (4.4, 1.94),
            (8.08, 1.94),
            (0.72, 4.2),
            (4.4, 4.2),
            (8.08, 4.2),
        ],
    ):
        elements.append(card(sid, title, x, y, 3.35, 1.86, title, lines, fill=fill))
        sid += 1
    slides.append(SlideSpec("使用效果", elements))

    # Slide 7
    elements, sid = base_slide(7, total, "06 / 更新传播", "日常更新动作，被压缩成一条轻量流程", "只要业务数据更新，这个页面就能跟着刷新，而不是再来一轮手工加工")
    step_titles = ["1. 更新日报", "2. 刷新数据", "3. 浏览预览", "4. 发布链接", "5. 统一查看"]
    step_lines = [
        ["线索 / 来店仍在 Excel 维护", "保留原来的业务习惯"],
        ["重建最新看板数据", "把日报转成统一页面内容"],
        ["浏览器先看效果", "确认本次日报是否正常"],
        ["把最新结果发到 Pages", "共享成本低很多"],
        ["领导 / 运营 / 区域看同一页", "减少反复解释口径"],
    ]
    x_positions = [0.72, 3.08, 5.44, 7.8, 10.16]
    for index, x in enumerate(x_positions):
        elements.append(card(sid, f"Step {index}", x, 2.1, 2.04, 2.18, step_titles[index], step_lines[index], fill=COLORS["surface"]))
        sid += 1
        if index < len(x_positions) - 1:
            elements.append(
                build_shape(
                    sid,
                    f"Step Arrow {index}",
                    BoxSpec(x + 2.0, 2.94, 0.22, 0.28, [para(">", size=18, color=COLORS["red"], bold=True, align="ctr")], fill=None, line=None, margin_left=0, margin_right=0, margin_top=0, margin_bottom=0, anchor="ctr"),
                )
            )
            sid += 1
    elements.append(card(sid, "Process Meaning", 0.72, 4.76, 6.02, 1.46, "这意味着什么", [
        "日报更新开始具备固定动作和固定出口，不再依赖谁临时整理得更快。",
        "页面本身既是查看端，也是传播端，少了一层“再转述一次”的损耗。",
    ], fill=COLORS["surface_alt"]))
    sid += 1
    elements.append(card(sid, "Boundary", 6.98, 4.76, 5.54, 1.46, "当前边界", [
        "它更适合读多写少的展示场景，不是业务录入系统。",
        "Excel 必须先完成重算并保存，否则页面会沿用旧缓存结果。",
    ], fill=COLORS["surface"]))
    slides.append(SlideSpec("更新传播", elements))

    # Slide 8
    elements, sid = base_slide(8, total, "07 / 结论", "这不是炫技型 PPT，而是已经能拿来汇报的日报展示物", "最后别整虚的，直接给能拍板的话")
    elements.append(card(sid, "Conclusion Main", 0.72, 1.92, 7.0, 4.38, "结论", [
        "1. AI Digest 已经把 Excel 日报变成浏览器可读、可讲、可分享的页面产物。",
        "2. 当前版本稳定承接 5 个 dashboard，覆盖线索总盘、NEV、ICE、来店与简报场景。",
        f"3. 以 {report_date} 快照为例，页面可以直接支撑 {lead_total} 线索、{arrival_total} 来店的汇报展示。",
        "4. 真正值得继续投入的方向，是让数据口径更稳、展示链路更顺，而不是急着上重平台。",
    ], fill=COLORS["surface"], title_color=COLORS["navy"]))
    sid += 1
    elements.append(card(sid, "Good Fit", 8.02, 1.92, 4.5, 1.22, "最适合的场景", [
        "领导查阅 / 晨会播报",
        "经营复盘 / 跨部门同步",
    ], fill=COLORS["surface_alt"], title_color=COLORS["red"]))
    sid += 1
    elements.append(card(sid, "Current Boundary", 8.02, 3.38, 4.5, 1.12, "当前边界", [
        "读多写少的展示物",
        "依赖 Excel 已保存数据，不承担权限审批",
    ], fill=COLORS["surface"], title_color=COLORS["amber"]))
    sid += 1
    elements.append(card(sid, "Next Step", 8.02, 4.72, 4.5, 1.58, "下一步值得补强", [
        quality_line_one,
        quality_line_two,
        "再补历史快照与页面 smoke 检查，整体就更稳了。",
    ], fill=COLORS["green_soft"], title_color=COLORS["green"]))
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Close Band",
            BoxSpec(0.72, 6.5, 11.8, 0.42, [para("建议方向：保留当前轻量发布形态，把重点放在数据可信度和汇报体验的持续加固上。", size=16, color=COLORS["white"], bold=True, align="ctr")], fill=COLORS["red"], line=None, rounded=True),
        )
    )
    slides.append(SlideSpec("结论", elements))

    return slides


def update_content_types(xml_bytes: bytes, slide_count: int) -> bytes:
    ET.register_namespace("", NS_CONTENT_TYPES)
    root = ET.fromstring(xml_bytes)
    for child in root.findall(qn(NS_CONTENT_TYPES, "Override")):
        if child.attrib.get("PartName") == "/ppt/presentation.xml":
            child.set("ContentType", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")

    existing = {child.attrib.get("PartName") for child in root.findall(qn(NS_CONTENT_TYPES, "Override"))}
    slide_type = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
    for slide_no in range(1, slide_count + 1):
        part = f"/ppt/slides/slide{slide_no}.xml"
        if part not in existing:
            override = ET.Element(qn(NS_CONTENT_TYPES, "Override"))
            override.set("PartName", part)
            override.set("ContentType", slide_type)
            root.append(override)

    return XML_DECL.encode("utf-8") + ET.tostring(root, encoding="utf-8")


def build_presentation_xml(slide_count: int) -> bytes:
    slide_ids = "".join(f"<p:sldId id=\"{256 + index}\" r:id=\"rId{2 + index}\"/>" for index in range(slide_count))
    return (
        f"{XML_DECL}"
        f"<p:presentation xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        f"xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        f"xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
        f"removePersonalInfoOnSave=\"1\" saveSubsetFonts=\"1\">"
        f"<p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rId1\"/></p:sldMasterIdLst>"
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f"<p:sldSz cx=\"{SLIDE_W}\" cy=\"{SLIDE_H}\"/>"
        f"<p:notesSz cx=\"6858000\" cy=\"9144000\"/>"
        f"<p:defaultTextStyle>"
        f"<a:defPPr><a:defRPr lang=\"en-US\"/></a:defPPr>"
        f"<a:lvl1pPr marL=\"0\" algn=\"l\" defTabSz=\"914400\" rtl=\"0\" eaLnBrk=\"1\" latinLnBrk=\"0\" hangingPunct=\"1\">"
        f"<a:defRPr sz=\"1800\" kern=\"1200\"><a:solidFill><a:schemeClr val=\"tx1\"/></a:solidFill>"
        f"<a:latin typeface=\"+mn-lt\"/><a:ea typeface=\"+mn-ea\"/><a:cs typeface=\"+mn-cs\"/></a:defRPr></a:lvl1pPr>"
        f"</p:defaultTextStyle>"
        f"</p:presentation>"
    ).encode("utf-8")


def build_presentation_rels_xml(slide_count: int) -> bytes:
    slide_rels = "".join(
        f"<Relationship Id=\"rId{2 + index}\" "
        f"Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" "
        f"Target=\"slides/slide{1 + index}.xml\"/>"
        for index in range(slide_count)
    )
    xml_text = (
        f"{XML_DECL}"
        f"<Relationships xmlns=\"{NS_REL}\">"
        f"<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>"
        f"{slide_rels}"
        f"<Relationship Id=\"rId{slide_count + 2}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps\" Target=\"presProps.xml\"/>"
        f"<Relationship Id=\"rId{slide_count + 3}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps\" Target=\"viewProps.xml\"/>"
        f"<Relationship Id=\"rId{slide_count + 4}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"theme/theme1.xml\"/>"
        f"<Relationship Id=\"rId{slide_count + 5}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles\" Target=\"tableStyles.xml\"/>"
        f"</Relationships>"
    )
    return xml_text.encode("utf-8")


def build_app_xml(slides: list[SlideSpec]) -> bytes:
    titles = ["Office Theme", *[slide.title for slide in slides]]
    titles_xml = "".join(f"<vt:lpstr>{escape(item)}</vt:lpstr>" for item in titles)
    xml_text = (
        f"{XML_DECL}"
        f"<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
        f"xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
        f"<Application>Microsoft Office PowerPoint</Application>"
        f"<PresentationFormat>Screen</PresentationFormat>"
        f"<Slides>{len(slides)}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><MMClips>0</MMClips>"
        f"<ScaleCrop>false</ScaleCrop>"
        f"<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\">"
        f"<vt:variant><vt:lpstr>Theme</vt:lpstr></vt:variant>"
        f"<vt:variant><vt:i4>1</vt:i4></vt:variant>"
        f"</vt:vector></HeadingPairs>"
        f"<TitlesOfParts><vt:vector size=\"{len(titles)}\" baseType=\"lpstr\">{titles_xml}</vt:vector></TitlesOfParts>"
        f"<Company></Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc>"
        f"<HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0000</AppVersion>"
        f"</Properties>"
    )
    return xml_text.encode("utf-8")


def build_core_xml() -> bytes:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    xml_text = (
        f"{XML_DECL}"
        f"<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        f"xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
        f"xmlns:dcterms=\"http://purl.org/dc/terms/\" "
        f"xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" "
        f"xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        f"<dc:title>AI Digest Dashboard 项目效果呈现</dc:title>"
        f"<dc:creator>OpenAI Codex</dc:creator>"
        f"<cp:lastModifiedBy>OpenAI Codex</cp:lastModifiedBy>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
        f"</cp:coreProperties>"
    )
    return xml_text.encode("utf-8")


def write_presentation(template_path: Path, output_path: Path) -> Path:
    context = load_context()
    slides = build_slides(context)
    slide_count = len(slides)

    with zipfile.ZipFile(template_path, "r") as source:
        content_types = update_content_types(source.read("[Content_Types].xml"), slide_count)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        skip_entries = {"[Content_Types].xml", "docProps/app.xml", "docProps/core.xml", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"}
        skip_entries.update({f"ppt/slides/slide{index}.xml" for index in range(1, 100)})
        skip_entries.update({f"ppt/slides/_rels/slide{index}.xml.rels" for index in range(1, 100)})

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                if item.filename in skip_entries:
                    continue
                target.writestr(item, source.read(item.filename))

            target.writestr("[Content_Types].xml", content_types)
            target.writestr("docProps/app.xml", build_app_xml(slides))
            target.writestr("docProps/core.xml", build_core_xml())
            target.writestr("ppt/presentation.xml", build_presentation_xml(slide_count))
            target.writestr("ppt/_rels/presentation.xml.rels", build_presentation_rels_xml(slide_count))

            for slide_no, slide in enumerate(slides, start=1):
                target.writestr(f"ppt/slides/slide{slide_no}.xml", make_slide_xml(slide.elements))
                target.writestr(f"ppt/slides/_rels/slide{slide_no}.xml.rels", make_slide_rels())

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a showcase PPTX for the AI Digest dashboard.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to a base POTX/PPTX template.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output PPTX path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template_path = Path(args.template)
    output_path = Path(args.out)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    result = write_presentation(template_path, output_path)
    print(f"presentation written: {result}")
    print(f"source data: {DASHBOARD_JSON}")
    print(f"summary data: {SUMMARY_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
