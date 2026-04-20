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

## 2026-04-17 14:45
- 需求目标：理解 `AI_Digest` 项目逻辑，并基于当前代码与数据产出一份可直接汇报的 PPT，覆盖功能介绍、架构逻辑、可行性分析、风险与建议
- 改动内容：新增 `scripts/generate_project_presentation.py`，基于仓库内 `dashboard.json` / `dashboard.summary.json` 与 Office 模板生成 `pptx` 汇报文件；新增 `reports/AI_Digest_Project_Analysis_2026-04-17.pptx`
- 涉及文件：`scripts/generate_project_presentation.py`、`reports/AI_Digest_Project_Analysis_2026-04-17.pptx`、`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`python -X utf8 scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --summary-out docs/data/dashboard.summary.json`、`python -X utf8 scripts/generate_project_presentation.py`
- 验证结果：`8` 个单元测试通过；`dashboard.json` 与 `dashboard.summary.json` 构建结果均为 `unchanged`；已生成 `10` 页 PPT，Zip 结构检查通过
- 回滚方法：删除 `scripts/generate_project_presentation.py` 与 `reports/AI_Digest_Project_Analysis_2026-04-17.pptx`，并移除本条变更记录
- 关联提交（如有）：待补充
- 备注：PPT 采用 Office 模板骨架 + Open XML 生成，避免依赖本机 PowerPoint COM 或额外第三方库

## 2026-04-17 17:16
- 需求目标：基于 `AI_Digest` 当前项目与数据，生成一份偏“效果呈现”的 PPT，不涉及代码实现细节，由工具自行决定内容结构
- 改动内容：新增 `scripts/generate_showcase_presentation.py`，基于仓库内 `dashboard.json` / `dashboard.summary.json` 生成效果展示版 PPT；新增 `reports/AI_Digest_Effect_Showcase_2026-04-17.pptx`
- 涉及文件：`scripts/generate_showcase_presentation.py`、`reports/AI_Digest_Effect_Showcase_2026-04-17.pptx`、`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 -m py_compile scripts/generate_showcase_presentation.py`、`python -X utf8 scripts/generate_showcase_presentation.py`
- 验证结果：已生成 `8` 页 PPT；Zip 结构检查通过；已完成一次内容 QA 与一次版式收敛修正
- 回滚方法：删除 `scripts/generate_showcase_presentation.py` 与 `reports/AI_Digest_Effect_Showcase_2026-04-17.pptx`，并移除本条变更记录
- 关联提交（如有）：待补充
- 备注：PPT 聚焦项目价值、页面观感、看板矩阵、最新业务快照与使用效果，避免展开代码层说明
## 2026-04-20 00:00
- 需求目标：将当前工作上下文切换到 `AI_Digest` 项目目录。
- 改动内容：确认当前工作目录为 `D:\WorkCode\AI_Digest`，并按项目规则读取根目录 `DEV_CHANGELOG.md`、`SCRIPTS.md` 与 Markdown 文件列表；未修改项目代码。
- 涉及文件：`DEV_CHANGELOG.md`
- 关键命令：`Get-ChildItem -Path d:\WorkCode\AI_Digest -Filter *.md | Select-Object -ExpandProperty Name`、`Get-Content -Path d:\WorkCode\AI_Digest\DEV_CHANGELOG.md -TotalCount 200`、`Get-Content -Path d:\WorkCode\AI_Digest\SCRIPTS.md -TotalCount 250`、`Get-Location | Select-Object -ExpandProperty Path`
- 验证结果：当前工作目录已确认为 `D:\WorkCode\AI_Digest`，后续可在该目录继续执行任务。
- 回滚方法：删除本条变更记录；如需执行删除，必须先获得明确授权。
- 关联提交（如有）：待补充
- 备注：本次为上下文切换与规则读取，无代码实现与测试变更。
## 2026-04-20 14:28
- 需求目标：将“月度对照表”顶部指标摘要从表格区域拆分出来，并合并到趋势图同一卡片容器中，位置放在趋势图上方。
- 改动内容：调整 `docs/assets/app.js`，新增 `renderTrendSummary()`，将趋势摘要改为在 `.chart-card` 内、`.chart-wrap` 之前渲染；同步修改 `docs/assets/styles.css`，为图表卡中的摘要增加间距，并让来店场景与移动端样式继续适配新的摘要容器位置。
- 涉及文件：`docs/assets/app.js`、`docs/assets/styles.css`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "月度对照表|4月全车有效线索趋势|累计本期实绩|当日本期实绩" -S .`、`git diff -- docs/assets/app.js docs/assets/styles.css`
- 验证结果：代码差异已确认，摘要卡片不再由表格组件渲染，而是进入趋势图卡片；尝试执行 `node --check docs\assets\app.js` 进行语法检查，但当前环境缺少 `node` 命令，未能完成该项验证。
- 回滚方法：回退 `docs/assets/app.js`、`docs/assets/styles.css` 与本条变更记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：本次未启动浏览器进行页面视觉验收，建议后续在本地预览页确认实际排版效果。
