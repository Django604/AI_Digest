# DEV CHANGELOG

## 2026-04-07 17:35
- 需求目标：分析 `NEV+ICE线索简报AI模板.xlsm` 的公式依赖、数据结构与面板结构，并将 `NEV 全车系线索日趋势`、`ICE 全车系线索日趋势` 制作为可发布到 `GitHub Pages` 的 Web 版
- 改动内容：复制源工作簿到 `data/source/dashboard-source.xlsm`；新增 Excel 分析报告；新增 `scripts/build_dashboard.py` 抽取面板数据；新增静态站点 `docs/`；新增 `GitHub Pages` 自动发布工作流；补充项目说明与脚本手册
- 涉及文件：`README.md`、`SCRIPTS.md`、`DEV_CHANGELOG.md`、`reports/excel_analysis.md`、`scripts/build_dashboard.py`、`docs/index.html`、`docs/assets/styles.css`、`docs/assets/app.js`、`docs/data/dashboard.json`、`.github/workflows/deploy-pages.yml`、`data/source/dashboard-source.xlsm`
- 关键命令：`python scripts/build_dashboard.py --workbook data/source/dashboard-source.xlsm --out docs/data/dashboard.json`、`python -m http.server 4173 --directory docs`
- 验证结果：已完成 Excel 结构梳理；已生成静态页面所需 JSON；已具备本地预览与 `GitHub Pages` 自动发布基础
- 回滚方法：删除本次新增的站点、脚本、报告与工作流文件，并移除 `data/source/dashboard-source.xlsm`
- 关联提交（如有）：待补充
- 备注：`Django` 不适合直接部署到 `GitHub Pages`，当前实现改用静态站点方案

## 2026-04-07 17:41
- 需求目标：删除源工作簿副本中的废弃工作表 `NEV大区汇总`
- 改动内容：从 `data/source/dashboard-source.xlsm` 移除 `NEV大区汇总` 工作表；重新生成 `docs/data/dashboard.json`；同步更新分析文档与项目说明
- 涉及文件：`data/source/dashboard-source.xlsm`、`docs/data/dashboard.json`、`reports/excel_analysis.md`、`scripts/build_dashboard.py`、`README.md`、`DEV_CHANGELOG.md`
- 关键命令：`python -c "from openpyxl import load_workbook; ..."`、`python scripts/build_dashboard.py --workbook data/source/dashboard-source.xlsm --out docs/data/dashboard.json`
- 验证结果：源工作簿副本现为 8 张表；数据抽取脚本重新执行通过
- 回滚方法：从未删除该工作表的原始 Excel 再复制一份到 `data/source/dashboard-source.xlsm`
- 关联提交（如有）：待补充
- 备注：仅修改仓库内副本，未动桌面原始文件

## 2026-04-07 17:59
- 需求目标：解决默认 `python -m http.server` 在访问 `/docs`、`/AI_Digest` 等路径时返回 404，导致本地预览“运行不了”
- 改动内容：新增 `scripts/serve_dashboard.py`，使用 `ThreadingHTTPServer` 定向到 `docs/` 并在干净 URL 缺少物理文件时回退到 `index.html`；更新 `README.md` 与 `SCRIPTS.md` 说明新的预览脚本
- 涉及文件：`scripts/serve_dashboard.py`、`README.md`、`SCRIPTS.md`、`DEV_CHANGELOG.md`
- 关键命令：`python scripts/serve_dashboard.py --port 4173`（新增脚本的使用方式）、`python - <<...`（模拟请求 `/`、`/docs`、`/AI_Digest` 验证回退）
- 验证结果：通过引入脚本后的临时服务器测试，`/`、`/docs`、`/AI_Digest` 均返回 200 并加载同一个仪表盘
- 回滚方法：删除 `scripts/serve_dashboard.py` 并将 `README.md`、`SCRIPTS.md` 恢复到仅记录默认 `http.server` 的版本
- 关联提交（如有）：待补充
- 备注：本地预览默认提示「按 Ctrl+C 退出」，避免悬挂后台进程
