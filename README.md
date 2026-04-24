# AI Digest Dashboard

把 `NEV+ICE` 线索与来店简报做成静态 Web 版，并为 `GitHub Pages` 部署准备好数据抽取脚本和自动发布工作流。

## 为什么不用 Django

`GitHub Pages` 只能托管静态内容，不能运行 Django 服务端代码。这个项目改用：

- `Python + openpyxl` 读取本地 Excel 源数据
- 静态 `HTML/CSS/JavaScript` 渲染页面
- `GitHub Actions` 在推送后自动生成 `docs/data/dashboard.json`
- `GitHub Pages` 发布 `docs/` 目录

这套组合和你的部署目标是对齐的，`Django` 在这里属于用力过猛还跑不起来。

## 目录

- `data/source/NEV+ICE_xsai.xlsm`：线索源工作簿
- `data/source/NEV+ICE_ldai.xlsx`：来店源工作簿
- `requirements.txt`：Python 依赖清单
- `scripts/build_dashboard.py`：从 Excel 抽取页面数据
- `scripts/fetch_daily_data.py`：复用日报取数平台登录逻辑，抓取线索 + 来店共 7 张日报表并回填两本工作簿
- `scripts/run_arrival_nev_exports.py`：NEV 来店导出包装器，运行时切到 FineReport `自定义` tab 并通过后台 `chart.data` 直接抓取按日序列
- `scripts/run_arrival_ice_exports.py`：ICE 来店导出包装器，运行时把 Tableau 导出入口锁定到 `来店批次分车系汇总表_按天T`
- `scripts/scheduled_update_runner.py`：定时自动更新执行入口，支持登录态弹窗执行与未登录静默执行
- `scripts/register_daily_update_task.ps1`：Windows 计划任务注册脚本，默认注册“登录态弹窗 + 未登录静默兜底”两条计划任务
- `scripts/rebuild_dashboard.ps1`：Windows 下本地一键重建 `dashboard.json`
- `docs/data/runtime-config.json`：前端远端更新服务配置
- `scripts/publish_dashboard.ps1`：Windows 下本地一键重建并推送到 GitHub
- `docs/`：静态站点
- `.github/workflows/deploy-pages.yml`：自动发布工作流
- `reports/excel_analysis.md`：Excel 结构分析

## 本地使用

1. 更新 `data/source/NEV+ICE_xsai.xlsm` 和 `data/source/NEV+ICE_ldai.xlsx`
2. 首次运行先执行 `pip install -r requirements.txt`
3. 运行 `powershell -ExecutionPolicy Bypass -File scripts/rebuild_dashboard.ps1`
   这会同时生成 `docs/data/dashboard.json` 和 `docs/data/dashboard.summary.json`
4. 运行 `python scripts/serve_dashboard.py --port 4173`，需要自动打开浏览器时可以附加 `--open-browser`
5. 打开 `http://127.0.0.1:4173`，即使误写成 `/docs` 或 `/AI_Digest` 等路径也会被回退到 `index.html`
6. 如果需要直接走浏览器取数，可在本地服务页面左侧点击 `数据更新`；它会按当天 `N-1` 抓取 `全国按日`、`全国按日ICE`、`十五代轩逸按日`、`NEV本期来店`、`NEV同期来店`、`ICE本期来店`、`ICE同期来店`，分别更新 `NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx` 后再重建页面数据
7. 如需指定业务日期或保留运行痕迹排查问题，可直接执行 `python scripts/fetch_daily_data.py --business-date 2026-04-20 --keep-runtime`
   其中 `NEV本期来店`、`NEV同期来店` 会通过内部包装器直接走 FineReport 后台 `chart.data` 导出链，`ICE本期来店`、`ICE同期来店` 会通过内部包装器强制走 `来店批次分车系汇总表_按天T` 的 Tableau 交叉表缩略图入口
8. 如需让这台电脑每天自动更新，可执行 `powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1`
   默认会注册两条每天自动运行的 Windows 计划任务：`09:00` 的登录态交互任务会弹出流程窗口，`09:01` 的静默兜底任务会以 `SYSTEM` 服务账号在未登录时后台执行；两者共享同一把运行锁，不会重复更新同一批数据
9. 如果你在 `09:00` 左右已经登录 Windows，就会看到启动窗口；2 分钟内没有点击“开始更新”也没事，系统会自动继续执行，执行过程中窗口不会消失，而是显示完成进度条，最终在同一窗口展示更新结果后自动关闭
10. 如果 `09:00` 时没有登录 Windows，也不需要提前打开网页、VS Code 或手动点任何按钮；`09:01` 的静默任务会直接在后台完成更新，并继续把日志与结果写入 `.runtime/scheduled_update/`

## GitHub Pages 点击更新

1. 在一台能访问目标取数系统的机器上运行后端服务：
   `python scripts/serve_dashboard.py --host 0.0.0.0 --port 4173 --no-open-browser --cors-allow-origin https://<你的-pages-域名>`
2. 把 `docs/data/runtime-config.json` 里的 `serviceBaseUrl` 改成这个后端地址，例如 `https://digest-api.example.com`
3. 如无特殊需要，`dashboardDataUrl` 留空即可，前端会自动改为从 `${serviceBaseUrl}/api/dashboard-data` 读取最新 dashboard 数据
4. 把这份配置随站点一起发布到 GitHub Pages 后，页面上的 `数据更新` 按钮就会真正调用远端后端执行更新，而不是只显示静态文案

注意：
- `runtime-config.json` 里只放后端访问地址，不要放账号密码之类的敏感信息
- 不要把 `http://localhost:4173` 这类仅本机可访问的地址直接提交到仓库；这会让别人打开 GitHub Pages 时去请求他自己电脑上的 `localhost`，页面自然直接报 `Failed to fetch`
- 真正的登录账号、密码、Chrome 环境与 Excel 文件都应保留在后端服务所在机器

## 测试

- 运行 `python -m unittest discover -s tests -v`
- 当前测试覆盖构建输出的关键结构、源工作簿缺 sheet / 缺列 / 参数日期异常等输入校验，以及本地/远端更新 API、线索 / 来店双工作簿回填逻辑与跨域预检
- GitHub Actions 在发布前也会先跑同一套测试，避免坏数据直接上 Pages

## 首次部署到 GitHub Pages

1. 把当前项目推到一个 GitHub 仓库的 `main` 分支
2. 打开仓库 `Settings > Pages`
3. 在 `Build and deployment` 中选择 `GitHub Actions`
4. 确认仓库的 Actions 权限允许工作流运行

## 日常更新方式

1. 本地用 Excel 更新源数据并保存
2. 直接运行 `powershell -ExecutionPolicy Bypass -File scripts/publish_dashboard.ps1`
3. 脚本会自动重建 `dashboard.json` 与 `dashboard.summary.json`，并只提交以下发布相关文件：
   - `data/source/NEV+ICE_xsai.xlsm`
   - `data/source/NEV+ICE_ldai.xlsx`
   - `docs/data/dashboard.json`
   - `docs/data/dashboard.summary.json`
4. `GitHub Actions` 自动重新生成并发布页面
5. 别人打开 GitHub Pages 链接时，就能看到最新数据

注意：`GitHub Pages` 不能直接读取你电脑本地文件。你在本地更新完数据后，必须把变更推送到 GitHub，网页才会同步更新。

## 注意

- 当前方案读取的是 Excel 保存后的缓存结果。你更新完源数据后，必须先让 Excel 完成重算并保存，否则页面会拿到旧结果。
- 工作流已经改成读取当前实际使用的两本源文件：`NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx`。
- `docs/data/dashboard.summary.json` 提供了报表日期、输入文件修改时间、dashboard 数量和本次是否真的发生内容变更，方便后续定时任务或自动巡检直接读取。
- 页面上的 `数据更新` 按钮在配置了 `docs/data/runtime-config.json` 的 `serviceBaseUrl` 后，可以从 `GitHub Pages` 直接调用远端后端执行更新；未配置时会退化为静态浏览模式。
- 即使远端更新服务临时不可达，页面现在也会自动回退到已发布的静态 `docs/data/dashboard.json`，避免整页直接加载失败。
## Auto Publish Notes

- To let scheduled updates publish to GitHub Pages automatically, register the tasks with `powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1 -AutoPublish -PublishRemote origin -PublishBranch main`.
- The scheduled runner now supports `--auto-publish`, `--publish-remote`, `--publish-branch`, and `--publish-commit-message`.
- Auto publish reuses `scripts/publish_dashboard.ps1 -SkipRebuild`, so it stages only the two workbook files plus `docs/data/dashboard.json` and `docs/data/dashboard.summary.json`.
- No Codex approval is needed when the scheduled task runs later on this machine. The task uses the local account context configured in Windows Task Scheduler.
- If the silent fallback task runs as `SYSTEM`, Git credentials must also be available to `SYSTEM`; otherwise data refresh may succeed but `git push` can still fail.
