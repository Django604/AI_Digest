# 脚本使用手册

最后更新：2026-04-07

## scripts/build_dashboard.py

- 路径：`./scripts/build_dashboard.py`
- 作用：读取 `NEV+ICE_xsai.xlsm` 与 `NEV+ICE_ldai.xlsx`，抽取线索与来店页面数据，输出静态站点使用的 `JSON`
- 使用方法：
  - `python scripts/build_dashboard.py --workbook data/source/NEV+ICE_xsai.xlsm --arrival-workbook data/source/NEV+ICE_ldai.xlsx --out docs/data/dashboard.json`
- 运行前提：
  - 本机可用 `Python`
  - 已安装 `openpyxl`
  - 两本源工作簿已经在 Excel 中重算并保存
- 输出结果：
  - `docs/data/dashboard.json`
- 备注：
  - 脚本优先读取面板页的缓存展示结果，而不是在 `Python` 里复刻全部 Excel 公式；这样和原模板展示更一致，但前提是源文件已保存最新计算结果

## scripts/rebuild_dashboard.ps1

- 路径：`./scripts/rebuild_dashboard.ps1`
- 作用：按项目当前默认路径一键重建 `docs/data/dashboard.json`
- 使用方法：
  - `powershell -ExecutionPolicy Bypass -File scripts/rebuild_dashboard.ps1`
- 运行前提：
  - 本机可用 `Python`
  - 已安装 `openpyxl`
  - `data/source/NEV+ICE_xsai.xlsm` 与 `data/source/NEV+ICE_ldai.xlsx` 已更新并保存
- 输出结果：
  - 更新 `docs/data/dashboard.json`
- 备注：
  - 这个脚本只负责本地重建数据；要让 GitHub Pages 同步更新，仍然需要把变更提交并推送到 GitHub

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
  - 已安装 `openpyxl`
  - `data/source/NEV+ICE_xsai.xlsm` 与 `data/source/NEV+ICE_ldai.xlsx` 已更新并保存
- 输出结果：
  - 更新 `docs/data/dashboard.json`
  - 自动提交并推送发布相关文件
- 备注：
  - 默认只会提交这 3 个文件：两本 Excel 源文件和 `docs/data/dashboard.json`
  - 如果工作区里已经暂存了别的文件，脚本会主动拦住，避免把无关改动一起推上去

## scripts/serve_dashboard.py

- 路径：`./scripts/serve_dashboard.py`
- 作用：启动一个指向 `docs/` 目录的本地 `ThreadingHTTPServer`，并在访问 `/docs`、`/AI_Digest` 等“干净 URL”时自动回退到 `index.html`，避免默认 `http.server` 的 404
- 使用方法：
  - `python scripts/serve_dashboard.py --port 4173 [--open-browser]`
- 运行前提：
  - 本机可用 `Python`（仅使用标准库）
- 输出结果：
  - 控制台展示访问地址，例如 `http://127.0.0.1:4173`
- 备注：
  - 端口被占用或目录缺失时会在控制台给出错误提示；按 `Ctrl+C` 即可退出
