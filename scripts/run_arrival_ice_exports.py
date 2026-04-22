from __future__ import annotations

import copy
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DAILY_SOURCE_ROOT = WORKSPACE_ROOT / "日报取数平台"
ARRIVAL_ICE_DIR = DAILY_SOURCE_ROOT / "日报来店ICE源"
ARRIVAL_ICE_GETDATA = ARRIVAL_ICE_DIR / "getdata.py"
TARGET_REPORT_KEYS = {
    "store_batch_vehicle_summary_本期_来店",
    "store_batch_vehicle_summary_同期_来店",
}
TARGET_THUMBNAIL_SHEET = "来店批次分车系汇总表_按天T"
TARGET_EXPORT_SHEET = "来店批次分车系汇总表_按天"
TARGET_TABLEAU_VIEW_PATH = "/_T"


def load_arrival_ice_module():
    if not ARRIVAL_ICE_GETDATA.exists():
        raise FileNotFoundError(f"未找到 ICE 来店取数脚本：{ARRIVAL_ICE_GETDATA}")

    for path in (ARRIVAL_ICE_DIR, DAILY_SOURCE_ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)

    spec = importlib.util.spec_from_file_location("ai_digest_arrival_ice_getdata", ARRIVAL_ICE_GETDATA)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{ARRIVAL_ICE_GETDATA}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def switch_tableau_view_to_daily(view_url: str) -> str:
    parsed = urlsplit(str(view_url or "").strip())
    if not parsed.fragment:
        return view_url

    fragment = parsed.fragment
    replaced_fragment = fragment.replace("/sheet2?", f"{TARGET_TABLEAU_VIEW_PATH}?", 1)
    replaced_fragment = replaced_fragment.replace("/sheet2#", f"{TARGET_TABLEAU_VIEW_PATH}#", 1)
    replaced_fragment = replaced_fragment.replace("/sheet2", TARGET_TABLEAU_VIEW_PATH, 1)
    if replaced_fragment == fragment:
        return view_url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, replaced_fragment))


def patch_report_config_builder(module) -> None:
    original_builder = module.build_effective_report_configs

    def patched_builder(args, report_keys):
        configs = original_builder(args, report_keys)
        patched_configs = []
        for config in configs:
            if getattr(config, "key", "") not in TARGET_REPORT_KEYS:
                patched_configs.append(config)
                continue

            metadata = copy.deepcopy(getattr(config, "request_metadata", {}) or {})
            export_crosstab = dict(metadata.get("export_crosstab") or {})
            thumbnail_uris = dict(export_crosstab.get("thumbnail_uris") or {})
            if TARGET_THUMBNAIL_SHEET not in thumbnail_uris:
                raise RuntimeError(f"ICE 来店导出配置中缺少目标缩略图 URI：{TARGET_THUMBNAIL_SHEET}")

            export_crosstab["thumbnail_uris"] = {
                TARGET_THUMBNAIL_SHEET: thumbnail_uris[TARGET_THUMBNAIL_SHEET],
            }
            metadata["export_crosstab"] = export_crosstab

            patched_configs.append(
                replace(
                    config,
                    bi_target_url=switch_tableau_view_to_daily(getattr(config, "bi_target_url", "")),
                    crosstab_sheet_name=TARGET_EXPORT_SHEET,
                    single_select_parameters=(),
                    request_metadata=metadata,
                )
            )
        return patched_configs

    module.build_effective_report_configs = patched_builder


def main() -> int:
    module = load_arrival_ice_module()
    patch_report_config_builder(module)
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
