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
- `scripts/build_dashboard.py`：从 Excel 抽取页面数据
- `scripts/rebuild_dashboard.ps1`：Windows 下本地一键重建 `dashboard.json`
- `scripts/publish_dashboard.ps1`：Windows 下本地一键重建并推送到 GitHub
- `docs/`：静态站点
- `.github/workflows/deploy-pages.yml`：自动发布工作流
- `reports/excel_analysis.md`：Excel 结构分析

## 本地使用

1. 更新 `data/source/NEV+ICE_xsai.xlsm` 和 `data/source/NEV+ICE_ldai.xlsx`
2. 运行 `powershell -ExecutionPolicy Bypass -File scripts/rebuild_dashboard.ps1`
3. 运行 `python scripts/serve_dashboard.py --port 4173`，需要自动打开浏览器时可以附加 `--open-browser`
4. 打开 `http://127.0.0.1:4173`，即使误写成 `/docs` 或 `/AI_Digest` 等路径也会被回退到 `index.html`

## 首次部署到 GitHub Pages

1. 把当前项目推到一个 GitHub 仓库的 `main` 分支
2. 打开仓库 `Settings > Pages`
3. 在 `Build and deployment` 中选择 `GitHub Actions`
4. 确认仓库的 Actions 权限允许工作流运行

## 日常更新方式

1. 本地用 Excel 更新源数据并保存
2. 直接运行 `powershell -ExecutionPolicy Bypass -File scripts/publish_dashboard.ps1`
3. 脚本会自动重建 `dashboard.json`，并只提交以下发布相关文件：
   - `data/source/NEV+ICE_xsai.xlsm`
   - `data/source/NEV+ICE_ldai.xlsx`
   - `docs/data/dashboard.json`
4. `GitHub Actions` 自动重新生成并发布页面
5. 别人打开 GitHub Pages 链接时，就能看到最新数据

注意：`GitHub Pages` 不能直接读取你电脑本地文件。你在本地更新完数据后，必须把变更推送到 GitHub，网页才会同步更新。

## 注意

- 当前方案读取的是 Excel 保存后的缓存结果。你更新完源数据后，必须先让 Excel 完成重算并保存，否则页面会拿到旧结果。
- 工作流已经改成读取当前实际使用的两本源文件：`NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx`。
