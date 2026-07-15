# 任务计划：AI_Digest 轻量化取数系统与网页更新入口

## 元信息
- 计划 ID：plan-2026-04-21-ai-digest-light-fetch
- 创建时间：2026-04-21T15:11:06+08:00
- 状态：待审批
- 预计复杂度：高
- 预计步骤数：7
- MCP 同步：否（当前会话无可用 MCP 任务同步工具）

---

## 任务目标

在 `AI_Digest` 内新增一套轻量化浏览器取数系统，复用“日报取数平台”的登录与浏览器运行思路，自动抓取 `N-1` 日对应的 3 张报表，将结果回填到 `NEV+ICE_xsai.xlsm` 的指定工作表，并在本地预览网页中增加一个小型“更新”按钮触发整套流程。

---

## 背景分析

### 现状
- `AI_Digest` 当前只具备 `Excel -> dashboard.json -> 静态网页` 的构建链路，核心入口为 [build_dashboard.py](/D:/WorkCode/AI_Digest/scripts/build_dashboard.py)。
- 本地预览服务 [serve_dashboard.py](/D:/WorkCode/AI_Digest/scripts/serve_dashboard.py) 目前只是静态文件服务器，没有任何本地 API 或任务执行能力。
- 前端页面 [index.html](/D:/WorkCode/AI_Digest/docs/index.html) 与 [app.js](/D:/WorkCode/AI_Digest/docs/assets/app.js) 已经有“截图工具”按钮区域，适合扩展一个小型“更新”按钮。
- `AI_Digest` 目标工作簿 [NEV+ICE_xsai.xlsm](/D:/WorkCode/AI_Digest/data/source/NEV+ICE_xsai.xlsm) 中确认存在目标工作表：
  - `全国按日NEV`
  - `全国按日ICE`
  - `十五代轩逸按日`
- “日报取数平台”已经存在成熟的浏览器登录与导出能力：
  - 共享浏览器/登录骨架：[script_runtime.py](/D:/WorkCode/日报取数平台/daily_sources/script_runtime.py)
  - NEV 线索入口：[日报线索NEV源/getdata.py](/D:/WorkCode/日报取数平台/日报线索NEV源/getdata.py)
  - ICE 线索入口：[日报线索ICE源/getdata.py](/D:/WorkCode/日报取数平台/日报线索ICE源/getdata.py)
- 3 张目标报表的来源已确认：
  - `全国按日-0420` 对应 NEV 模块 `national_daily`
  - `全国按日ICE-0420` 对应 ICE 模块 `ice_national_daily`
  - `十五代轩逸按日-0420` 对应 ICE 模块 `ice_sylphy15_daily`

### 问题 / 需求
- 当前 `AI_Digest` 的数据更新依赖人工维护 Excel，缺少“点一下就自动取数并回填”的入口。
- 用户希望新增“更新”按钮，但当前页面是纯静态页面，浏览器端不能直接启动本地 Python / Playwright 任务。
- 需求同时涉及两类系统能力：
  - 本地浏览器自动化取数
  - 本地 Excel 工作簿精准回填

### 影响范围
- 涉及文件：
  - [serve_dashboard.py](/D:/WorkCode/AI_Digest/scripts/serve_dashboard.py)
  - [build_dashboard.py](/D:/WorkCode/AI_Digest/scripts/build_dashboard.py)
  - [index.html](/D:/WorkCode/AI_Digest/docs/index.html)
  - [app.js](/D:/WorkCode/AI_Digest/docs/assets/app.js)
  - [styles.css](/D:/WorkCode/AI_Digest/docs/assets/styles.css)
  - [requirements.txt](/D:/WorkCode/AI_Digest/requirements.txt)
  - [NEV+ICE_xsai.xlsm](/D:/WorkCode/AI_Digest/data/source/NEV+ICE_xsai.xlsm)
- 可能新增文件：
  - `AI_Digest/scripts/fetch_daily_data.py`
  - `AI_Digest/scripts/fetch_runtime/*.py`
  - `AI_Digest/tests/test_fetch_daily_data.py`
  - `AI_Digest/tests/test_workbook_update.py`

---

## 实现方案

### 技术选型

选择“本地预览服务增强 + 轻量抓数脚本 + 工作簿回填器”的方案，不直接让前端调用浏览器自动化。

原因：
1. `AI_Digest` 当前网页是静态页，部署到 GitHub Pages 后无法直接执行本地脚本，必须通过本地服务桥接。
2. 直接跨项目 import 整个“日报取数平台”会把 `AI_Digest` 变成兄弟项目的附庸，耦合太重，维护时很容易炸锅。
3. 更稳妥的做法是“复用登录逻辑的设计与必要代码”，在 `AI_Digest` 内沉淀一个只服务 3 张表的轻量实现。

拟采用的边界：
- 本地模式：
  - `serve_dashboard.py` 扩展为“静态页 + 本地更新 API”。
  - 前端“更新”按钮只在本地服务环境可用。
- 部署模式：
  - GitHub Pages 继续保持只读展示。
  - “更新”按钮在远端部署环境默认隐藏或禁用，并显示说明文案。

### 关键设计决策

1. **不直接复用整个平台入口**
- 不引入 `run_daily_sources.py` 全量调度。
- 只抽取必要能力：Chrome 启动、登录复用、目标报表导出。

2. **分模块导出，统一回填**
- NEV 模块抓 `national_daily`
- ICE 模块抓 `ice_national_daily`
- ICE 模块抓 `ice_sylphy15_daily`
- 抓取结束后统一写回 `NEV+ICE_xsai.xlsm`

3. **按钮不直接触发 Python，可通过本地 HTTP API 触发**
- 前端点击“更新”
- `app.js` 调用本地 `POST /api/update-data`
- 服务端串行执行：
  - 浏览器取数
  - Excel 回填
  - 重建 `dashboard.json`
  - 返回状态给前端

4. **工作簿更新采用 `keep_vba=True` 的原位写回**
- 必须保留 `.xlsm` 宏结构
- 不能用 `data_only=True` 回写
- 只替换目标 sheet 的数据区，不动无关工作表

### 步骤分解

#### 步骤 1：确定本地更新链路的服务边界
- **状态**：待执行
- **目标**：明确“更新”按钮只在本地服务环境可执行，远端静态部署保持只读。
- **涉及文件**：
  - [serve_dashboard.py](/D:/WorkCode/AI_Digest/scripts/serve_dashboard.py) — 修改
  - [index.html](/D:/WorkCode/AI_Digest/docs/index.html) — 修改
  - [app.js](/D:/WorkCode/AI_Digest/docs/assets/app.js) — 修改
- **具体操作**：
  1. 为本地服务增加最小 API 路由设计，例如 `POST /api/update-data` 与 `GET /api/update-status`。
  2. 约定 GitHub Pages 环境下按钮隐藏或禁用的判断规则。
  3. 设计统一的前端状态提示文案：空闲、执行中、成功、失败。
- **验证方法**：
  - 本地服务启动后可识别 API 路由；
  - 静态部署环境不暴露可执行更新入口。

#### 步骤 2：抽取日报取数平台的最小可复用登录能力
- **状态**：待执行
- **目标**：在 `AI_Digest` 内形成轻量运行时，不直接依赖兄弟项目整套结构。
- **涉及文件**：
  - [日报取数平台/daily_sources/script_runtime.py](/D:/WorkCode/日报取数平台/daily_sources/script_runtime.py) — 参考
  - [日报线索NEV源/getdata.py](/D:/WorkCode/日报取数平台/日报线索NEV源/getdata.py) — 参考
  - [日报线索ICE源/getdata.py](/D:/WorkCode/日报取数平台/日报线索ICE源/getdata.py) — 参考
  - `AI_Digest/scripts/fetch_runtime/*.py` — 新建
- **具体操作**：
  1. 提炼必需能力：UTF-8 输出、Chrome 路径检测、Playwright 浏览器上下文创建、登录页识别、登录执行、关闭流程。
  2. 去掉平台级 GUI、批量调度、历史产物目录规则等重逻辑。
  3. 将“日报取数平台”的实现视为参考源，而不是运行时强依赖。
- **验证方法**：
  - 轻量运行时可以独立 import；
  - 不需要 `run_daily_sources.py` 也能完成登录和单报表导出准备。

#### 步骤 3：实现 3 张目标报表的轻量抓取脚本
- **状态**：待执行
- **目标**：以 `N-1` 日为业务日期抓取 3 张目标表。
- **涉及文件**：
  - `AI_Digest/scripts/fetch_daily_data.py` — 新建
  - [日报线索NEV源/report_fetcher/report_configs.py](/D:/WorkCode/日报取数平台/日报线索NEV源/report_fetcher/report_configs.py) — 参考
  - [日报线索ICE源/report_fetcher/report_configs.py](/D:/WorkCode/日报取数平台/日报线索ICE源/report_fetcher/report_configs.py) — 参考
- **具体操作**：
  1. 固定映射 3 张报表：
     - `national_daily -> 全国按日NEV`
     - `ice_national_daily -> 全国按日ICE`
     - `ice_sylphy15_daily -> 十五代轩逸按日`
  2. 默认业务日期使用 `N-1`，同时保留可选 `--business-date` 覆盖能力。
  3. 导出结果先落到临时目录，避免直接写工作簿时中途失败污染源文件。
  4. 为每张报表输出 trace 与结构校验结果。
- **验证方法**：
  - 指定业务日期后能生成 3 份导出文件；
  - 导出文件名与报表映射一致；
  - 任一报表失败时可以明确报错并中断回填。

#### 步骤 4：实现工作簿回填器
- **状态**：待执行
- **目标**：将 3 份导出结果精准写回 `NEV+ICE_xsai.xlsm` 的指定工作表。
- **涉及文件**：
  - `AI_Digest/scripts/fetch_daily_data.py` — 修改
  - [NEV+ICE_xsai.xlsm](/D:/WorkCode/AI_Digest/data/source/NEV+ICE_xsai.xlsm) — 运行产物
  - [build_dashboard.py](/D:/WorkCode/AI_Digest/scripts/build_dashboard.py) — 参考结构校验
- **具体操作**：
  1. 读取目标工作簿时使用 `keep_vba=True`。
  2. 基于工作表现有头部结构，定义“表头保留 + 数据区清空 + 新数据写入”的规则。
  3. 对 3 个 sheet 分别做列头匹配与行写入。
  4. 写回后重新打开并运行结构校验，确保 `build_dashboard.py` 可继续消费。
- **验证方法**：
  - 回填后工作簿仍能被 `openpyxl.load_workbook(..., keep_vba=True)` 正常打开；
  - [build_dashboard.py](/D:/WorkCode/AI_Digest/scripts/build_dashboard.py) 的 sheet/header 校验通过。

#### 步骤 5：将回填与 dashboard 重建串成单一任务
- **状态**：待执行
- **目标**：一次调用完成“抓数 -> 回填 -> 重建 JSON”。
- **涉及文件**：
  - `AI_Digest/scripts/fetch_daily_data.py` — 修改
  - [build_dashboard.py](/D:/WorkCode/AI_Digest/scripts/build_dashboard.py) — 复用
  - [rebuild_dashboard.ps1](/D:/WorkCode/AI_Digest/scripts/rebuild_dashboard.ps1) — 可选调整
- **具体操作**：
  1. 在抓数脚本中调用现有构建入口，而不是重复实现 dashboard 重建逻辑。
  2. 统一输出任务摘要：业务日期、3 张表状态、工作簿更新时间、JSON 重建状态。
  3. 保证失败时不覆盖旧的 `dashboard.json`。
- **验证方法**：
  - 单条命令即可完成全流程；
  - 成功后 `docs/data/dashboard.json` 与 `dashboard.summary.json` 更新；
  - 失败时旧页面仍可用。

#### 步骤 6：接入网页“更新”按钮
- **状态**：待执行
- **目标**：在网页侧边栏增加一个小型“更新”按钮，并展示任务状态。
- **涉及文件**：
  - [index.html](/D:/WorkCode/AI_Digest/docs/index.html) — 修改
  - [app.js](/D:/WorkCode/AI_Digest/docs/assets/app.js) — 修改
  - [styles.css](/D:/WorkCode/AI_Digest/docs/assets/styles.css) — 修改
- **具体操作**：
  1. 在现有截图工具区域附近增加小型按钮，文案固定为“更新”。
  2. 按钮点击后请求本地 API，不直接在浏览器里执行抓数。
  3. 增加执行中的禁用态、完成态、失败态和错误提示。
  4. 如服务端支持轮询状态，则前端展示进度文本。
- **验证方法**：
  - 页面加载完成后按钮可见；
  - 点击后可收到任务反馈；
  - 执行中不可重复点击。

#### 步骤 7：补测试、说明文档与变更记录
- **状态**：待执行
- **目标**：让这套轻量取数系统可维护、可交接、可回归。
- **涉及文件**：
  - `AI_Digest/tests/test_fetch_daily_data.py` — 新建
  - `AI_Digest/tests/test_workbook_update.py` — 新建
  - [README.md](/D:/WorkCode/AI_Digest/README.md) — 修改
  - [SCRIPTS.md](/D:/WorkCode/AI_Digest/SCRIPTS.md) — 修改
  - [DEV_CHANGELOG.md](/D:/WorkCode/AI_Digest/DEV_CHANGELOG.md) — 修改
- **具体操作**：
  1. 为报表映射、业务日期计算、sheet 回填规则增加单元测试。
  2. 为本地更新入口补使用说明和限制说明。
  3. 在变更日志中记录新增脚本、更新按钮与验证结果。
- **验证方法**：
  - 单元测试可跑；
  - 文档能说明本地模式与远端模式差异；
  - 变更记录完整。

---

## 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| GitHub Pages 静态页无法直接执行本地抓数 | 高 | 高 | 明确限定“更新”按钮只在本地服务模式可用，远端隐藏或禁用 |
| 直接复用兄弟项目整套代码导致耦合过重 | 高 | 高 | 只抽取必要登录/浏览器能力，避免跨项目硬依赖 |
| 导出报表结构与目标 sheet 结构不一致 | 中 | 高 | 先做表头匹配校验，校验失败则停止回填 |
| `.xlsm` 回写破坏宏或格式 | 中 | 高 | 使用 `keep_vba=True`，仅改数据区，先写临时副本再原位替换 |
| 浏览器登录态或站点参数变更导致抓数失效 | 中 | 高 | 保留 trace、错误日志和可选 headed 调试模式 |
| 长任务由按钮触发，前端体验不稳定 | 中 | 中 | 使用服务端任务状态返回和前端禁用态/状态文本 |
| Playwright / requests 新依赖引入后影响现有环境 | 中 | 中 | 将抓数依赖最小化，必要时拆成独立 requirements 段落或附加安装说明 |

---

## 验收标准

### 完成条件
- [ ] 本地预览页出现一个小型“更新”按钮，点击后能触发本地更新任务
- [ ] 系统默认按 `N-1` 业务日期抓取 3 张目标报表
- [ ] `全国按日NEV`、`全国按日ICE`、`十五代轩逸按日` 3 个工作表被正确回填
- [ ] 回填后 `build_dashboard.py` 能成功重建 `dashboard.json`
- [ ] GitHub Pages 远端静态环境不会错误暴露不可执行的本地更新能力

### 验证方法
- 手动验证：
  1. 启动本地 `serve_dashboard.py`
  2. 打开页面点击“更新”
  3. 观察前端状态提示
  4. 检查 `NEV+ICE_xsai.xlsm` 的 3 个目标 sheet 已更新
  5. 检查 `docs/data/dashboard.json` 与 `docs/data/dashboard.summary.json` 已更新
- 自动化验证：
  - 单元测试校验业务日期、报表映射、sheet 写回规则
  - 结构校验复用 [build_dashboard.py](/D:/WorkCode/AI_Digest/scripts/build_dashboard.py) 的现有工作簿验证逻辑

---

## 执行记录

| 时间 | 操作 | 结果 |
|------|------|------|
| 2026-04-21T15:11:06+08:00 | 创建计划文档 | 完成 |

---

## 用户确认

- [ ] 我已审阅并批准此计划
/do-plan 
**批准后执行**：`/do-plan`
