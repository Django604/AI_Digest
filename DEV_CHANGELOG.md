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
## 2026-04-20 14:35
- 需求目标：移除页面中所有标题上方的英文小标题文案。
- 改动内容：更新 `docs/index.html`，删除页面主标题与区块标题模板中的英文小标题节点；更新 `docs/assets/app.js`，移除 `dashboard-kicker`、`section-label` 的渲染与赋值逻辑；更新 `docs/assets/styles.css`，清理对应样式选择器。
- 涉及文件：`docs/index.html`、`docs/assets/app.js`、`docs/assets/styles.css`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "dashboard-kicker|section-label|Daily Brief|toUpperCase\\(" docs\\assets\\app.js docs\\assets\\styles.css docs\\index.html`、`git diff -- docs/index.html docs/assets/app.js docs/assets/styles.css`
- 验证结果：相关英文小标题节点与渲染入口已移除，检索结果确认 `dashboard-kicker`、`section-label`、`Daily Brief` 与标题上方英文赋值逻辑均已从相关文件中清除。
- 回滚方法：回退 `docs/index.html`、`docs/assets/app.js`、`docs/assets/styles.css` 与本条变更记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：本次未启动浏览器进行视觉验收，建议刷新本地页面确认标题间距是否符合预期。
## 2026-04-20 14:35
- 需求目标：将“全车有效线索管控”页面内容区标题改为“全车系线索”，并将其移动到“月度对照表”所在上一级容器中。
- 改动内容：更新 `docs/assets/app.js`，为 `lead-control` dashboard 增加展示层标题策略：取消该页顶部 `dashboard-header` 标题渲染，并将首个 section 的标题注入为“全车系线索”，使标题显示在“月度对照表”的父级容器顶部。
- 涉及文件：`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "全车有效线索管控|全车系线索|月度对照表|dashboard-title|section-title" docs\\assets\\app.js docs\\index.html docs\\data\\dashboard.json`、`git diff -- docs/assets/app.js`
- 验证结果：已确认 `lead-control` 页面改为不渲染顶部大标题，并将首个区块标题设置为“全车系线索”；本次未启动浏览器做实际页面验收。
- 回滚方法：回退 `docs/assets/app.js` 与本条变更记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：侧边栏按钮与原始数据文案未改动，本次仅调整页面内容区的展示位置与标题文本。
## 2026-04-20 14:55
- 需求目标：将 `NEV 线索趋势` 改为 `NEV 线索`，并将下方 `NEV 总盘` 及其英文标题一并替换。
- 改动内容：更新 `docs/assets/app.js`，新增 dashboard 展示标题映射 `getDisplayDashboardTitle()`，将 `nev` 页签与内容区标题统一显示为 `NEV 线索`；扩展 `getDisplaySections()`，将 `nev` 首个区块标题替换为 `NEV 线索` 并清空 `sectionLabel`，避免继续显示原先的 `NEV 总盘` 与英文小标题。
- 涉及文件：`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "getDisplayDashboardTitle|NEV 线索|NEV 总盘|dashboard-kicker|section-label" docs\\assets\\app.js docs\\assets\\styles.css docs\\index.html`、`git diff -- docs/index.html docs/assets/app.js docs/assets/styles.css DEV_CHANGELOG.md`
- 验证结果：代码检索已确认 `NEV` 页标题映射与首个区块标题替换逻辑已写入展示层；英文小标题模板入口已移除；本次未启动浏览器做页面视觉验收。
- 回滚方法：回退 `docs/assets/app.js` 与本条变更记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：本次仅调整前端展示层，不修改 `docs/data/dashboard.json` 原始数据。

## 2026-04-20 15:29
- 需求目标：删除 `NEV` 页面内容区顶部重复显示的第一个大标题，仅保留下方卡片内的 `NEV 线索` 标题。
- 改动内容：更新 `docs/assets/app.js`，将 dashboard 标题渲染条件改为当其与首个 section 标题重复时不渲染，并继续保留 `lead-control` 页面对 dashboard 标题的隐藏策略。
- 涉及文件：`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`git diff -- docs/assets/app.js`、`Get-Date -Format "yyyy-MM-dd HH:mm"`
- 验证结果：代码差异已确认，`nev` 页面会因为 dashboard 标题与首个 section 标题同为 `NEV 线索` 而自动隐藏顶部大标题；未启动浏览器做页面目视验收。
- 回滚方法：回退 `docs/assets/app.js` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：该规则同时避免未来其他 dashboard 再出现标题与首块内容重复显示的问题。

## 2026-04-20 15:33
- 需求目标：将 `ICE 线索趋势` 改为 `ICE 线索`，替换原来的 `ICE 总盘`，并删除顶部重复显示的大标题。
- 改动内容：更新 `docs/assets/app.js`，为 `ice` dashboard 增加展示标题映射 `ICE 线索`，并将首个 section 标题同步替换为 `ICE 线索`，从而复用已有的重复标题隐藏逻辑。
- 涉及文件：`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "ICE 线索趋势|ICE 线索|ICE 总盘|getDisplayDashboardTitle|getDisplaySections" docs\assets\app.js docs\data\dashboard.json`、`git diff -- docs/assets/app.js DEV_CHANGELOG.md`
- 验证结果：代码差异已确认，`ice` 页面顶部 dashboard 标题会与首个 section 标题统一为 `ICE 线索`，因此顶部大标题将自动不再渲染；未启动浏览器做页面目视验收。
- 回滚方法：回退 `docs/assets/app.js` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：本次仍仅调整前端展示层，不修改 `docs/data/dashboard.json` 中的原始标题文本。

## 2026-04-20 15:59
- 需求目标：将两处趋势图文案分别改为 `4 月NEV 新增线索趋势` 与 `4 月ICE 有效线索趋势`，并推送到远端仓库。
- 改动内容：更新 `docs/data/dashboard.json` 中 `nev` 与 `ice` 首个趋势图的 `chartTitle`，移除原文案中的 `总盘` 字样，使页面截图文案与当前标题策略保持一致。
- 涉及文件：`docs/data/dashboard.json`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "4 月NEV 总盘新增线索趋势|4 月ICE 总盘有效线索趋势|4 月NEV|4 月ICE" docs\data\dashboard.json docs\assets\app.js`、`git diff -- docs\data\dashboard.json DEV_CHANGELOG.md`
- 验证结果：代码检索已确认两处 `chartTitle` 文案已替换为目标文本；未启动浏览器做页面目视验收。
- 回滚方法：回退 `docs/data/dashboard.json` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：本次仅修改静态数据文案，不涉及 `docs/assets/app.js` 的展示逻辑调整。

## 2026-04-20 16:07
- 需求目标：解决趋势图文案修改后页面仍未生效的问题，并确保部署后继续保持 `4 月NEV 新增线索趋势` 与 `4 月ICE 有效线索趋势`。
- 改动内容：定位到 `GitHub Pages` 工作流会在推送后重新运行 `scripts/build_dashboard.py` 覆盖 `docs/data/dashboard.json`；因此改为更新 `scripts/build_dashboard.py` 的趋势图标题生成逻辑，仅对 `NEV 总盘 + 新增线索` 与 `ICE 总盘 + 有效线索` 做标题归一化，再重新生成 `docs/data/dashboard.json` 与 `docs/data/dashboard.summary.json`。
- 涉及文件：`scripts/build_dashboard.py`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json`、`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --summary-out docs/data/dashboard.summary.json`、`rg -n "4 月NEV 新增线索趋势|4 月ICE 有效线索趋势|4 月NEV 总盘新增线索趋势|4 月ICE 总盘有效线索趋势" docs\data\dashboard.json scripts\build_dashboard.py`
- 验证结果：重建后的 `docs/data/dashboard.json` 已确认输出目标文案；`docs/data/dashboard.summary.json` 同步记录本次构建状态为 `updated`；后续工作流重建时不会再把文案打回旧值。
- 回滚方法：回退 `scripts/build_dashboard.py`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：本次修复的是生成源头而非静态产物补丁，避免部署流程再次覆盖文案。

## 2026-04-20 16:43
- 需求目标：增加一个全局一键截图功能，批量导出各板块趋势图区域到用户选择的本地文件夹，并跳过 `4 月ICE 有效线索趋势`。
- 改动内容：更新 `docs/index.html`，在侧边栏新增截图工具入口；更新 `docs/assets/styles.css`，补充截图按钮、状态提示和离屏渲染容器样式；更新 `docs/assets/app.js`，新增基于 `showDirectoryPicker()` 的批量截图流程、离屏渲染导出 PNG 逻辑、文件名清洗规则及 `ICE` 总盘跳过策略。
- 涉及文件：`docs/index.html`、`docs/assets/styles.css`、`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`rg -n "capture-all-button|handleGlobalTrendCapture|showDirectoryPicker|capture-stage|buildTrendCaptureJobs|shouldSkipTrendCapture" docs\index.html docs\assets\app.js docs\assets\styles.css`
- 验证结果：项目现有 `8` 个单元测试通过；代码检索已确认截图入口、批量导出逻辑、文件夹选择能力和离屏截图容器均已接入；由于当前环境缺少浏览器自动化验收，本次未实际点击按钮完成端到端截图测试。
- 回滚方法：回退 `docs/index.html`、`docs/assets/styles.css`、`docs/assets/app.js` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：截图功能依赖浏览器 `File System Access API`，建议在最新版 Chrome / Edge 且通过 `localhost` 或 `https` 环境使用。

## 2026-04-20 16:55
- 需求目标：修复一键截图时出现 `Tainted canvases may not be exported` 导致导出失败的问题。
- 改动内容：更新 `docs/assets/app.js`，移除基于 `foreignObject` 的整块 DOM 转 PNG 方案，改为生成纯 SVG 的趋势图导出卡片，再安全转换为 PNG；同步清理 `docs/assets/styles.css` 中已不再需要的离屏渲染容器样式。
- 涉及文件：`docs/assets/app.js`、`docs/assets/styles.css`、`DEV_CHANGELOG.md`
- 关键命令：`rg -n "renderTrendCardToPng|buildTrendCardExportSvg|buildTrendChartExportMarkup|buildLegendLayout|escapeXml" docs\assets\app.js`、`python -X utf8 -m unittest discover -s tests -v`
- 验证结果：项目现有 `8` 个单元测试通过；代码层已不再使用会污染 canvas 的 `foreignObject` 导出链路；由于当前环境缺少浏览器端自动化验收，本次未实际点击按钮复测导出成功结果。
- 回滚方法：回退 `docs/assets/app.js`、`docs/assets/styles.css` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：新的导出方式会生成一张结构化的趋势图卡片 PNG，目标是规避浏览器安全限制而不是逐像素复制当前 DOM。

## 2026-04-20 17:01
- 需求目标：继续修复截图导出仍触发 canvas 污染的问题，并提高浏览器兼容性。
- 改动内容：更新 `docs/assets/app.js`，将 SVG 图片加载方式从 `blob:` URL 改为内联 `data:image/svg+xml`，并为 `Image` 显式设置 `crossOrigin = "anonymous"`；同时补充针对 canvas 污染异常的定向报错提示。
- 涉及文件：`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`git diff -- docs/assets/app.js`
- 验证结果：项目现有 `8` 个单元测试通过；代码差异已确认导出链路改为内联 SVG 数据 URL；由于当前环境缺少浏览器端自动化验收，本次未实际点击按钮复测。
- 回滚方法：回退 `docs/assets/app.js` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：如果个别浏览器仍然严格拦截，下一步应改为完全基于 Canvas API 手工绘制导出卡片，不再经过 `Image` 解码 SVG。

## 2026-04-20 17:19
- 需求目标：在推送前完成“一键截图趋势图”功能的真实浏览器自测，确认批量导出链路可用。
- 改动内容：未修改功能代码；补充一次基于本地 HTTP 服务与 Playwright 的端到端验收，真实点击页面上的 `一键截图趋势图` 按钮，并通过模拟 `showDirectoryPicker()` 将导出的 PNG 写入本地临时目录。
- 涉及文件：`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`python -X utf8 - <<'PY' ... PY`
- 验证结果：单元测试 `8/8` 通过；浏览器端真实导出成功，状态文案为“截图完成，已保存 8 张趋势图到所选文件夹，已跳过 4 月ICE 有效线索趋势。”；临时目录内共生成 `8` 张 PNG，且未导出被要求跳过的 `4 月ICE 有效线索趋势`。
- 回滚方法：删除本条 `DEV_CHANGELOG.md` 记录即可。
- 关联提交（如有）：待补充
- 备注：自动化验收过程中出现 1 条静态资源 `404` 控制台日志，但不影响页面加载与截图导出流程。

## 2026-04-20 17:22
- 需求目标：将已完成真实验收的截图导出修复提交并推送到 GitHub。
- 改动内容：仅提交 `docs/assets/app.js` 与 `DEV_CHANGELOG.md`；创建提交 `743d611`，并推送到远端 `origin/main`。
- 涉及文件：`DEV_CHANGELOG.md`
- 关键命令：`git add docs/assets/app.js DEV_CHANGELOG.md`、`git commit -m "Fix screenshot export compatibility"`、`git push origin main`
- 验证结果：远端推送成功，`main` 分支已从 `204c88c` 更新到 `743d611`。
- 回滚方法：如需撤回，基于提交 `743d611` 执行新的反向提交，不直接改写远端历史。
- 关联提交（如有）：`743d611`
- 备注：仓库内存在未跟踪的 `pptx` 与脚本文件，本次未纳入提交。

## 2026-04-20 17:45
- 需求目标：修复一键截图导出时趋势图右侧被裁切、日期轴只显示到 `4/22` 的问题。
- 改动内容：更新 `docs/assets/app.js`，将导出卡片宽度从固定 `1120` 改为至少覆盖完整趋势图 SVG 宽度，避免趋势图内容超出卡片边界后被裁切。
- 涉及文件：`docs/assets/app.js`、`DEV_CHANGELOG.md`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`python -X utf8 - <<'PY' ... PY`
- 验证结果：单元测试 `8/8` 通过；真实浏览器自动化复测中，一键截图成功导出 `8` 张 PNG，首张截图尺寸为 `3232x1756`，其余趋势图截图宽度同样扩展到 `3232`，不再沿用此前会截断右侧内容的较窄导出宽度。
- 回滚方法：回退 `docs/assets/app.js` 与本条 `DEV_CHANGELOG.md` 记录到修改前状态。
- 关联提交（如有）：待补充
- 备注：自动化复测过程中仍出现 1 条静态资源 `404` 控制台日志，但不影响页面加载与截图导出结果。
