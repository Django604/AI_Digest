# 脚本使用手册

最后更新：2026-06-10 00:00

## scripts/build_dashboard.py

- 路径：`./scripts/build_dashboard.py`
- 作用：读取 `NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx`，抽取线索与来店页面数据，输出静态站点使用的 `JSON`
- 使用方法：
  - `python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json`
  - 指定摘要输出：`python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --summary-out docs/data/dashboard.summary.json`
  - 指定业务日期覆盖：`python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --report-date 2026-04-20`
  - CI 保留已提交的源文件时间：`python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --preserve-input-modified-times`
- 运行前提：
  - 本机可用 `Python`
  - 已执行 `pip install -r requirements.txt`
  - 两本源工作簿已经在 Excel 中重算并保存
- 输出结果：
  - `docs/data/dashboard.json`
  - `docs/data/dashboard.summary.json`
- 备注：
  - 脚本优先读取面板页的缓存展示结果，而不是在 `Python` 里复刻全部 Excel 公式；这样和原模板展示更一致，但前提是源文件已保存最新计算结果
  - 如果只有 `generatedAt` 变化、其余内容没变，脚本不会重复改写 `docs/data/dashboard.json`，更适合定时任务或 CI 场景
  - 摘要文件会输出报表日期、输入文件修改时间、dashboard 数量、section 数量以及本次是否真的发生内容更新
  - `--report-date` 支持 `YYYY-MM-DD` 与 `YYYYMMDD`，用于本地取数后强制按指定业务日期重建页面数据，避免依赖 Excel 缓存公式日期
  - `--preserve-input-modified-times` 仅供 GitHub Actions 重建使用：它会严格复用现有 dashboard 与 summary 中已提交的两本源工作簿修改时间，避免 checkout 后的 UTC 文件时间覆盖本地实际记录；本地更新不要启用该参数
  - 趋势表的 `columnMeta` 现在会同时输出 `holiday / weekend / makeupWorkday / regularWorkday` 语义，前端据此显示 `节 / 周 / 班` 标签并区分补班日
  - `NEV 线索趋势` 会从 `全国按日NEV` 精确匹配车型 `2026款探陆` 并生成独立月度对照与趋势区块；`NEV 总盘` 和每日简报四车合计仍只统计 `NX8 / N7 / N6 / 天籁·鸿蒙座舱`，`全车系有效线索管控` 则包含 `2026款探陆`；2026 年 7 月在 `目标竖版` 暂无该车型时使用月目标 `7,759` 的兜底序列，趋势表和图表直接删除 7 月 1—15 日列并从 7 月 16 日起展示，后续出现同名车型目标后优先读取工作簿数据

## scripts/purge_jsdelivr_cache.py

- 路径：`./scripts/purge_jsdelivr_cache.py`
- 作用：遗留的 jsDelivr CDN 缓存诊断工具；正式发布链与 GitHub Pages workflow 均不再调用
- 使用方法：
  - 清理默认公开入口缓存：`python scripts/purge_jsdelivr_cache.py`
  - 指定仓库与分支：`python scripts/purge_jsdelivr_cache.py --repository django604/AI_Digest --ref main`
  - 调整重试次数与单次超时：`python scripts/purge_jsdelivr_cache.py --attempts 3 --timeout 20`
  - 只清理日常发布数据：`python scripts/purge_jsdelivr_cache.py --dashboard-only`
  - 针对其他静态目录做验证：`python scripts/purge_jsdelivr_cache.py --docs-dir <目录>`
- 输出结果：
  - 逐文件输出 `[OK]` 或 `[FAIL]` 及实际 purge URL
  - 最后输出总文件数、成功数、失败数和关键文件失败数
- 备注：
  - 正式公开入口仅为 `https://django604.github.io/AI_Digest/`
  - 该脚本只保留给历史问题诊断，不应作为 Pages 是否发布成功的判断条件
  - SVG 入口、前端 JS/CSS、当前 dashboard、月度索引及所有月度 dashboard/summary 属于脚本内部的关键文件；任一关键文件清理失败时脚本返回非零退出码，但不会影响正式 Pages 发布
  - purge API 返回 `throttled=true` 表示该路径刚刚清理过，脚本会记录为 `[THROTTLED]` 并按成功处理，避免紧邻的自动/手动刷新互相误伤
  - Python 调用方可通过 `repo_paths` 只诊断指定仓库路径；`--dashboard-only` 对应 5 条数据路径
  - 图片、字体等非关键资源也会清理并报告失败，但不会因单个非关键文件失败阻断 dashboard 发布
  - purge API 不需要账号、Token 或其他秘密信息

## scripts/fetch_daily_data.py

- 路径：`./scripts/fetch_daily_data.py`
- 作用：复用 `日报取数平台` 的登录与取数逻辑，抓取 `全国按日`、`全国按日ICE`、`NEV本期来店`、`NEV同期来店`、`ICE本期来店`、`ICE同期来店` 共 6 张 `N-1` 日报表，分别回填 `NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx` 后重建 `docs/data/dashboard.json`
- 使用方法：
  - `python scripts/fetch_daily_data.py`
  - 指定业务日期：`python scripts/fetch_daily_data.py --business-date 2026-04-20`
  - 调试浏览器流程：`python scripts/fetch_daily_data.py --business-date 2026-04-20 --headed --keep-runtime`
- 运行前提：
  - 本机可用 `Python`
  - 已执行 `pip install -r requirements.txt`
  - 同级目录存在 `../日报取数平台/日报线索NEV源/getdata.py` 与 `../日报取数平台/日报线索ICE源/getdata.py`
  - 运行环境可以正常打开本地 Chrome 并访问目标系统
- 输出结果：
  - 更新 `data/source/NEV+ICE_xsai.xlsm` 中 `全国按日NEV`、`全国按日ICE`
  - 更新 `data/source/NEV+ICE_ldai.xlsx` 中 `NEV本期来店`、`NEV同期来店`、`ICE本期来店`、`ICE同期来店`
  - 更新 `docs/data/dashboard.json`
  - 更新 `docs/data/dashboard.summary.json`
- 备注：
  - 默认按当天的 `N-1` 作为业务日期，也可通过 `--business-date` 显式覆盖
  - 十五代轩逸已于 `2026-07-15` 停更：不再抓取或回填 `十五代轩逸按日`，页面继续保留截至该日的冻结数据
  - 脚本运行成功后会自动清理 `.runtime/daily_update/` 临时目录；若带 `--keep-runtime`，会保留导出文件与日志便于排查
  - NEV 线索中的 `全国按日` 会通过 `scripts/run_leads_nev_exports.py` 内部包装器复用 `日报线索NEV源`，并在运行时显式清空 FineReport 平台默认的 `营业状态` 筛选，避免只取 `营业店`
  - NEV 来店中的 `本期/同期` 会通过 `scripts/run_arrival_nev_exports.py` 内部包装器复用 `日报来店NEV源` 的登录态与参数模板，并在后台执行 `tab/execute -> REPORT2 -> chart.data` 直接抓取自定义按日序列，不依赖前端页面点选与 SVG 解析
  - ICE 来店中的 `本期/同期` 会通过 `scripts/run_arrival_ice_exports.py` 内部包装器强制把 Tableau 交叉表缩略图入口锁定到 `来店批次分车系汇总表_按天T`，同时保留实际导出 sheet 名 `E3S报表样式` 以匹配 `sheetdocId`
  - 该脚本只负责本地更新；静态部署到 `GitHub Pages` 后不会自动具备浏览器取数能力

## scripts/run_leads_nev_exports.py

- 路径：`./scripts/run_leads_nev_exports.py`
- 作用：作为 `日报线索NEV源/getdata.py` 的轻量包装器，仅对 `全国按日` 报表运行时注入 `营业状态: []`，清空 FineReport 平台默认勾选的营业状态条件后再交给原取数脚本导出
- 使用方法：
  - 一般不单独调用，由 `python scripts/fetch_daily_data.py ...` 自动串联
  - 需要单独验证时可执行：`python scripts/run_leads_nev_exports.py --business-date 2026-06-09 --report-keys national_daily --keep-runtime`
- 备注：
  - 该包装器不会改动兄弟项目源码，只在运行时 monkey-patch `report_fetcher.report_configs.REPORT_CONFIGS`
  - 空列表 `[]` 表示该筛选条件不选任何营业状态，用来覆盖平台新增的默认 `营业店`

## scripts/run_arrival_nev_exports.py

- 路径：`./scripts/run_arrival_nev_exports.py`
- 作用：作为 `日报来店NEV源/getdata.py` 的轻量包装器，仅对 `NEV本期来店`、`NEV同期来店` 两份 FineReport 报表切换到 `自定义` tab，并通过后台 `chart.data` 接口直接提取按日来店数据后导出为两列表 Excel
- 使用方法：
  - 一般不单独调用，由 `python scripts/fetch_daily_data.py ...` 自动串联
  - 需要单独验证时可执行：`python scripts/run_arrival_nev_exports.py --business-date 2026-04-21 --report-keys store_current_period,store_same_period --safe-bootstrap --capture-wait-ms 30000`
- 备注：
  - 该包装器不会改动兄弟项目源码，只在运行时修正目标报表 URL、参数模板和导出策略
  - 若 `REPORT2 load/content` 直接返回的不是按日两列表，而是“合计值 + simplechart”，包装器会继续从 `simplechart` 里提取 `chartID` 与 `ecName`，再请求 `chart.data` 还原每日来店量

## scripts/run_arrival_ice_exports.py

- 路径：`./scripts/run_arrival_ice_exports.py`
- 作用：作为 `日报来店ICE源/getdata.py` 的轻量包装器，仅对 `ICE本期来店`、`ICE同期来店` 两份 Tableau 报表改写导出配置，强制使用 `来店批次分车系汇总表_按天T` 的缩略图入口
- 使用方法：
  - 一般不单独调用，由 `python scripts/fetch_daily_data.py ...` 自动串联
  - 需要单独验证时可执行：`python scripts/run_arrival_ice_exports.py --business-date 2026-04-20 --report-keys store_batch_vehicle_summary_本期_来店,store_batch_vehicle_summary_同期_来店`
- 备注：
  - 该包装器不会改动兄弟项目源码，只在运行时 monkey-patch `build_effective_report_configs`
  - 这里不能把 `crosstab_sheet_name` 直接改成 `来店批次分车系汇总表_按天T`，否则 Tableau 导出响应里会因为拿不到真实的 `sheetdocId` 而失败

## scripts/rebuild_dashboard.ps1

- 路径：`./scripts/rebuild_dashboard.ps1`
- 作用：按项目当前默认路径一键重建 `docs/data/dashboard.json`
- 使用方法：
  - `powershell -ExecutionPolicy Bypass -File scripts/rebuild_dashboard.ps1`
  - 指定输入输出路径：`powershell -ExecutionPolicy Bypass -File scripts/rebuild_dashboard.ps1 -Workbook data/source/NEV+ICE_xsai.xlsm -ArrivalWorkbook data/source/NEV+ICE_ldai.xlsx -Out docs/data/dashboard.json -SummaryOut docs/data/dashboard.summary.json`
- 运行前提：
  - 本机可用 `Python`
  - 已执行 `pip install -r requirements.txt`
  - `data/source/NEV+ICE_xsai.xlsm` 与 `data/source/NEV+ICE_ldai.xlsx` 已更新并保存
- 输出结果：
  - 更新 `docs/data/dashboard.json`
  - 更新 `docs/data/dashboard.summary.json`
- 备注：
  - 这个脚本只负责本地重建数据；要让 GitHub Pages 同步更新，仍然需要把变更提交并推送到 GitHub
  - 脚本会优先使用 `python`，找不到时自动回退到 `py -3`

## scripts/scheduled_update_runner.py

- 路径：`./scripts/scheduled_update_runner.py`
- 作用：作为 Windows 计划任务的实际执行入口，按当天 `N-1` 自动调用 `fetch_daily_data.py` 背后的 `run_update()`；支持 `interactive` 弹窗模式与 `silent` 静默模式，并通过文件锁避免双任务重复回填同一批数据
- 使用方法：
  - 手动静默验证：`python scripts/scheduled_update_runner.py --mode silent`
  - 调试登录态弹窗 + 有头浏览器：`python scripts/scheduled_update_runner.py --mode interactive --headed --suppress-start-message`
  - 指定业务日期：`python scripts/scheduled_update_runner.py --mode interactive --business-date 2026-04-21`
- 输出结果：
  - 写入 `.runtime/scheduled_update/<timestamp>/scheduled_update.log`
  - 写入 `.runtime/scheduled_update/<timestamp>/run_meta.json`
  - 写入 `.runtime/scheduled_update/<timestamp>/result.json`
- 备注：
  - 正常计划任务场景下不需要额外带 `--suppress-*` 参数；`silent` 模式会自动关闭全部弹窗
  - `interactive` 模式下，启动窗口弹出后若 2 分钟内未点击“开始更新”，系统会自动继续执行
  - 一旦开始执行，窗口不会中途消失，而是切换为进度条视图，并根据日志阶段持续推进完成进度
  - 更新完成或失败后，结果会在同一个窗口里展示，随后自动关闭
  - 无论是 `interactive` 还是 `silent`，都会写同一套日志 / 结果文件；若发现已有任务持锁，当前任务会记一次 `skipped` 并直接退出

## scripts/register_daily_update_task.ps1

- 路径：`./scripts/register_daily_update_task.ps1`
- 作用：在当前 Windows 机器上注册每天自动执行的双计划任务，默认前缀为 `AI_Digest_Daily_Update`
- 使用方法：
  - 直接注册默认任务：`powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1`
  - 自定义时间：`powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1 -Time 09:00`
  - 自定义静默兜底延迟：`powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1 -Time 09:00 -SilentDelayMinutes 1`
  - 自定义 Python 路径：`powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1 -PythonPath C:\Python313\pythonw.exe`
- 备注：
  - 计划任务按当前 Windows 本地时区执行；这台机器的场景即北京时间
  - 注册脚本会优先使用 `pythonw.exe`，避免计划任务运行时弹黑色控制台窗口
  - 脚本默认注册两条任务：`AI_Digest_Daily_Update_Interactive` 会在登录态下弹窗执行，`AI_Digest_Daily_Update_Silent` 会以 `SYSTEM` 服务账号在未登录时静默兜底
  - 两条任务通过 `scheduled_update_runner.py` 内部的文件锁互斥，避免同时回填 Excel 与 dashboard 数据

## scripts/publish_dashboard.ps1

- 路径：`./scripts/publish_dashboard.ps1`
- 作用：一键重建 `dashboard.json`，把发布所需文件提交并推送到 GitHub；随后由 GitHub Actions 自动部署 Pages
- 使用方法：
  - `powershell -ExecutionPolicy Bypass -File scripts/publish_dashboard.ps1`
  - 指定提交信息：`powershell -ExecutionPolicy Bypass -File scripts/publish_dashboard.ps1 -CommitMessage "Update dashboard data"`
  - 指定远程与分支：`powershell -ExecutionPolicy Bypass -File scripts/publish_dashboard.ps1 -Remote origin -Branch main`
- 运行前提：
  - 当前目录已经初始化为 Git 仓库
  - 已配置好 Git 远程仓库，例如 `origin`
  - 本机可用 `Python`
  - 已执行 `pip install -r requirements.txt`
  - `data/source/NEV+ICE_xsai.xlsm` 与 `data/source/NEV+ICE_ldai.xlsx` 已更新并保存
- 输出结果：
  - 更新 `docs/data/dashboard.json`
  - 更新 `docs/data/dashboard.summary.json`
  - 自动提交并推送发布相关文件
  - 推送成功后触发 GitHub Pages workflow
- 备注：
  - 这个脚本现在只是薄封装，实际的 rebuild / stage / commit / push 逻辑在 `./scripts/dashboard_publish.py`
  - 默认只会提交这 4 个文件：两本 Excel 源文件、`docs/data/dashboard.json` 和 `docs/data/dashboard.summary.json`
  - 如果工作区里已经暂存了别的文件，脚本会主动拦住，避免把无关改动一起推上去

## scripts/dashboard_publish.py

- 路径：`./scripts/dashboard_publish.py`
- 作用：统一承担发布前检查、重建、`git add`、`git commit` 与 `git push`；Pages 部署由 GitHub Actions 独立完成
- 使用方法：
  - `python scripts/dashboard_publish.py --remote origin --branch main`
  - 跳过重建：`python scripts/dashboard_publish.py --skip-rebuild`
  - 允许已有暂存文件：`python scripts/dashboard_publish.py --allow-existing-staged`
- 备注：
  - 定时更新与附魔工作台手动兜底会调用这个 Python 入口
  - `git push` 带 300 秒超时，若被中断会自动重试一次，并在失败时保留完整的阶段与命令信息
  - Python 调用方可传入 `push_if_no_changes=True`，在没有新的发布文件可提交时仍执行 `git push`；默认值为 `False`，原定时更新与更新后自动发布行为不变
  - `git push` 成功即视为本地发布完成，不再等待或调用任何 CDN；远端 workflow 继续完成 GitHub Pages 部署

## scripts/serve_dashboard.py

- 路径：`./scripts/serve_dashboard.py`
- 作用：启动一个指向 `docs/` 目录的 `ThreadingHTTPServer`，并在访问 `/docs`、`/AI_Digest` 等“干净 URL”时自动回退到 `index.html`；同时暴露 dashboard 数据和历史归档索引；手动兜底更新与月度归档发布入口已迁移到附魔工作台
- 使用方法：
  - `python scripts/serve_dashboard.py --port 4173 [--open-browser]`
  - 作为 GitHub Pages 远端后端：`python scripts/serve_dashboard.py --host 0.0.0.0 --port 4173 --no-open-browser --cors-allow-origin https://<你的-pages-域名>`
  - 只想本地刷新、不自动推 GitHub 时：`python scripts/serve_dashboard.py --port 4173 --no-auto-publish`
  - 自定义访问日志目录：`python scripts/serve_dashboard.py --access-log-dir .runtime\\custom_access_logs`
  - 关闭访问日志：`python scripts/serve_dashboard.py --no-access-log`
- 运行前提：
  - 本机可用 `Python`（仅使用标准库）
- 输出结果：
  - 控制台展示访问地址，例如 `http://127.0.0.1:4173`
- 备注：
  - 端口被占用或目录缺失时会在控制台给出错误提示；按 `Ctrl+C` 即可退出
  - API 端点包括 `/api/update-status`、`/api/update-data`、`/api/dashboard-data`、`/api/dashboard-summary`、`/api/dashboard-archive`
  - `--cors-allow-origin` 可重复传入多个域名；默认允许 `*`
  - 默认会把页面访问与关键 API 访问写到 `.runtime/access_logs/visits-YYYYMMDD.jsonl`，记录 `clientIp`、`remoteAddr`、`forwardedFor`、时间、路径、状态码、`User-Agent` 与 `Referer`
  - 访问日志只保留在服务端，不会展示在前端页面；静态资源和 `/api/update-status` 这类高频噪声请求默认不写入
  - `/api/update-status` 与 `/api/update-data` 仅保留兼容响应，会提示手动兜底更新已迁移到附魔工作台
  - “保存当前月为历史数据”写入动作已迁移到 `附魔工作台` 的 `/api/archive-current-month`，避免 GitHub Pages 静态站点发起无效 POST
  - 月初归档开启新月份时，会在 `docs/data/monthly/YYYY-MM/` 生成空白 dashboard/summary，并让新月份入口指向该空白归档，避免新月份继续展示上月末 live 数据

## start_dashboard_server.bat

- 路径：`./start_dashboard_server.bat`
- 作用：为 `scripts/serve_dashboard.py` 提供双击即可启动的 Windows 快捷入口，默认启动本机仪表盘服务并自动打开浏览器
- 使用方法：
  - 资源管理器中双击 `start_dashboard_server.bat`
  - 需要透传参数时也可在命令行执行：`start_dashboard_server.bat --no-auto-publish`
- 运行前提：
  - 本机已安装 `Python`，或项目目录下存在 `.venv\Scripts\python.exe` / `venv\Scripts\python.exe`
- 备注：
  - 脚本会优先使用项目内虚拟环境，其次尝试 `python`，最后回退到 `py -3`
  - 额外参数会原样转发给 `scripts/serve_dashboard.py`
  - 启动后按 `Ctrl+C` 即可停止服务；若启动失败，窗口会保留错误信息，避免一闪而过

## docs/data/runtime-config.json

- 路径：`./docs/data/runtime-config.json`
- 作用：给静态前端提供远端数据服务地址，让 GitHub Pages 页面可读取独立后端的最新 dashboard 数据
- 使用方法：
  - `serviceBaseUrl`：填写远端后端基地址，例如 `https://digest-api.example.com`
  - `dashboardDataUrl`：可选；留空时前端默认使用 `${serviceBaseUrl}/api/dashboard-data`
- 备注：
  - 该文件适合保存公开可见的服务地址，不应放置账号密码等敏感配置
  - 如果两个字段都留空，公开页面会回退到静态 `docs/data/dashboard.json` 浏览模式；此时如需手动兜底或月度归档发布，请打开 `附魔工作台`

## tests/test_build_dashboard.py

- 路径：`./tests/test_build_dashboard.py`
- 作用：校验 `build_dashboard.py` 的关键输出结构，以及源工作簿缺 sheet / 缺列 / 参数日期无效时能否及时失败
- 使用方法：
  - `python -m unittest discover -s tests -v`

## tests/test_fetch_daily_data.py

- 路径：`./tests/test_fetch_daily_data.py`
- 作用：校验 `fetch_daily_data.py` 的业务日期解析、导出文件匹配、工作簿回填与 `report_date_override` 重建逻辑
- 使用方法：
  - `python -m unittest discover -s tests -v`

## tests/test_run_arrival_ice_exports.py

- 路径：`./tests/test_run_arrival_ice_exports.py`
- 作用：校验 ICE 来店包装器会把导出缩略图入口锁定到 `来店批次分车系汇总表_按天T`，同时保留真实的 `crosstab_sheet_name`
- 使用方法：
  - `python -m unittest discover -s tests -v`

## tests/test_serve_dashboard.py

- 路径：`./tests/test_serve_dashboard.py`
- 作用：校验本地 dashboard 服务的静态数据、历史归档、访问日志和迁移提示 API 行为
- 使用方法：
  - `python -m unittest discover -s tests -v`
## Auto Publish Update

- `scripts/scheduled_update_runner.py` now supports `--auto-publish`, `--publish-remote`, `--publish-branch`, and `--publish-commit-message`.
- `scripts/register_daily_update_task.ps1` now supports `-AutoPublish`, `-PublishRemote`, and `-PublishBranch`.
- Auto publish calls `scripts/dashboard_publish.py --skip-rebuild`, so the scheduled task reuses the existing guarded git add/commit/push flow instead of rebuilding `dashboard.json` twice.
- If the silent fallback task runs as `SYSTEM`, make sure `SYSTEM` can use Git credentials on this machine, or the refresh step may succeed while publish still fails.
## scripts/run_silent_test_once.ps1

- 路径：`./scripts/run_silent_test_once.ps1`
- 作用：用于本次锁屏静默更新验证，调用 `scheduled_update_runner.py --mode silent --keep-runtime`，并在传入 `TaskName` 时于执行结束后注销对应的临时计划任务
- 使用方法：一般不单独手动运行，由一次性 Windows 计划任务以 `-File scripts/run_silent_test_once.ps1 -TaskName <task-name>` 方式调用
- 备注：这是临时测试包装器，不会改动正式日常计划任务的触发时间
## 月度归档

- `scripts/build_dashboard.py`：除当前 `docs/data/dashboard.json`、`docs/data/dashboard.summary.json` 外，还会同步生成 `docs/data/monthly/YYYY-MM/dashboard.json`、`docs/data/monthly/YYYY-MM/dashboard.summary.json`，并维护 `docs/data/monthly/index.json`。
- `scripts/serve_dashboard.py`：提供 `/api/dashboard-archive`；`/api/dashboard-data` 与 `/api/dashboard-summary` 支持 `?month=YYYY-MM`，供前端按年月加载历史归档或当前源数据月份入口。写入型的月度归档发布已迁移到 `附魔工作台`；若源数据更新时间为每月首日，会为新月份写入空白归档并将索引入口指向该空白文件。

## scripts/probe_system_git_publish.ps1

- 路径：`./scripts/probe_system_git_publish.ps1`
- 作用：以 `SYSTEM` 身份验证当前仓库的 Git 自动发布前置条件，依次检查系统级 `safe.directory`、仓库 `core.sshCommand`、`git ls-remote origin` 与 `git push --dry-run origin HEAD:main`
- 使用方法：一般不手动双击运行，而是通过一次性 `SYSTEM` 计划任务调用，并将结果写入 `.runtime/system_git_probe/*.json`
- 备注：这个脚本只做 Git / SSH 链路探测，不会修改业务数据，也不会执行真实 `git push`
