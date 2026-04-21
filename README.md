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
- `scripts/fetch_daily_data.py`：复用日报取数平台登录逻辑，抓取 3 张日报表并回填工作簿
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
6. 如果需要直接走浏览器取数，可在本地服务页面左侧点击 `数据更新`；它会按当天 `N-1` 抓取 `全国按日`、`全国按日ICE`、`十五代轩逸按日`，更新 `NEV+ICE_xsai.xlsm` 后再重建页面数据
7. 如需指定业务日期或保留运行痕迹排查问题，可直接执行 `python scripts/fetch_daily_data.py --business-date 2026-04-20 --keep-runtime`

## GitHub Pages 点击更新

1. 在一台能访问目标取数系统的机器上运行后端服务：
   `python scripts/serve_dashboard.py --host 0.0.0.0 --port 4173 --no-open-browser --cors-allow-origin https://<你的-pages-域名>`
2. 把 `docs/data/runtime-config.json` 里的 `serviceBaseUrl` 改成这个后端地址，例如 `https://digest-api.example.com`
3. 如无特殊需要，`dashboardDataUrl` 留空即可，前端会自动改为从 `${serviceBaseUrl}/api/dashboard-data` 读取最新 dashboard 数据
4. 把这份配置随站点一起发布到 GitHub Pages 后，页面上的 `数据更新` 按钮就会真正调用远端后端执行更新，而不是只显示静态文案

注意：
- `runtime-config.json` 里只放后端访问地址，不要放账号密码之类的敏感信息
- 真正的登录账号、密码、Chrome 环境与 Excel 文件都应保留在后端服务所在机器

## 测试

- 运行 `python -m unittest discover -s tests -v`
- 当前测试覆盖构建输出的关键结构、源工作簿缺 sheet / 缺列 / 参数日期异常等输入校验，以及本地/远端更新 API、跨域预检与工作簿回填逻辑
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
