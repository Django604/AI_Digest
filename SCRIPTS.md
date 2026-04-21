# 脚本使用手册

最后更新：2026-04-21

## scripts/build_dashboard.py

- 路径：`./scripts/build_dashboard.py`
- 作用：读取 `NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx`，抽取线索与来店页面数据，输出静态站点使用的 `JSON`
- 使用方法：
  - `python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json`
  - 指定摘要输出：`python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --summary-out docs/data/dashboard.summary.json`
  - 指定业务日期覆盖：`python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json --report-date 2026-04-20`
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

## scripts/fetch_daily_data.py

- 路径：`./scripts/fetch_daily_data.py`
- 作用：复用 `日报取数平台` 的登录与取数逻辑，抓取 `全国按日`、`全国按日ICE`、`十五代轩逸按日`、`NEV本期来店`、`NEV同期来店`、`ICE本期来店`、`ICE同期来店` 共 7 张 `N-1` 日报表，分别回填 `NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx` 后重建 `docs/data/dashboard.json`
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
  - 更新 `data/source/NEV+ICE_xsai.xlsm` 中 `全国按日NEV`、`全国按日ICE`、`十五代轩逸按日`
  - 更新 `data/source/NEV+ICE_ldai.xlsx` 中 `NEV本期来店`、`NEV同期来店`、`ICE本期来店`、`ICE同期来店`
  - 更新 `docs/data/dashboard.json`
  - 更新 `docs/data/dashboard.summary.json`
- 备注：
  - 默认按当天的 `N-1` 作为业务日期，也可通过 `--business-date` 显式覆盖
  - 脚本运行成功后会自动清理 `.runtime/daily_update/` 临时目录；若带 `--keep-runtime`，会保留导出文件与日志便于排查
  - 该脚本只负责本地更新；静态部署到 `GitHub Pages` 后不会自动具备浏览器取数能力

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

## scripts/publish_dashboard.ps1

- 路径：`./scripts/publish_dashboard.ps1`
- 作用：一键重建 `dashboard.json`，并把发布所需文件提交、推送到 GitHub
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
- 备注：
  - 默认只会提交这 4 个文件：两本 Excel 源文件、`docs/data/dashboard.json` 和 `docs/data/dashboard.summary.json`
  - 如果工作区里已经暂存了别的文件，脚本会主动拦住，避免把无关改动一起推上去

## scripts/serve_dashboard.py

- 路径：`./scripts/serve_dashboard.py`
- 作用：启动一个指向 `docs/` 目录的 `ThreadingHTTPServer`，并在访问 `/docs`、`/AI_Digest` 等“干净 URL”时自动回退到 `index.html`；同时暴露可独立部署的更新 API，供页面上的 `数据更新` 按钮触发浏览器取数流程
- 使用方法：
  - `python scripts/serve_dashboard.py --port 4173 [--open-browser]`
  - 作为 GitHub Pages 远端后端：`python scripts/serve_dashboard.py --host 0.0.0.0 --port 4173 --no-open-browser --cors-allow-origin https://<你的-pages-域名>`
- 运行前提：
  - 本机可用 `Python`（仅使用标准库）
- 输出结果：
  - 控制台展示访问地址，例如 `http://127.0.0.1:4173`
- 备注：
  - 端口被占用或目录缺失时会在控制台给出错误提示；按 `Ctrl+C` 即可退出
  - API 端点包括 `/api/update-status`、`/api/update-data`、`/api/dashboard-data`、`/api/dashboard-summary`
  - `--cors-allow-origin` 可重复传入多个域名；默认允许 `*`
  - 本地更新任务会串行执行；已有任务运行中时，再次点击只会返回当前状态，不会重复启动并发任务

## docs/data/runtime-config.json

- 路径：`./docs/data/runtime-config.json`
- 作用：给静态前端提供远端更新服务地址，让 GitHub Pages 页面能把 `数据更新` 按钮请求转发到独立后端
- 使用方法：
  - `serviceBaseUrl`：填写远端后端基地址，例如 `https://digest-api.example.com`
  - `dashboardDataUrl`：可选；留空时前端默认使用 `${serviceBaseUrl}/api/dashboard-data`
- 备注：
  - 该文件适合保存公开可见的服务地址，不应放置账号密码等敏感配置
  - 如果两个字段都留空，页面会回退到静态 `docs/data/dashboard.json` 浏览模式，`数据更新` 按钮不会真正执行更新

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

## tests/test_serve_dashboard.py

- 路径：`./tests/test_serve_dashboard.py`
- 作用：校验本地更新任务管理器不会锁死，并通过真实 HTTP 请求验证 `/api/update-status` 与 `/api/update-data` 的交互
- 使用方法：
  - `python -m unittest discover -s tests -v`
