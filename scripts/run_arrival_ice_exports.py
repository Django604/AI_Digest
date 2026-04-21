from __future__ import annotations

import copy
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DAILY_SOURCE_ROOT = WORKSPACE_ROOT / "日报取数平台"
ARRIVAL_ICE_DIR = DAILY_SOURCE_ROOT / "日报来店ICE源"
ARRIVAL_ICE_GETDATA = ARRIVAL_ICE_DIR / "getdata.py"
TARGET_REPORT_KEYS = {
    "store_batch_vehicle_summary_本期_来店",
    "store_batch_vehicle_summary_同期_来店",
}
TARGET_CROSSTAB_SHEET = "来店批次分车系汇总表_按天T"


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
            if TARGET_CROSSTAB_SHEET not in thumbnail_uris:
                raise RuntimeError(f"ICE 来店导出配置中缺少目标缩略图 URI：{TARGET_CROSSTAB_SHEET}")

            # Tableau 导出弹窗里返回的 sheetName 仍然是 "E3S报表样式"，
            # 但真正选中的视图由 thumbnail URI 决定。这里仅强制使用 _按天T 的
            # 缩略图入口，避免把 crosstab_sheet_name 改成中文视图名后找不到 sheetdocId。
            export_crosstab["thumbnail_uris"] = {
                TARGET_CROSSTAB_SHEET: thumbnail_uris[TARGET_CROSSTAB_SHEET],
            }
            metadata["export_crosstab"] = export_crosstab

            patched_configs.append(
                replace(
                    config,
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
