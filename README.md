# AI Digest Dashboard

把 `NEV+ICE` 线索与来店简报做成静态 Web 版，并通过独立工作流并行发布到 `GitHub Pages` 与 `Cloudflare Pages`。

## 公开访问入口

- 公司网络入口：https://django604-ai-digest.pages.dev/
- 原 GitHub Pages 入口：https://django604.github.io/AI_Digest/

每次将 `main` 分支推送到 GitHub 后，`Deploy Dashboard To Pages` 与 `Deploy Dashboard To Cloudflare Pages` 会分别完成测试、数据重建和站点部署，任一平台失败都不会关闭或替换另一平台。

## 为什么不用 Django

`GitHub Pages` 只能托管静态内容，不能运行 Django 服务端代码。这个项目改用：

- `Python + openpyxl` 读取本地 Excel 源数据
- 静态 `HTML/CSS/JavaScript` 渲染页面
- `GitHub Actions` 在推送后自动生成 `docs/data/dashboard.json`
- `GitHub Pages` 与 `Cloudflare Pages` 分别发布 `docs/` 目录

这套组合和你的部署目标是对齐的，`Django` 在这里属于用力过猛还跑不起来。

## 目录

- `data/source/NEV+ICE_xsai.xlsm`：线索源工作簿
- `data/source/NEV+ICE_ldai.xlsm`：来店源工作簿
- `config/dashboard_targets.json`：全车系有效线索月目标配置，由附魔工作台的“手动兜底更新”工具维护
- `requirements.txt`：Python 依赖清单（包含每日取数所需的 Playwright Python 包）
- `scripts/build_dashboard.py`：从 Excel 抽取页面数据
- `scripts/purge_jsdelivr_cache.py`：遗留 CDN 诊断工具，不接入正式发布流程
- `scripts/fetch_daily_data.py`：复用日报取数平台登录逻辑，默认抓取线索 + 来店共 10 张日报表并回填两本工作簿；`--leads-only` 只更新 `NEV+ICE_xsai.xlsm` 中 4 张全国按日线索表；NEV 线索参数上下文最多等待 `30s`，NEV 来店安全初始化最多等待 `300s`，缺日后的网页查询最多等待 `600s`；兼容 NEV / ICE 上期来店的不同导出日期后缀；十五代轩逸历史数据保留但不再更新或展示
- `scripts/run_leads_nev_exports.py`：NEV 线索全国按日导出包装器，运行时清空 FineReport 默认 `营业状态` 筛选，并抓取去年同期完整自然月
- `scripts/run_leads_ice_exports.py`：ICE 线索全国按日导出包装器，运行时扩展日期规则并抓取去年同期完整自然月
- `scripts/run_arrival_nev_exports.py`：NEV 来店导出包装器，优先通过 FineReport 后台 `chart.data` 抓取按日序列；本期截止业务日，上期与同期抓取完整自然月；接口缺少目标日期时自动切到网页 `自定义` tab 查询并等待完整图表
- `scripts/run_arrival_ice_exports.py`：ICE 来店导出包装器，运行时把 Tableau 导出入口锁定到 `来店批次分车系汇总表_按天T`；本期截止业务日，上期与同期抓取完整自然月
- `scripts/scheduled_update_runner.py`：定时自动更新执行入口，支持登录态弹窗执行与失败后的二次静默更新
- `scripts/register_daily_update_task.ps1`：Windows 计划任务注册脚本，默认注册“登录态首轮更新 + 未成功时静默兜底”两条计划任务
- `scripts/rebuild_dashboard.ps1`：Windows 下本地一键重建 `dashboard.json`
- `scripts/dashboard_publish.py`：统一处理 `rebuild -> git add -> commit -> push` 的发布核心逻辑
- `start_dashboard_server.bat`：Windows 下双击启动 `serve_dashboard.py` 的快捷入口
- `docs/data/runtime-config.json`：前端远端更新服务配置
- `scripts/publish_dashboard.ps1`：Windows 下本地一键重建并推送到 GitHub
- `docs/`：静态站点
- `.github/workflows/deploy-pages.yml`：自动发布工作流
- `.github/workflows/deploy-cloudflare-pages.yml`：独立的 Cloudflare Pages 自动发布工作流
- `reports/excel_analysis.md`：Excel 结构分析

## 本地使用

1. 更新 `data/source/NEV+ICE_xsai.xlsm` 和 `data/source/NEV+ICE_ldai.xlsm`
2. 首次运行先执行 `pip install -r requirements.txt`
3. 运行 `powershell -ExecutionPolicy Bypass -File scripts/rebuild_dashboard.ps1`
   这会同时生成 `docs/data/dashboard.json` 和 `docs/data/dashboard.summary.json`
4. 双击 `start_dashboard_server.bat`，或手动运行 `python scripts/serve_dashboard.py --port 4173`
5. 打开 `http://127.0.0.1:4173`，即使误写成 `/docs` 或 `/AI_Digest` 等路径也会被回退到 `index.html`
   服务端会默认把页面/API 访问记录写到 `.runtime/access_logs/visits-YYYYMMDD.jsonl`，其中包含 `clientIp`、时间、路径、状态码和 `User-Agent`，不会显示在前端页面
6. 手动兜底更新与“保存当前月为历史数据”已迁移到 `附魔工作台`，本页面只保留静态数据浏览、截图导出和月份切换能力
7. 如需指定业务日期或保留运行痕迹排查问题，可直接执行 `python scripts/fetch_daily_data.py --business-date 2026-04-20 --keep-runtime`
   其中两张线索同期表按去年同月周期抓取；`全国按日` 会通过内部包装器清空 FineReport 默认 `营业状态` 筛选；NEV 来店本期/上期/同期通过 FineReport 后台 `chart.data` 导出链；ICE 来店本期/上期/同期通过 `来店批次分车系汇总表_按天T` 的 Tableau 交叉表缩略图入口
8. 如需让这台电脑每天自动更新，可执行 `powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1`
   默认会注册两条每天自动运行的 Windows 计划任务：`09:00` 的登录态交互任务会弹出流程窗口；如果首轮失败，窗口会提示“已进入二次更新”，`09:20` 的静默兜底任务再以 `SYSTEM` 服务账号执行；首轮已经成功时，`09:20` 只记录“二次更新无需执行”，不会重复抓取数据
9. 如果你在 `09:00` 左右已经登录 Windows，就会看到启动窗口；2 分钟内没有点击“开始更新”也没事，系统会自动继续执行，执行过程中窗口不会消失，而是显示完成进度条，最终在同一窗口展示更新结果后自动关闭
10. 如果 `09:00` 时没有登录 Windows，也不需要提前打开网页、VS Code 或手动点任何按钮；因当天没有成功记录，`09:20` 的静默任务会直接在后台完成更新，并继续把日志与结果写入 `.runtime/scheduled_update/`

## GitHub Pages 数据服务

1. 在一台能访问目标取数系统的机器上运行后端服务：
   `python scripts/serve_dashboard.py --host 0.0.0.0 --port 4173 --no-open-browser --cors-allow-origin https://<你的-pages-域名>`
2. 把 `docs/data/runtime-config.json` 里的 `serviceBaseUrl` 改成这个后端地址，例如 `https://digest-api.example.com`
3. 如无特殊需要，`dashboardDataUrl` 留空即可，前端会自动改为从 `${serviceBaseUrl}/api/dashboard-data` 读取最新 dashboard 数据
4. 把这份配置随站点一起发布到 GitHub Pages 后，页面可读取远端后端的当前数据和历史归档索引；写入型操作统一改到 `附魔工作台`
5. 如果你想保持仓库里的 `runtime-config.json` 为空，不改公开站点默认行为，也可以只在本机运行 `python scripts/serve_dashboard.py --port 4173`；需要手动兜底时，改用 `附魔工作台`

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

## Cloudflare Pages 自动部署

1. Cloudflare Pages 项目保持为 `django604-ai-digest`
2. 在 Cloudflare 创建仅具备 Pages 编辑权限的 API Token
3. 在 GitHub 仓库 `Settings > Secrets and variables > Actions` 新增 `CLOUDFLARE_ACCOUNT_ID` 与 `CLOUDFLARE_API_TOKEN`
4. `.github/workflows/deploy-cloudflare-pages.yml` 会在 `main` 的发布相关文件变化时重建并部署 `docs/`
5. 附魔工作台手动兜底与每天 9 点自动更新都通过 `dashboard_publish.py` 推送同一分支，因此会同时触发 GitHub Pages 与 Cloudflare Pages

## 日常更新方式

1. 本地用 Excel 更新源数据并保存
2. 直接运行 `powershell -ExecutionPolicy Bypass -File scripts/publish_dashboard.ps1`
3. 脚本会自动重建 `dashboard.json` 与 `dashboard.summary.json`，内部通过 `scripts/dashboard_publish.py` 统一完成提交与推送，并只提交以下发布相关文件：
   - `data/source/NEV+ICE_xsai.xlsm`
   - `data/source/NEV+ICE_ldai.xlsm`
   - `config/dashboard_targets.json`
   - `docs/data/dashboard.json`
   - `docs/data/dashboard.summary.json`
   - `docs/data/monthly/`
4. 推送成功后，两条 GitHub Actions workflow 会并行测试、重建并分别部署到 GitHub Pages 与 Cloudflare Pages
5. 两个公开入口都会更新到同一版数据

注意：两个静态站都不能直接读取你电脑本地文件。你在本地更新完数据后，必须把变更推送到 GitHub，网页才会同步更新。

公开页面首次打开和“回到当前月”会读取 live `docs/data/dashboard.json`；只有明确切换某个年月时才读取 `docs/data/monthly/YYYY-MM/dashboard.json`，避免当前月误读旧归档。

## 注意

- 当前方案读取的是 Excel 保存后的缓存结果。你更新完源数据后，必须先让 Excel 完成重算并保存，否则页面会拿到旧结果。
- 工作流读取当前实际使用的两本源文件：`NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsm`。
- 每日简报按“全车系有效线索 / NEV新增线索 / 2026款探陆线索 / 来店简报”四块展示；全车系月目标按报表月份读取 `config/dashboard_targets.json`（2026 年 7 月为 `668,262`），可在附魔工作台的“手动兜底更新”工具中填写；线索同比取两张 `全国按日*-同期`，来店环比取两张 `*上期来店`。
- 历史对照数据按完整自然月抓取，用于补齐趋势表与趋势图后半月；同比、环比摘要卡片和每日简报仍只取与业务日对齐的累计区间，不会用本期月中数据直接比较历史整月。
- `docs/data/dashboard.summary.json` 提供了报表日期、输入文件修改时间、dashboard 数量和本次是否真的发生内容变更，方便后续定时任务或自动巡检直接读取。
- 页面不再显示 `数据更新` 按钮；手动兜底入口已迁移到 `附魔工作台`，本页面不会再提示配置 `serviceBaseUrl` 后进行补跑。
- 趋势明细表现在会根据年度节假日配置直接标出 `节 / 周 / 班`：`节` 为法定节假日，`周` 为普通周末，`班` 为调休补班日；补班不会再被误判成周末或放假。
- `serve_dashboard.py` 现在会把页面访问与关键 API 访问静默记录到 `.runtime/access_logs/`；如果服务前面挂了反向代理或 CDN，可通过 `CF-Connecting-IP`、`X-Forwarded-For`、`X-Real-IP` 头识别真实来源 IP。
- `start_dashboard_server.bat` 默认会自动打开浏览器，并把额外参数原样转发给 `serve_dashboard.py`；例如可用 `start_dashboard_server.bat --no-auto-publish` 做只更新本地不自动推 GitHub 的临时调试。
- 即使远端更新服务临时不可达，页面现在也会自动回退到已发布的静态 `docs/data/dashboard.json`，避免整页直接加载失败。
## Auto Publish Notes

- To let scheduled updates publish to both Pages sites automatically, register the tasks with `powershell -ExecutionPolicy Bypass -File scripts/register_daily_update_task.ps1 -AutoPublish -PublishRemote origin -PublishBranch main`.
- The scheduled runner now supports `--auto-publish`, `--publish-remote`, `--publish-branch`, and `--publish-commit-message`.
- `附魔工作台` now owns write actions such as manual fallback and month archive publish; `scripts/serve_dashboard.py` only serves read APIs for the static dashboard.
- Auto publish reuses `scripts/dashboard_publish.py -SkipRebuild`, so one push triggers the independent GitHub Pages and Cloudflare Pages workflows.
- No Codex approval is needed when the scheduled task runs later on this machine. The task uses the local account context configured in Windows Task Scheduler.
- If the silent fallback task runs as `SYSTEM`, Git credentials must also be available to `SYSTEM`; otherwise data refresh may succeed but `git push` can still fail.

## 月度归档

- `scripts/build_dashboard.py` 现在会在刷新当前 `docs/data/dashboard.json`、`docs/data/dashboard.summary.json` 的同时，同步写入 `docs/data/monthly/YYYY-MM/dashboard.json` 与 `docs/data/monthly/YYYY-MM/dashboard.summary.json`。
- 所有可切换月份会汇总到 `docs/data/monthly/index.json`，页面侧边栏的“切换年月”按钮会读取这里的归档清单。
- 页面默认仍展示当前这份 dashboard 数据；切到历史月份后，读取的是对应月份的归档快照，不会被后续新月份的数据覆盖。
- `scripts/serve_dashboard.py` 提供 `/api/dashboard-archive`，并让 `/api/dashboard-data`、`/api/dashboard-summary` 支持 `?month=YYYY-MM` 查询参数。
- “保存当前月为历史数据”已迁移到 `附魔工作台` 首页的“月度归档发布”：点击后会固化当前报表月份，若源数据更新时间是每月 1 日，会开启源数据所属的新月份空白入口，并顺手提交、推送到 GitHub。
