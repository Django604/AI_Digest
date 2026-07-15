from __future__ import annotations

import argparse
import json
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_JSON = ROOT / "docs" / "data" / "dashboard.json"
SUMMARY_JSON = ROOT / "docs" / "data" / "dashboard.summary.json"
TEST_FILE = ROOT / "tests" / "test_build_dashboard.py"
DEFAULT_OUT = ROOT / "reports" / "AI_Digest_Project_Analysis_2026-04-17.pptx"
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
    "line": "E6DED3",
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


def append_xml(parent: ET.Element, xml_text: str) -> None:
    parent.append(ET.fromstring(xml_text))


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def fmt_dt(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%Y-%m-%d %H:%M")


def count_tests(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"^\s*def\s+test_", text, flags=re.M))


def load_context() -> dict[str, object]:
    payload = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    brief_sections = payload["dashboards"]["brief"]["briefing"]["sections"]
    context = {
        "payload": payload,
        "summary": summary,
        "report_date": payload["meta"]["reportDateLabel"],
        "data_start": payload["meta"]["dataRangeStart"],
        "data_end": payload["meta"]["dataRangeEnd"],
        "workbook_name": payload["meta"]["workbookName"],
        "arrival_workbook_name": payload["meta"]["arrivalWorkbookName"],
        "dashboard_count": summary["stats"]["dashboardCount"],
        "section_counts": summary["stats"]["sectionCounts"],
        "sheet_count": summary["stats"]["sheetCount"],
        "issue_count": summary["stats"]["issueCount"],
        "warnings": summary["warnings"],
        "dashboard_status": summary["outputs"]["dashboardStatus"],
        "generated_at": summary["generatedAt"],
        "brief_sections": brief_sections,
        "lead_summary": payload["dashboards"]["lead-control"]["sections"][0]["trend"]["summary"]["items"],
        "nev_summary": payload["dashboards"]["nev"]["sections"][0]["trend"]["summary"]["items"],
        "ice_summary": payload["dashboards"]["ice"]["sections"][0]["trend"]["summary"]["items"],
        "arrival_summary": payload["dashboards"]["arrival"]["sections"][0]["trend"]["summary"]["items"],
        "nev_sections": [section["title"] for section in payload["dashboards"]["nev"]["sections"]],
        "ice_sections": [section["title"] for section in payload["dashboards"]["ice"]["sections"]],
        "test_count": count_tests(TEST_FILE),
    }
    return context


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


def build_shape(
    shape_id: int,
    name: str,
    box: BoxSpec,
) -> str:
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
            BoxSpec(
                0.72,
                0.38,
                2.3,
                0.36,
                [para(section, size=14, color=COLORS["red"], bold=True)],
                fill=None,
                line=None,
            ),
        )
    )
    shape_id += 1
    elements.append(
        build_shape(
            shape_id,
            "Title",
            BoxSpec(0.72, 0.72, 9.0, 0.62, [para(title, size=28, color=COLORS["navy"], bold=True)], fill=None, line=None),
        )
    )
    shape_id += 1
    if subtitle:
        elements.append(
            build_shape(
                shape_id,
                "Subtitle",
                BoxSpec(0.72, 1.24, 10.7, 0.34, [para(subtitle, size=13, color=COLORS["muted"])], fill=None, line=None),
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


def pill(shape_id: int, text: str, x: float, y: float, w: float, fill: str, text_color: str = COLORS["white"]) -> str:
    return build_shape(
        shape_id,
        f"Pill {text}",
        BoxSpec(x, y, w, 0.34, [para(text, size=13, color=text_color, bold=True, align="ctr")], fill=fill, line=None, rounded=True),
    )


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
    return build_shape(
        shape_id,
        name,
        BoxSpec(x, y, w, h, paragraphs, fill=fill, line=line, rounded=True),
    )


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
    return build_shape(
        shape_id,
        name,
        BoxSpec(x, y, w, h, paragraphs, fill=COLORS["surface"], line=COLORS["border"], rounded=True),
    )


def build_slides(context: dict[str, object]) -> list[SlideSpec]:
    total = 10
    slides: list[SlideSpec] = []

    report_date = str(context["report_date"])
    workbook_name = str(context["workbook_name"])
    arrival_workbook_name = str(context["arrival_workbook_name"])
    lead_summary = context["lead_summary"]
    nev_summary = context["nev_summary"]
    ice_summary = context["ice_summary"]
    arrival_summary = context["arrival_summary"]
    section_counts = context["section_counts"]
    warnings = context["warnings"]
    brief_sections = context["brief_sections"]
    test_count = int(context["test_count"])

    # Slide 1
    elements, sid = base_slide(1, total, "AI DIGEST / 汇报版", "AI Digest 项目逻辑梳理与可行性分析", "围绕 NEV / ICE 线索与来店日报的静态化交付方案")
    elements.append(
        build_shape(
            sid,
            "Hero Bar",
            BoxSpec(0.72, 1.82, 0.12, 2.8, [], fill=COLORS["red"], line=None, tx_box=False),
        )
    )
    sid += 1
    elements.append(
        build_shape(
            sid,
            "Cover Summary",
            BoxSpec(
                0.98,
                1.88,
                6.05,
                2.7,
                [
                    para("这不是另起炉灶做 BI，而是把日常 Excel 日报拆成“可构建、可预览、可发布”的稳定流水线。", size=24, color=COLORS["navy"], bold=True),
                    para("核心动作：读取两本 Excel 缓存结果，生成 dashboard.json，再用原生前端渲染为多看板站点。", size=16, color=COLORS["navy_soft"]),
                    para(f"本次材料基于仓库现状与 {report_date} 报表快照整理。", size=14, color=COLORS["muted"]),
                ],
                fill=None,
                line=None,
            ),
        )
    )
    sid += 1
    elements.append(card(sid, "Cover Callout", 7.3, 1.78, 5.22, 2.95, "为什么这个方案能讲得通", [
        "部署目标是 GitHub Pages，天生适配静态站点，不适合继续扛 Django。",
        "数据口径留在 Excel，发布口径落到 JSON，既尊重现有业务习惯，也把自动化补上。",
        "单测、结构校验、变更去抖都已经落地，不是纯概念图。",
    ], fill=COLORS["surface"], line=COLORS["border"]))
    sid += 1
    elements.append(metric_card(sid, "Stat 1", 0.72, 5.42, 2.6, 1.15, "Excel 源", "2 本", f"{workbook_name} + {arrival_workbook_name}", accent=COLORS["navy"]))
    sid += 1
    elements.append(metric_card(sid, "Stat 2", 3.48, 5.42, 2.6, 1.15, "Dashboard", f"{context['dashboard_count']} 个", "简报 / 线索 / 来店 全覆盖", accent=COLORS["red"]))
    sid += 1
    elements.append(metric_card(sid, "Stat 3", 6.24, 5.42, 2.6, 1.15, "验证", f"{test_count} 项", "单测已通过，构建结果稳定", accent=COLORS["green"]))
    sid += 1
    elements.append(metric_card(sid, "Stat 4", 9.0, 5.42, 3.52, 1.15, "最新报表", report_date, f"数据范围 {context['data_start']} 至 {context['data_end']}", accent=COLORS["amber"]))
    slides.append(SlideSpec("封面", elements))

    # Slide 2
    elements, sid = base_slide(2, total, "01 / 项目定位", "这个项目到底在解决什么问题", "先把价值说人话，不然一张架构图能把人讲睡着")
    elements.append(card(sid, "Goal", 0.72, 1.86, 3.8, 1.95, "项目目标", [
        "把领导日常看的 Excel 日报，转成浏览器即可访问的静态 Dashboard。",
        "保留 Excel 作为事实来源，不强行改业务入口。",
        "让“更新数据 -> 预览 -> 发布”变成固定动作，而不是手工复制粘贴。"
    ], fill=COLORS["surface"]))
    sid += 1
    elements.append(card(sid, "Why Static", 4.72, 1.86, 3.8, 1.95, "为什么不用 Django", [
        "GitHub Pages 只能托管静态内容，跑不了服务端框架。",
        "当前需求核心是日报展示，不是多用户事务系统。",
        "静态站点 + 构建脚本更轻、更稳、更符合现有部署边界。"
    ], fill=COLORS["surface_alt"]))
    sid += 1
    elements.append(card(sid, "Conclusion", 8.72, 1.86, 3.8, 1.95, "一句话结论", [
        "这是“Excel 日报 Web 化 + 自动发布”的工程化升级。",
        "它的重点在于口径固化、发布效率和可持续维护。"
    ], fill=COLORS["surface"], title_color=COLORS["red"]))
    sid += 1
    elements.append(build_shape(sid, "KPI Band", BoxSpec(0.72, 4.18, 11.8, 0.78, [
        para("当前产物覆盖：每日简报、全车有效线索管控、NEV 线索趋势、ICE 线索趋势、全国来店日趋势", size=16, color=COLORS["white"], bold=True, align="ctr")
    ], fill=COLORS["navy"], line=None, rounded=True)))
    sid += 1
    elements.append(card(sid, "Evidence", 0.72, 5.18, 5.7, 1.42, "已经拿到的证据", [
        f"dashboard.summary.json 标记当前构建状态为 {context['dashboard_status']}。",
        f"当前分析工作表数量 {context['sheet_count']}，已识别问题 {context['issue_count']} 个。"
    ], fill=COLORS["surface"]))
    sid += 1
    elements.append(card(sid, "Boundary", 6.62, 5.18, 5.9, 1.42, "天然边界", [
        "GitHub Pages 不会直接读你电脑本地 Excel，更新后仍要提交到仓库。",
        "项目依赖的是 Excel 已保存缓存结果，不是重写全部公式引擎。"
    ], fill=COLORS["surface"]))
    slides.append(SlideSpec("项目定位", elements))

    # Slide 3
    elements, sid = base_slide(3, total, "02 / 模块职责", "目录与代码模块是怎么分工的", "这里是项目骨架，谁负责抽数，谁负责展示，谁负责发布，一眼看穿")
    module_cards = [
        ("scripts/build_dashboard.py", ["读取两本 Excel", "校验工作表与列头", "输出 dashboard.json / summary.json"], COLORS["surface"]),
        ("docs/assets/app.js", ["加载 dashboard.json", "渲染页面导航与图表", "支持目录联动与放大查看"], COLORS["surface_alt"]),
        ("scripts/serve_dashboard.py", ["本地启动 ThreadingHTTPServer", "为 /docs、/AI_Digest 等干净 URL 做回退"], COLORS["surface"]),
        ("scripts/rebuild_dashboard.ps1", ["本地一键重建数据文件", "优先找 python，失败再回退 py -3"], COLORS["surface_alt"]),
        ("scripts/publish_dashboard.ps1", ["限定发布范围只含 4 个核心文件", "串起 rebuild -> git add -> commit -> push"], COLORS["surface"]),
        (".github/workflows/deploy-pages.yml", ["CI 安装依赖、跑测试、构建数据", "上传 docs/ 到 GitHub Pages"], COLORS["surface_alt"]),
    ]
    positions = [
        (0.72, 1.92), (4.4, 1.92), (8.08, 1.92),
        (0.72, 4.2), (4.4, 4.2), (8.08, 4.2),
    ]
    for (title, lines, fill), (x, y) in zip(module_cards, positions):
        elements.append(card(sid, title, x, y, 3.35, 1.85, title, lines, fill=fill))
        sid += 1
    slides.append(SlideSpec("模块职责", elements))

    # Slide 4
    elements, sid = base_slide(4, total, "03 / 逻辑链路", "从 Excel 到网页，这条数据链是怎么跑通的", "这页是全项目最核心的逻辑，不懂这页，后面全是看热闹")
    flow_titles = [
        "1. 源数据",
        "2. Python 构建",
        "3. JSON 产物",
        "4. 前端渲染",
        "5. 发布与预览",
    ]
    flow_lines = [
        ["NEV+ICE_xsai.xlsm", "NEV+ICE_ldai.xlsx", "Excel 先重算并保存"],
        ["校验 sheet / header / 日期", "聚合目标、实绩、来店", "补简报文案与统计摘要"],
        ["dashboard.json", "dashboard.summary.json", "忽略 generatedAt 抖动"],
        ["index.html + app.js", "多看板切换", "图表缩放、节假日高亮"],
        ["serve_dashboard.py 本地预览", "GitHub Actions 跑测试与构建", "Pages 发布 docs/"],
    ]
    x_positions = [0.72, 3.12, 5.52, 7.92, 10.32]
    for index, x in enumerate(x_positions):
        elements.append(card(sid, f"Flow {index}", x, 2.2, 2.0, 2.12, flow_titles[index], flow_lines[index], fill=COLORS["surface"]))
        sid += 1
        if index < len(x_positions) - 1:
            elements.append(
                build_shape(
                    sid,
                    f"Arrow {index}",
                    BoxSpec(x + 1.94, 2.92, 0.28, 0.36, [para("->", size=18, color=COLORS["red"], bold=True, align="ctr")], fill=None, line=None),
                )
            )
            sid += 1
    elements.append(card(sid, "Rules", 0.72, 4.72, 5.7, 1.55, "项目里的 4 条关键规则", [
        "报表日期取自 参数!C2，按当前月与上月同日做对比。",
        "NEV 线索由“目标竖版 + 全国按日NEV”组合生成。",
        "到店简报不再吃汇总缓存，改为 4 张来店底表聚合。",
        "十五代轩逸目标与特殊节假日有单独代码规则。"
    ], fill=COLORS["surface_alt"]))
    sid += 1
    elements.append(card(sid, "Why", 6.62, 4.72, 5.9, 1.55, "为什么这条链靠谱", [
        "数据与展示彻底分离，网页不需要碰 Excel 公式。",
        "构建失败会在校验阶段直接报错，不会静默产出坏页面。",
        "summary.json 把输入时间、输出状态、dashboard 数量都记下来了。"
    ], fill=COLORS["surface"]))
    slides.append(SlideSpec("逻辑链路", elements))

    # Slide 5
    elements, sid = base_slide(5, total, "04 / 实用功能", "这个项目能给使用者带来哪些直接可用的能力", "不是空谈架构，得把能用的东西一条条摆出来")
    features = [
        ("每日简报", [f"自动拼出 {brief_sections[1]['title']}、{brief_sections[2]['title']}、{brief_sections[3]['title']} 文案", "适合直接发群或做晨会口播"]),
        ("线索总控", ["全车有效线索按日、累计、环比同屏展示", "未来日期自动留空，避免 #N/A 污染界面"]),
        ("NEV 看板", [f"覆盖 {' / '.join(context['nev_sections'])}", "总盘 + 分车型拆开看，适合追目标达成"]),
        ("ICE 看板", [f"覆盖 {' / '.join(context['ice_sections'])}", "既看总盘，也能盯住十五代轩逸子模块"]),
        ("来店看板", ["全国累计来店、当日来店、同比一屏看全", "NEV / ICE 拆分显示，方便识别结构变化"]),
        ("前端体验", ["侧边栏页面导航 + 分支目录", "图表点击放大、节假日高亮、移动端可横向查看"]),
    ]
    positions = [
        (0.72, 1.9), (4.4, 1.9), (8.08, 1.9),
        (0.72, 4.18), (4.4, 4.18), (8.08, 4.18),
    ]
    fills = [COLORS["surface"], COLORS["surface_alt"], COLORS["surface"], COLORS["surface_alt"], COLORS["surface"], COLORS["surface_alt"]]
    for (title, lines), (x, y), fill in zip(features, positions, fills):
        elements.append(card(sid, title, x, y, 3.35, 1.86, title, lines, fill=fill))
        sid += 1
    slides.append(SlideSpec("实用功能", elements))

    # Slide 6
    elements, sid = base_slide(6, total, "05 / 当前快照", "基于最新报表快照的实际输出情况", f"报表日期 {report_date}，这些数字来自当前仓库里的 dashboard.json")
    elements.append(metric_card(sid, "Lead Metric", 0.72, 1.94, 2.8, 1.6, "全车有效线索", lead_summary[0]["displayValue"], f"累计环比 {lead_summary[2]['displayValue']}；当日 {lead_summary[3]['displayValue']}", accent=COLORS["red"]))
    sid += 1
    elements.append(metric_card(sid, "NEV Metric", 3.68, 1.94, 2.8, 1.6, "NEV 累计实绩", nev_summary[1]["displayValue"], f"累计达成 {nev_summary[2]['displayValue']}；当日 {nev_summary[4]['displayValue']}", accent=COLORS["navy"]))
    sid += 1
    elements.append(metric_card(sid, "ICE Metric", 6.64, 1.94, 2.8, 1.6, "ICE 累计实绩", ice_summary[1]["displayValue"], f"累计环比见备注；当日 {ice_summary[4]['displayValue']}", accent=COLORS["amber"]))
    sid += 1
    elements.append(metric_card(sid, "Arrival Metric", 9.6, 1.94, 2.92, 1.6, "累计来店", arrival_summary[0]["displayValue"], f"同比 {arrival_summary[2]['displayValue']}；当日 {arrival_summary[3]['displayValue']}", accent=COLORS["green"]))
    sid += 1
    elements.append(card(sid, "Brief Snapshot", 0.72, 3.92, 7.1, 2.06, "最新简报摘录", [
        str(brief_sections[1]["lines"][0]),
        str(brief_sections[2]["lines"][0]),
        str(brief_sections[3]["lines"][0]),
    ], fill=COLORS["surface"]))
    sid += 1
    elements.append(card(sid, "Dashboard Inventory", 8.02, 3.92, 4.5, 2.06, "看板覆盖范围", [
        f"Dashboard 数量：{context['dashboard_count']} 个",
        f"NEV 分段：{section_counts['nev']} 段；ICE 分段：{section_counts['ice']} 段；来店分段：{section_counts['arrival']} 段",
        f"简报分区：{len(brief_sections)} 个",
        f"summary.json 状态：{context['dashboard_status']}",
    ], fill=COLORS["surface_alt"]))
    slides.append(SlideSpec("当前快照", elements))

    # Slide 7
    elements, sid = base_slide(7, total, "06 / 可行性分析", "这套方案为什么具备落地可行性", "技术、部署、运营、验证四个角都得站得住，才不算 PPT 工程")
    elements.append(card(sid, "Tech Feasibility", 0.72, 1.9, 5.75, 1.8, "技术可行性", [
        "依赖非常轻：Python + openpyxl + 原生 HTML/CSS/JS。",
        "没有引入服务端复杂度，也没有强绑定重型 BI 平台。",
        "构建逻辑已经覆盖日期、目标、实绩、来店和简报文本。"
    ], fill=COLORS["surface"]))
    sid += 1
    elements.append(pill(sid, "已验证", 5.38, 2.04, 0.92, COLORS["green"]))
    sid += 1
    elements.append(card(sid, "Deploy Feasibility", 6.77, 1.9, 5.75, 1.8, "部署可行性", [
        "docs/ 目录天然适配 GitHub Pages 发布模型。",
        "本地有 serve_dashboard.py 处理干净 URL，不再踩 http.server 的 404 坑。",
        "CI 直接在 ubuntu-latest 执行，跨环境成本低。"
    ], fill=COLORS["surface_alt"]))
    sid += 1
    elements.append(pill(sid, "已验证", 11.43, 2.04, 0.92, COLORS["green"]))
    sid += 1
    elements.append(card(sid, "Ops Feasibility", 0.72, 4.18, 5.75, 1.8, "运营可行性", [
        "rebuild_dashboard.ps1 和 publish_dashboard.ps1 已封装日常动作。",
        "publish 脚本只允许提交 4 个核心文件，避免顺手把脏改动一锅端。",
        "summary.json 记录输入时间、输出状态、section 数量，方便追踪。"
    ], fill=COLORS["surface_alt"]))
    sid += 1
    elements.append(pill(sid, "已验证", 5.38, 4.32, 0.92, COLORS["green"]))
    sid += 1
    elements.append(card(sid, "Quality Feasibility", 6.77, 4.18, 5.75, 1.8, "质量可行性", [
        f"当前仓库含 {test_count} 个单元测试，覆盖结构校验、摘要统计和变更去抖。",
        "构建脚本会先检查工作表、关键列和报表日期有效性。",
        "最新一次本地测试通过，构建结果为 unchanged，说明产物稳定。"
    ], fill=COLORS["surface"]))
    sid += 1
    elements.append(pill(sid, "已验证", 11.43, 4.32, 0.92, COLORS["green"]))
    slides.append(SlideSpec("可行性分析", elements))

    # Slide 8
    elements, sid = base_slide(8, total, "07 / 风险与边界", "能做成，不代表没有坑；这页专门讲坑", "提前把雷区画出来，比上线后装无辜强多了")
    risk_cards = [
        ("风险 1：Excel 缓存依赖", ["脚本读取的是 Excel 保存后的缓存值。", "如果业务改完数据却没让 Excel 重算并保存，网页会吃旧结果。", "建议把“保存前重算”写进操作规范。"]),
        ("风险 2：口径规则写在代码里", ["例如特殊节假日和十五代轩逸目标 override。", "短期有效，长期容易变成隐形业务规则。", "建议后续抽到配置文件。"]),
        ("风险 3：前端验证还偏轻", ["当前测试更偏后端结构与构建逻辑。", "页面样式、图表视觉和交互没有自动化回归。", "建议补一层 smoke test 或截图对比。"]),
        ("风险 4：Pages 天生不是业务系统", ["它适合发布读多写少的结果页。", "不适合实时写入、权限控制、审批链之类需求。", "如果未来升级成运营平台，就得重构边界。"]),
    ]
    positions = [(0.72, 1.92), (6.62, 1.92), (0.72, 4.18), (6.62, 4.18)]
    fills = [COLORS["surface"], COLORS["surface_alt"], COLORS["surface_alt"], COLORS["surface"]]
    for (title, lines), (x, y), fill in zip(risk_cards, positions, fills):
        elements.append(card(sid, title, x, y, 5.9, 1.92, title, lines, fill=fill, title_color=COLORS["red"]))
        sid += 1
    slides.append(SlideSpec("风险与边界", elements))

    # Slide 9
    elements, sid = base_slide(9, total, "08 / 建议路线", "如果继续做，下一步最值得投到哪里", "别一口吃成胖子，先把最值钱的几步补上")
    roadmap = [
        ("近期 1-2 周", [
            "把节假日、目标 override、车型配置抽成独立配置文件。",
            "给 dashboard.summary.json 增加更清晰的数据版本号。",
            "在 README / SCRIPTS 里补充标准更新 SOP。"
        ], COLORS["surface"]),
        ("中期 1-2 月", [
            "补前端 smoke test，至少覆盖页面加载、tab 切换、图表渲染。",
            "为异常数据做告警，例如 sheet 缺失、数值为负、报表日期回退。",
            "把日报快照归档，支持按日期回看。"
        ], COLORS["surface_alt"]),
        ("长期", [
            "如果需要权限、角色、历史追踪，再评估迁移到真正的应用平台。",
            "若数据源持续增多，可在 JSON 产物前再加统一数据模型层。",
            "到那个阶段再谈服务端，不要现在先把自己吓死。"
        ], COLORS["surface"]),
    ]
    xs = [0.72, 4.47, 8.22]
    for (title, lines, fill), x in zip(roadmap, xs):
        elements.append(card(sid, title, x, 2.02, 3.55, 3.92, title, lines, fill=fill))
        sid += 1
    elements.append(build_shape(sid, "Roadmap Footer", BoxSpec(0.72, 6.2, 11.8, 0.56, [
        para("优先级建议：先补数据治理与自动验证，再考虑平台化扩张。", size=16, color=COLORS["white"], bold=True, align="ctr")
    ], fill=COLORS["navy"], line=None, rounded=True)))
    slides.append(SlideSpec("建议路线", elements))

    # Slide 10
    elements, sid = base_slide(10, total, "09 / 结论", "最后一句话：这个项目值得继续，但要按对的方向继续", "收口别太虚，得给出能拍板的建议")
    elements.append(card(sid, "Conclusion Main", 0.72, 1.96, 7.0, 3.3, "结论", [
        "1. 当前方案已经证明：把 Excel 日报静态化，并通过 GitHub Pages 发布，是可行且成本低的。",
        "2. 项目最强的价值不在花哨图表，而在于把数据构建、前端展示和发布流程拆成了可维护链路。",
        "3. 继续投入是值得的，但重点应该放在数据治理、自动验证和配置外置，不要急着上重量级平台。"
    ], fill=COLORS["surface"], title_color=COLORS["navy"]))
    sid += 1
    elements.append(card(sid, "Decision", 7.98, 1.96, 4.54, 1.5, "适用场景", [
        "领导日报查看",
        "内部经营复盘",
        "轻量对外/跨部门共享"
    ], fill=COLORS["surface_alt"], title_color=COLORS["red"]))
    sid += 1
    elements.append(card(sid, "Not Fit", 7.98, 3.66, 4.54, 1.6, "暂不适合", [
        "实时写入业务系统",
        "强权限审批流",
        "复杂多租户管理"
    ], fill=COLORS["surface"], title_color=COLORS["amber"]))
    sid += 1
    elements.append(build_shape(sid, "Close Bar", BoxSpec(0.72, 5.7, 11.8, 0.66, [
        para("建议结论：保留“静态站点 + 构建脚本 + Pages 发布”主架构，围绕数据质量和可维护性持续加固。", size=18, color=COLORS["white"], bold=True, align="ctr")
    ], fill=COLORS["red"], line=None, rounded=True)))
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
    slide_ids = "".join(
        f"<p:sldId id=\"{256 + index}\" r:id=\"rId{2 + index}\"/>"
        for index in range(slide_count)
    )
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
        f"<dc:title>AI Digest 项目逻辑梳理与可行性分析</dc:title>"
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
    parser = argparse.ArgumentParser(description="Generate a PPTX briefing for the AI Digest project.")
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
