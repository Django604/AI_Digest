# jsDelivr 对外访问镜像设计

## 背景

`https://django604.github.io/AI_Digest/` 已成功部署，但当前网络访问 GitHub Pages 时出现 `ERR_CONNECTION_RESET`。DNS 返回的 4 个 GitHub Pages IPv4 节点中，只有 `185.199.110.153` 可以完成 TLS 并返回 `HTTP 200`，其余 3 个节点在 TLS 建立前被重置。该问题发生在 HTTP 请求到达站点之前，无法通过页面代码修复。

线上数据已通过可用节点核验：报表日期为 `2026-07-14`，新探陆 section 存在，NEV 共 6 个 section。

## 目标

在不依赖自有域名、新云账号或额外凭据的前提下，为公司内外用户提供可稳定访问的公开入口，并保留 GitHub Pages 作为备用地址。

对外主入口：

`https://cdn.jsdelivr.net/gh/Django604/AI_Digest@main/docs/index.svg`

备用入口：

`https://django604.github.io/AI_Digest/`

## 架构

jsDelivr 直接从公开 GitHub 仓库的 `main` 分支分发 `docs/` 静态文件。真实浏览器验证发现 jsDelivr 会把 `.html` 强制返回为 `text/plain`，因此新增 `docs/index.svg` 作为 CDN 入口：它通过 SVG `foreignObject` 承载现有页面 DOM，并用一层 XML/HTML DOM 兼容逻辑继续加载同目录下的 `assets/`、`data/` 与 `data/monthly/`。GitHub Pages 继续使用原 `index.html`。

GitHub Pages workflow 继续执行现有测试、dashboard 重建和 Pages 部署。在 build job 完成测试与 dashboard 构建后，新增 jsDelivr 缓存清理步骤，使仓库中已提交的发布文件尽快从 CDN 刷新。

## 缓存清理脚本

新增 `scripts/purge_jsdelivr_cache.py`：

- 递归枚举 `docs/` 下需要公开分发的文件。
- 为每个文件构造 `https://purge.jsdelivr.net/gh/Django604/AI_Digest@main/<仓库相对路径>`。
- 使用 Python 标准库发送请求，不新增依赖。
- 对临时网络错误执行有限次数重试。
- 输出成功、失败和总文件数摘要。
- 任何关键入口文件清理失败时返回非零退出码。

关键文件包括：

- `docs/index.html`
- `docs/index.svg`
- `docs/assets/app.js`
- `docs/assets/styles.css`
- `docs/data/dashboard.json`
- `docs/data/dashboard.summary.json`
- `docs/data/monthly/index.json`
- 所有月度 dashboard 与 summary JSON

图片、字体或其他 `docs/` 文件也一并清理，避免后续新增静态资源时忘记更新脚本白名单。

## Workflow 时序

build job 的执行顺序：

1. Checkout
2. Setup Python
3. Install dependencies
4. Run tests
5. Build dashboard data
6. Purge jsDelivr cache
7. Configure Pages
8. Upload Pages artifact

缓存清理只在测试和构建成功后执行。若测试失败，继续保留 CDN 上一版可用缓存，不把失败构建当成发布。

GitHub Pages deploy job 保持不变，作为备用入口继续发布。

## 失败处理

- jsDelivr 清理失败会让 build job 失败，防止对外宣称已更新但 CDN 仍长期展示旧数据。
- 清理请求采用重试，避免一次瞬时网络抖动直接导致失败。
- 脚本日志必须列出失败 URL，便于手动重新执行。
- 不在脚本或 workflow 中写入账号、Token 或其他秘密信息；jsDelivr purge API 无需凭据。

## 文档与使用方式

README 增加“公开访问入口”：

- 推荐同事使用 jsDelivr `index.svg` 主入口，并说明不能直接使用会展示源码的 `index.html`。
- GitHub Pages 作为备用。
- 说明 jsDelivr 链接较长，但无需安装客户端、修改 hosts 或使用公司内网。

`SCRIPTS.md` 记录缓存清理脚本的用途、参数和手动执行方式。

## 验证

1. 单元测试覆盖文件枚举、URL 编码、重试、关键文件失败和成功摘要。
2. 运行脚本语法检查、专项测试和全量测试。
3. 在干净 Git worktree 中运行 workflow 同款测试与构建。
4. 推送后验证 jsDelivr SVG 入口的 `Content-Type` 为 `image/svg+xml`，JS、CSS、当前 dashboard JSON 和月度索引均返回 `HTTP 200`。
5. 使用真实浏览器打开 jsDelivr SVG 主入口，确认页面渲染、当前数据、新探陆 section 和月份切换正常；同时确认 `.html` 入口只作为 CDN MIME 诊断对象，不对外分发。

## 范围外事项

- 不修改本机或同事电脑的 hosts 文件。
- 不购买或配置自有域名。
- 不新增 Cloudflare、阿里云或腾讯云账号。
- 不移除 GitHub Pages。
- 不改变 dashboard 业务数据和页面功能。
