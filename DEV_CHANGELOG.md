# DEV CHANGELOG

## 2026-04-23 14:55
- 需求 / 目标：去掉每日简报卡片正文中的强制回车换行，让正文按卡片宽度自然换行显示。
- 改动内容：更新 `docs/assets/app.js` 的简报卡片渲染逻辑，将原先按 `section.lines` 逐条渲染多个段落，改为合并成单个正文段落输出。
- 涉及文件：`docs/assets/app.js`
- 关键命令：待补充
- 验证结果：代码层面已确认正文改为通过 `buildBriefBodyHtml()` 合并输出，不再逐条生成多个 `.brief-page-line` 段落。
- 回滚方法：回退本次 `docs/assets/app.js` 渲染逻辑修改。
- 关联提交（如有）：待补充
- 备注：这次是去掉硬回车，不是阻止浏览器自然换行，别把两码事搅一块。

## 2026-04-23 11:29
- 需求 / 目标：将页面文案 `4月全车有效线索趋势` 调整为 `4月全车系有效线索趋势`。
- 改动内容：更新 `scripts/build_dashboard.py` 的趋势图标题生成文案，并重建 `docs/data/dashboard.json` 以同步页面产物。
- 涉及文件：`scripts/build_dashboard.py`、`docs/data/dashboard.json`
- 关键命令：`python -X utf8 scripts\\build_dashboard.py --workbook data\\source\\NEV+ICE_xsai.xlsm --arrival-workbook data\\source\\NEV+ICE_ldai.xlsx --out docs\\data\\dashboard.json --summary-out docs\\data\\dashboard.summary.json`
- 验证结果：`dashboard.json` 中对应 `chartTitle` 已更新为 `4月全车系有效线索趋势`。
- 回滚方法：回退本次 `build_dashboard.py` 与 `dashboard.json` 文案变更。
- 关联提交（如有）：待补充
- 备注：这次只是改文案，不是改数据，别让小字眼装成大故障。

## 2026-04-23 11:17
- 需求 / 目标：修复 GitHub Pages 在提交了本机 `localhost` 更新服务地址后，其他人打开页面直接 `Failed to fetch` 的问题。
- 改动内容：将 `docs/data/runtime-config.json` 的默认 `serviceBaseUrl` 清空，恢复为公共静态浏览模式；更新 `docs/assets/app.js`，当远端数据服务不可达时自动回退到静态 `./data/dashboard.json`，不再让整页直接报错；同步更新 `README.md` 说明。
- 涉及文件：`docs/data/runtime-config.json`、`docs/assets/app.js`、`README.md`
- 关键命令：待补充
- 验证结果：代码层面已确认默认不会再请求 `http://localhost:4173`；若未来再次配置不可达远端地址，前端会回退到静态 `dashboard.json` 而非整页失败。
- 回滚方法：回退本次前端与配置文件修改，恢复旧版远端优先且无静态回退的实现。
- 关联提交（如有）：待补充
- 备注：把 `localhost` 推到 GitHub Pages 上，和把家里门牌号写到导航里让别人自己找一样离谱。

## 2026-04-23 10:53
- 需求 / 目标：完成定时更新“双通道”系统级验收，确认登录态交互任务与未登录静默任务都能真实执行。
- 改动内容：提权重注册 `AI_Digest_Daily_Update_Interactive` 与 `AI_Digest_Daily_Update_Silent`，确认静默任务身份已改为 `SYSTEM / ServiceAccount`；手动触发静默任务并持续轮询 `.runtime/scheduled_update/` 运行目录、日志与 `result.json`；同步记录最终验收结果。
- 涉及文件：`DEV_CHANGELOG.md`
- 关键命令：`Start-ScheduledTask -TaskName AI_Digest_Daily_Update_Silent`、`Get-ScheduledTaskInfo -TaskName AI_Digest_Daily_Update_Silent`
- 验证结果：交互任务最近一次成功执行时间为 `2026-04-23 10:13:15`，`LastTaskResult = 0`；静默任务已于 `2026-04-23 10:45:30` 通过 `SYSTEM` 成功启动，`2026-04-23 10:49:09` 完成全链路更新，`result.json` 位于 `D:\WorkCode\AI_Digest\.runtime\scheduled_update\20260423_104530_900758\result.json`，`LastTaskResult = 0`。
- 回滚方法：删除当前双任务并回退调度脚本 / 注册脚本到旧版单任务实现后重新注册。
- 关联提交（如有）：待补充
- 备注：这次终于不是“理论双通道”，而是交互和静默两条腿都实打实落地了。

## 2026-04-23 10:40
- 需求 / 目标：补完定时更新“双通道”系统级验证，修复静默计划任务实际上无法启动的问题。
- 改动内容：排查 `AI_Digest_Daily_Update_Silent` 的计划任务事件日志，确认原先 `S4U` 登录在 `LogonUserS4U` 阶段失败；调整 `scripts/register_daily_update_task.ps1`，把静默兜底任务改为使用 `SYSTEM` 服务账号执行；同步更新 `README.md`、`SCRIPTS.md` 说明。
- 涉及文件：`scripts/register_daily_update_task.ps1`、`README.md`、`SCRIPTS.md`
- 关键命令：`Get-WinEvent -LogName Microsoft-Windows-TaskScheduler/Operational ...`、`powershell -ExecutionPolicy Bypass -File scripts\\register_daily_update_task.ps1`
- 验证结果：事件日志已确认旧版静默任务失败根因是 `LogonUserS4U` 登录错误 `2147943726`；修复后的重新注册与系统级手动触发验证待补充。
- 回滚方法：回退注册脚本与文档变更，并重新注册旧版计划任务。
- 关联提交（如有）：待补充
- 备注：这次不是脚本装死，是计划任务自己连门禁都刷不过。

## 2026-04-23 10:29
- 需求 / 目标：修复 `全国来店日趋势` 中 `ICE本期实绩` 丢失 `4 月 1 日` 数据的问题，并重新生成页面数据。
- 改动内容：调整 `scripts/build_dashboard.py` 的 `load_arrival_daily_sheet()`，改为从第 1 行开始扫描来店底表，兼容“带表头”和“无表头”两种导出结构；补充 `tests/test_build_dashboard.py`，覆盖无表头 `ICE` 来店底表与 `ICE本期实绩` 首日不再为 `-` 的场景；重建 `docs/data/dashboard.json`。
- 涉及文件：`scripts/build_dashboard.py`、`tests/test_build_dashboard.py`、`docs/data/dashboard.json`
- 关键命令：`python -X utf8 -m unittest tests.test_build_dashboard -v`、`python -X utf8 scripts\\build_dashboard.py --workbook data\\source\\NEV+ICE_xsai.xlsm --arrival-workbook data\\source\\NEV+ICE_ldai.xlsx --out docs\\data\\dashboard.json --summary-out docs\\data\\dashboard.summary.json`
- 验证结果：`BuildDashboard` 相关单测 `12/12` 通过；重建后的 `dashboard.json` 中 `ICE本期实绩` 前 6 个值已变为 `1187, 1006, 1059, 1942, 2282, 1951`，`4/1` 不再缺失。
- 回滚方法：回退本次 `build_dashboard.py`、相关测试与 `dashboard.json` 的变更。
- 关联提交（如有）：待补充
- 备注：这次不是数据没来，是代码把第一行当空气了。

## 2026-04-23 10:06
- 需求 / 目标：把定时更新改成“登录时弹窗执行，未登录时静默执行”，并避免两条计划任务重复更新同一批数据。
- 改动内容：更新 `scripts/scheduled_update_runner.py`，新增 `interactive/silent` 双模式、计划任务文件锁与锁冲突跳过结果；更新 `scripts/register_daily_update_task.ps1`，改为注册 `AI_Digest_Daily_Update_Interactive` 与 `AI_Digest_Daily_Update_Silent` 两条任务，默认分别在 `09:00` 与 `09:01` 执行；补充 `tests/test_scheduled_update_runner.py` 对静默模式、模式解析与重复运行锁的覆盖；同步更新 `README.md`、`SCRIPTS.md` 说明。
- 涉及文件：`scripts/scheduled_update_runner.py`、`scripts/register_daily_update_task.ps1`、`tests/test_scheduled_update_runner.py`、`README.md`、`SCRIPTS.md`
- 关键命令：`python -X utf8 -m py_compile scripts\\scheduled_update_runner.py tests\\test_scheduled_update_runner.py`、`python -X utf8 -m unittest tests.test_scheduled_update_runner -v`
- 验证结果：定时更新相关单测 `10/10` 通过，已确认 `silent` 模式可无弹窗执行，且在已有运行锁时会写出 `skipped` 结果并直接退出。
- 回滚方法：回退本次提交涉及的调度脚本、注册脚本、测试与文档，并重新注册旧版单任务计划任务。
- 关联提交（如有）：待补充
- 备注：这次总算把“人在线给窗看，没人在线也得干活”这件事从口号改成机制了。

## 2026-04-23 09:54
- 需求 / 目标：将“2 分钟自动开始 + 常驻进度窗”版本推送到 GitHub，并手动触发一次计划任务，确认在无人点击启动按钮的情况下也能自动完成更新。
- 改动内容：未新增功能代码；提权执行 `Start-ScheduledTask -TaskName AI_Digest_Daily_Update` 手动拉起计划任务，并持续轮询 `result.json` 与任务状态，验证新交互逻辑不会再卡死在启动提示阶段；同步记录本次验证结果。
- 涉及文件：`DEV_CHANGELOG.md`
- 关键命令：`Start-ScheduledTask -TaskName AI_Digest_Daily_Update`、`schtasks /Query /TN AI_Digest_Daily_Update /V /FO LIST`
- 验证结果：在未手动点击启动按钮的前提下，计划任务于 `2026-04-23 09:48:28` 自动启动，并在 `2026-04-23 09:53:55` 成功完成，业务日期为 `2026-04-22`；结果文件位于 `D:\WorkCode\AI_Digest\.runtime\scheduled_update\20260423_094828\result.json`，对应抓取运行目录为 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260422_20260423-095027`。
- 回滚方法：无需回滚代码；若后续发现定时任务交互异常，可回退上一版 `scheduled_update_runner.py` 并重新注册计划任务。
- 关联提交（如有）：待补充
- 备注：任务查询时仍短暂显示 `Running`，是因为结果窗口会保留一段时间后自动关闭；核心更新流程已经成功结束，不是卡死。

## 2026-04-23 09:23
- 需求 / 目标：调整定时更新提示框交互，要求在弹框出现后若 2 分钟未点击“确定/开始”，系统自动继续执行；执行过程中提示框不消失，并显示完成进度条。
- 改动内容：重写 `scripts/scheduled_update_runner.py` 的交互层，弃用阻塞式 `MessageBox`，改为基于 `tkinter` 的常驻进度窗；启动阶段显示更新流程说明和 2 分钟自动开始倒计时，超时后自动进入执行；执行阶段保留窗口并根据 `run_update()` 的日志阶段更新进度条与状态文案；完成或失败后在同一窗口展示结果摘要并自动关闭；补充 `tests/test_scheduled_update_runner.py`，覆盖自动开始提示文案、等待状态文案以及日志驱动进度推断。
- 涉及文件：`scripts/scheduled_update_runner.py`、`tests/test_scheduled_update_runner.py`、`README.md`、`SCRIPTS.md`
- 关键命令：`python -X utf8 -m py_compile scripts\\scheduled_update_runner.py tests\\test_scheduled_update_runner.py`、`python -X utf8 -m unittest discover -s tests -v`
- 验证结果：`AI_Digest` 全量单测 `35/35` 通过；新增调度相关单测通过，确认自动开始文案和进度推断逻辑符合预期。
- 回滚方法：回退本次提交涉及的调度窗口实现、测试与文档，恢复到原先阻塞式提示框方案。
- 关联提交（如有）：待补充
- 备注：由于交互窗口需要桌面会话，本轮未在沙箱中做完整的手动点窗验收；但计划任务后续会直接使用新的常驻进度窗实现。

## 2026-04-22 18:16
- 需求 / 目标：手动触发一次已注册的 Windows 计划任务 `AI_Digest_Daily_Update`，确认定时自动更新任务能够被即时拉起。
- 改动内容：未修改功能代码；提权执行 `Start-ScheduledTask -TaskName AI_Digest_Daily_Update` 手动触发计划任务，并通过 `schtasks /Query /TN AI_Digest_Daily_Update /V /FO LIST` 与 `.runtime/scheduled_update/` 运行痕迹确认任务已进入运行态。
- 涉及文件：`DEV_CHANGELOG.md`
- 关键命令：`Start-ScheduledTask -TaskName AI_Digest_Daily_Update`、`schtasks /Query /TN AI_Digest_Daily_Update /V /FO LIST`
- 验证结果：计划任务于 `2026-04-22 18:08:16` 成功进入 `Running`，新的运行目录为 `D:\WorkCode\AI_Digest\.runtime\scheduled_update\20260422_180820`，并写入 `run_meta.json`；由于当前设计包含“启动即弹流程提示框”，日志尚未继续写入，说明任务正等待用户确认启动提示框后再继续执行。
- 回滚方法：无需回滚代码；若不再需要该计划任务，可删除 Windows 任务 `AI_Digest_Daily_Update`。
- 关联提交（如有）：待补充
- 备注：手动触发时若看到任务长时间 `Running`，先别一惊一乍，优先检查桌面上是否有启动提示框尚未确认。

## 2026-04-22 17:53
- 需求 / 目标：为 `AI_Digest` 增加每天北京时间 `09:00` 自动执行的数据更新能力，替代手动点击网页 `数据更新`，并在任务启动与结束时弹出提示框说明更新流程和结果。
- 改动内容：新增 `scripts/scheduled_update_runner.py`，复用 `fetch_daily_data.py` 的 `run_update()` 执行全量更新，并把启动说明、成功结果、失败结果分别封装成 Windows MessageBox 提示；新增 `scripts/register_daily_update_task.ps1`，使用 Windows 计划任务 API 注册默认任务 `AI_Digest_Daily_Update`，每天 `09:00` 触发、按交互式登录模式运行并优先使用 `pythonw.exe`；补充 `tests/test_scheduled_update_runner.py`，覆盖提示文案生成；同步更新 `README.md` 与 `SCRIPTS.md`。
- 涉及文件：`scripts/scheduled_update_runner.py`、`scripts/register_daily_update_task.ps1`、`tests/test_scheduled_update_runner.py`、`README.md`、`SCRIPTS.md`
- 关键命令：`python -X utf8 -m py_compile scripts\\scheduled_update_runner.py tests\\test_scheduled_update_runner.py`、`python -X utf8 -m unittest discover -s tests -v`
- 验证结果：新增调度相关单测通过，`AI_Digest` 当前全量单测 `32/32` 通过。
- 回滚方法：删除计划任务 `AI_Digest_Daily_Update`，并回退本次新增的调度脚本、测试与文档。
- 关联提交（如有）：待补充
- 备注：计划任务若需要正常显示提示框，需在“用户已登录”的交互式会话中运行；若机器关机或未登录，任务可触发但不会有可见弹框。

## 2026-04-22 17:30
- 需求 / 目标：修复 `NEV本期来店`、`NEV同期来店` 仍未真实按日更新的问题，改为直接从 FineReport 后台接口导出自定义来店数据，并重新跑通整条网页更新链路后准备提交 GitHub。
- 改动内容：新增 `scripts/run_arrival_nev_exports.py` 作为 `日报来店NEV源` 的运行时包装器，复用原登录态和参数模板，补上 `tab/execute(tabName=自定义)`，当 `REPORT2 load/content` 返回“合计值 + simplechart”时，继续解析 `chartID/ecName` 并请求 `chart.data` 还原按日序列；更新 `scripts/fetch_daily_data.py` 改为调用该包装器；更新 `scripts/build_dashboard.py`，去掉 `NEV` 来店按日数据为空时回退到线索工作簿 `arrivals` 聚合值的兜底逻辑，避免掩盖真实取数异常；补充 `tests/test_run_arrival_nev_exports.py`，覆盖 simplechart 元数据提取、chart.data 按日解析与 URL 构造；同步更新 `README.md` 与 `SCRIPTS.md`。
- 涉及文件：`scripts/run_arrival_nev_exports.py`、`tests/test_run_arrival_nev_exports.py`、`scripts/fetch_daily_data.py`、`scripts/build_dashboard.py`、`README.md`、`SCRIPTS.md`、`data/source/NEV+ICE_ldai.xlsx`、`data/source/NEV+ICE_xsai.xlsm`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`python -X utf8 scripts/run_arrival_nev_exports.py --business-date 2026-04-21 --report-keys store_current_period,store_same_period --output-dir D:\WorkCode\AI_Digest\.runtime\nev_arrival_chart_fix_test --output-folder-name debug-0421g --safe-bootstrap --capture-wait-ms 30000 --headless`、`python -X utf8 scripts/fetch_daily_data.py --business-date 2026-04-21 --keep-runtime`
- 验证结果：`AI_Digest` 全量单测 `29/29` 通过；真实导出已生成 `NEV本期-0421.xlsx`、`NEV同期-0421.xlsx`，结构为标准两列表，抽样首尾值分别验证为 `2026-04-01 | 1286`、`2026-04-21 | 2017` 与 `2025-04-01 | 82`、`2025-04-21 | 263`；完整更新链路已成功回填 7 张表，运行目录为 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260421_20260422-172530`，`dashboard.json` 与 `dashboard.summary.json` 均已更新。
- 回滚方法：回退本次提交涉及的 NEV 来店包装器、回填逻辑、测试与数据文件，或基于本次提交创建新的反向提交。
- 关联提交（如有）：待补充
- 备注：当前仓库仍有与本次任务无关的未跟踪文件（如 `.codex/`、`reports/*.pptx`、`tests/.tmp-copy-check/`），本次不会纳入提交。

## 2026-04-22 14:42
- 需求 / 目标：修复页面 `全国来店日趋势` 中 `NEV本期实绩` 整排显示为 `-` 的问题，并同步恢复来店简报中的 NEV 来店数据。
- 改动内容：调整 `scripts/build_dashboard.py` 的来店数据编排逻辑，在 `NEV本期来店/NEV同期来店` 工作表不是按日两列表时，回退使用 `NEV+ICE_xsai.xlsm` 的 `全国按日NEV` 中 `新增到店量` 聚合生成 NEV 来店按日序列；补充 `tests/test_build_dashboard.py`，锁定 `NEV本期实绩` 行不再为空。  
- 涉及文件：`scripts/build_dashboard.py`、`tests/test_build_dashboard.py`、`docs/data/dashboard.json`
- 关键命令：`python -X utf8 scripts/build_dashboard.py --workbook data\\source\\NEV+ICE_xsai.xlsm --arrival-workbook data\\source\\NEV+ICE_ldai.xlsx --out docs\\data\\dashboard.json --summary-out docs\\data\\dashboard.summary.json`、`python -X utf8 -m unittest discover -s tests -v`
- 验证结果：全量单测 `22/22` 通过；重建后的 `dashboard.json` 中 `NEV本期实绩` 已恢复按日数据，`全国累计来店` 更新为 `85,973`，`①NEV累计来店` 更新为 `50,835`，不再是只显示 ICE 数据。
- 回滚方法：基于本次提交创建新的反向提交，或回退 `scripts/build_dashboard.py`、相关测试与 `dashboard.json` 到修复前版本。
- 关联提交（如有）：待补充
- 备注：仓库内仍有与本次任务无关的未跟踪文件，本次不会纳入提交。

## 2026-04-22 14:13
- 需求 / 目标：修复 `ICE本期来店`、`ICE同期来店` 仍未按日更新的问题，按用户更正强制改为从 `来店批次分车系汇总表_按天T` 的导出入口取数，并重新跑通整条更新链路。
- 改动内容：调整 `scripts/run_arrival_ice_exports.py`，将目标 Tableau 视图从 `sheet2` 切到 `/_T`，仅保留 `来店批次分车系汇总表_按天T` 的缩略图入口，并把导出 sheet 名锁定为 `来店批次分车系汇总表_按天`，同时清空 `_T` 页面不再适用的旧单选参数；同步补充 `tests/test_run_arrival_ice_exports.py` 覆盖该行为。
- 涉及文件：`scripts/run_arrival_ice_exports.py`、`tests/test_run_arrival_ice_exports.py`、`data/source/NEV+ICE_ldai.xlsx`、`data/source/NEV+ICE_xsai.xlsm`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`python -X utf8 scripts/run_arrival_ice_exports.py --business-date 2026-04-21 --report-keys store_batch_vehicle_summary_本期_来店,store_batch_vehicle_summary_同期_来店 --output-dir D:\WorkCode\AI_Digest\.runtime\ice_arrival_daily_fix_test --output-folder-name debug-0421f`、`python -X utf8 scripts/fetch_daily_data.py --business-date 2026-04-21 --keep-runtime`
- 验证结果：全量单测 `21/21` 通过；已导出 `来店本期-0421.xlsx`、`来店同期-0421.xlsx`，首行数据分别验证为 `2026年4月1日 | 1187` 与 `2025年4月1日 | 2390` 的按日两列表结构；完整更新运行目录为 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260421_20260422-142613`；`docs/data/dashboard.json` 中 `全国来店日趋势` 已恢复非零数据。
- 回滚方法：基于本次提交创建新的反向提交，或回退 `scripts/run_arrival_ice_exports.py`、相关测试与数据产物到修复前版本。
- 关联提交（如有）：待补充
- 备注：仓库内仍有与本次任务无关的未跟踪文件，本次不会纳入提交。

## 2026-04-21 18:28
- 需求目标：修正 `ICE本期来店`、`ICE同期来店` 的取数源，按更正要求强制走 `来店批次分车系汇总表_按天T`，并重新跑通本地更新链路与页面更新 API。
- 改动内容：新增并调整 `scripts/run_arrival_ice_exports.py` 的运行时补丁逻辑，只收敛 Tableau `thumbnail_uris` 到 `来店批次分车系汇总表_按天T`，保留真实导出 `sheetdocId` 对应的 `crosstab_sheet_name = E3S报表样式`；更新 `scripts/fetch_daily_data.py` 继续通过该包装器执行 ICE 来店导出；补充 `tests/test_run_arrival_ice_exports.py` 单测；同步更新 `README.md`、`SCRIPTS.md` 说明，并重新生成工作簿与 dashboard 数据。
- 涉及文件：`DEV_CHANGELOG.md`、`README.md`、`SCRIPTS.md`、`scripts/fetch_daily_data.py`、`scripts/run_arrival_ice_exports.py`、`tests/test_run_arrival_ice_exports.py`、`data/source/NEV+ICE_xsai.xlsm`、`data/source/NEV+ICE_ldai.xlsx`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json`
- 关键命令：`python -X utf8 -m unittest discover -s tests -v`、`python -X utf8 scripts/run_arrival_ice_exports.py --business-date 2026-04-20 --report-keys store_batch_vehicle_summary_本期_来店,store_batch_vehicle_summary_同期_来店 --output-dir D:\WorkCode\AI_Digest\.runtime\ice_arrival_override_test2 --output-folder-name debug-0420`、`python -X utf8 scripts/fetch_daily_data.py --business-date 2026-04-20 --keep-runtime`、`Invoke-WebRequest -Method Post http://127.0.0.1:4173/api/update-data`
- 验证结果：全量测试 `20/20` 通过；直接全链路更新成功，运行目录 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260420_20260421-181812` 已生成 7 张导出表并回填两本源工作簿；重启本地 `4173` 服务后，`/api/update-data` 再次真实返回 `success`，运行目录为 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260420_20260421-182437`；保留的 ICE 来店 trace 已确认 `request_export_error = null`，说明请求导出不再因 `sheetdocId` 匹配失败回退到 UI 下载。
- 回滚方法：回退本次提交涉及的包装器、文档、测试与数据文件，或基于本次提交创建新的反向提交。
- 关联提交（如有）：待补充
- 备注：仓库内仍存在与本次修复无关的未跟踪 `pptx`、`.codex/`、`tests/.tmp-copy-check/` 等文件，本次不会纳入提交。

## 2026-04-21 17:09
- 需求目标：在网页 `更新` 按钮现有真实更新能力基础上，再补齐来店 4 张表，让同一次更新任务同时覆盖线索工作簿与来店工作簿。
- 改动内容：扩展 `scripts/fetch_daily_data.py`，新增 `日报来店NEV源` 与 `日报来店ICE源` 两组任务，抓取 `NEV本期来店`、`NEV同期来店`、`ICE本期来店`、`ICE同期来店` 并回填 `data/source/NEV+ICE_ldai.xlsx`；为 NEV 来店任务固化 `--safe-bootstrap --capture-wait-ms 30000` 以规避共享初始化失败；补充导出别名、宏 / 非宏工作簿回填与报表日期回退测试；更新 `README.md`、`SCRIPTS.md` 说明；重启 `4173` 本地更新后端并通过真实 API 再次执行更新。
- 涉及文件：`DEV_CHANGELOG.md`、`README.md`、`SCRIPTS.md`、`scripts/fetch_daily_data.py`、`scripts/build_dashboard.py`、`tests/test_fetch_daily_data.py`、`tests/test_build_dashboard.py`、`data/source/NEV+ICE_xsai.xlsm`、`data/source/NEV+ICE_ldai.xlsx`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json`
- 关键命令：`python -X utf8 scripts/fetch_daily_data.py --business-date 2026-04-20 --keep-runtime`、`python -X utf8 -m unittest discover -s tests -v`、`Invoke-WebRequest -Method Post http://127.0.0.1:4173/api/update-data`
- 验证结果：`/api/update-data` 真实返回 `success`，业务日期为 `2026-04-20`；运行目录 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260420_20260421-170457` 中生成 `全国按日-0420.xlsx`、`全国按日ICE-0420.xlsx`、`十五代轩逸按日-0420.xlsx`、`NEV本期-0420.xlsx`、`NEV同期-0420.xlsx`、`来店本期-0420.xlsx`、`来店同期-0420.xlsx` 共 7 张导出表；全量测试 `19/19` 通过。
- 回滚方法：停止 `4173` 端口本地服务；如需撤回此次代码、配置与数据变更，基于本次提交创建新的反向提交。
- 关联提交（如有）：待补充
- 备注：当前 `docs/data/runtime-config.json` 仍指向 `http://localhost:4173`，因此只有在这台机器上打开 GitHub Pages 页面时，点击 `更新` 才会调用到本机后端。

## 2026-04-21 16:08
- 需求目标：把 GitHub Pages 页面的 `更新` 按钮真正跑起来，而不是只停留在前端展示层。
- 改动内容：保留 `docs/data/runtime-config.json` 的 `serviceBaseUrl = http://localhost:4173`；确认本地更新服务在 `127.0.0.1:4173` 可访问；实际通过 `/api/update-data` 执行一次完整更新任务，复用 `日报取数平台` 登录逻辑拉取 `N-1` 日报表并回写工作簿，再重建仪表盘数据。
- 涉及文件：`DEV_CHANGELOG.md`、`docs/data/runtime-config.json`、`data/source/NEV+ICE_xsai.xlsm`、`docs/data/dashboard.json`、`docs/data/dashboard.summary.json`
- 关键命令：`python -X utf8 scripts/serve_dashboard.py --host 127.0.0.1 --port 4173 --no-open-browser --cors-allow-origin https://django604.github.io`、`Invoke-WebRequest -Method Post http://127.0.0.1:4173/api/update-data`、`Invoke-WebRequest http://127.0.0.1:4173/api/update-status`
- 验证结果：任务状态为 `success`，业务日期为 `2026-04-20`；运行目录 `D:\WorkCode\AI_Digest\.runtime\daily_update\20260420_20260421-160530` 中生成 `全国按日-0420.xlsx`、`全国按日ICE-0420.xlsx`、`十五代轩逸按日-0420.xlsx`，并确认 `dashboardChanged = true`、`summaryChanged = true`。
- 回滚方法：停止 `4173` 端口本地服务；如需撤回此次数据更新与配置变更，基于本次提交创建新的反向提交。
- 关联提交（如有）：待补充
- 备注：当前配置适用于“同一台机器打开 GitHub Pages 并调用本机后端”的场景；如果页面在别的机器上打开，`localhost:4173` 自然会指向那台机器自己，不会连回这台电脑。

## 2026-04-21 15:59
- 需求目标：按方案 1 直接执行同机版部署，让 GitHub Pages 页面上的 `数据更新` 按钮默认指向本机独立后端，并实际启动后端服务。
- 改动内容：将 `docs/data/runtime-config.json` 的 `serviceBaseUrl` 配置为 `http://localhost:4173`，用于当前机器上打开 GitHub Pages 页面时直接调用本机更新后端；同步补充本条执行记录。
- 涉及文件：`docs/data/runtime-config.json`、`DEV_CHANGELOG.md`
- 关键命令：`python scripts/serve_dashboard.py --host 127.0.0.1 --port 4173 --no-open-browser --cors-allow-origin https://django604.github.io`
- 验证结果：待补充
- 回滚方法：将 `docs/data/runtime-config.json` 中的 `serviceBaseUrl` 恢复为空，并停止本机 `serve_dashboard.py` 服务。
- 关联提交（如有）：待补充
- 备注：该配置面向“在同一台机器上打开 GitHub Pages 页面并调用本机后端”的场景；若需跨机器使用，仍需把后端暴露为可访问的公网或内网服务地址。

## 2026-04-21 15:45
- 需求目标：按“静态前端 + 独立后端 API”方案，让 GitHub Pages 页面上的 `数据更新` 按钮能够真正调用远端后端执行更新，而不是只在本地同源模式下可用。
- 改动内容：扩展 `scripts/serve_dashboard.py`，新增 `/api/dashboard-data`、`/api/dashboard-summary` 与 `OPTIONS`/CORS 支持，使其既能本地预览，也能作为远端更新后端部署；新增 `docs/data/runtime-config.json`，允许静态前端配置 `serviceBaseUrl` / `dashboardDataUrl`；更新 `docs/assets/app.js`，增加运行时配置加载、远端 API URL 解析、远端 dashboard 数据源切换与不可达提示；补充 `tests/test_serve_dashboard.py`，覆盖数据接口与跨域预检；同步更新 `README.md`、`SCRIPTS.md`。
- 涉及文件：`README.md`、`SCRIPTS.md`、`DEV_CHANGELOG.md`、`scripts/serve_dashboard.py`、`docs/data/runtime-config.json`、`docs/assets/app.js`、`tests/test_serve_dashboard.py`
- 关键命令：`python -X utf8 -m py_compile scripts\serve_dashboard.py tests\test_serve_dashboard.py`、`python -X utf8 -m unittest discover -s tests -v`
- 验证结果：远端后端所需的 `dashboard-data` 与 `update-data` API 已接入同一服务；新增测试将验证 `dashboard-data` 返回结果与 `OPTIONS` 跨域预检响应头。
- 回滚方法：回退本条涉及的后端脚本、前端运行时配置与测试文件；如需撤销远端更新方案，优先使用新的反向提交处理。
- 关联提交（如有）：待补充
- 备注：真正上线时仍需在可访问目标系统的机器上部署 `scripts/serve_dashboard.py`，并把 `docs/data/runtime-config.json` 指向该服务地址。

## 2026-04-21 15:33
- 需求目标：为 `AI_Digest` 落地轻量化浏览器取数系统，复用 `日报取数平台` 登录逻辑抓取 `全国按日`、`全国按日ICE`、`十五代轩逸按日` 三张 `N-1` 日报表，回填 `NEV+ICE_xsai.xlsm` 指定工作表，并在本地页面增加 `更新` 按钮触发整套流程。
- 改动内容：新增 `scripts/fetch_daily_data.py`，串联兄弟项目取数脚本、导出文件匹配、工作簿回填与 dashboard 重建；扩展 `scripts/build_dashboard.py` 支持 `--report-date`/`report_date_override` 且补上 `YYYYMMDD` 日期解析；重写 `scripts/serve_dashboard.py` 暴露 `/api/update-status` 与 `/api/update-data` 并修复任务管理器锁死问题；更新 `docs/index.html`、`docs/assets/styles.css`、`docs/assets/app.js` 增加本地 `更新` 按钮与状态轮询；新增 `tests/test_fetch_daily_data.py`、`tests/test_serve_dashboard.py` 覆盖日期解析、工作簿回填与本地更新 API；同步更新 `README.md`、`SCRIPTS.md`、`.gitignore`。
- 涉及文件：`.gitignore`、`README.md`、`SCRIPTS.md`、`DEV_CHANGELOG.md`、`scripts/build_dashboard.py`、`scripts/fetch_daily_data.py`、`scripts/serve_dashboard.py`、`docs/index.html`、`docs/assets/styles.css`、`docs/assets/app.js`、`tests/test_fetch_daily_data.py`、`tests/test_serve_dashboard.py`
- 关键命令：`python -X utf8 -m py_compile scripts\build_dashboard.py scripts\fetch_daily_data.py scripts\serve_dashboard.py tests\test_fetch_daily_data.py tests\test_serve_dashboard.py`、`python -X utf8 -m unittest discover -s tests -v`
- 验证结果：`14/14` 项单元测试通过；新增测试已覆盖 `YYYYMMDD` 日期解析、工作簿回填、本地更新任务去重与 `/api/update-status`、`/api/update-data` 的真实 HTTP 交互；页面本地模式下具备触发更新的前后端链路。
- 回滚方法：回退本条涉及的脚本、前端文件、测试文件与文档更新；如需撤销已落地功能，优先以新的反向提交处理，不直接删除用户已有数据文件。
- 关联提交（如有）：待补充
- 备注：浏览器取数依赖本地可访问目标系统与可用 Chrome 环境；静态 `GitHub Pages` 页面不会直接执行该本地更新能力。

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
