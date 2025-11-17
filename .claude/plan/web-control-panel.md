# Web 控制面板实施计划

## 任务背景

**用户需求**：
- 现有的照片下载和上传功能已实现，但必须通过命令行模式运行
- 需要提前设置好配置文件，使用不便
- 希望利用免费云服务（GitHub Actions、Cloudflare等）创建前端页面
- 用户可在前端输入配置（access token、存储路径等）
- 支持开始/停止脚本执行

**核心问题**：
- 现有代码持续运行（while True 循环）会浪费 GitHub Actions 时间
- 应改为间隔固定时间运行一次，每次检查是否有新照片

## 解决方案设计

### 架构选择

**方案 A**（已采用）：GitHub Actions + 静态前端

- **前端**：HTML/CSS/JavaScript (Vanilla) + Cloudflare Pages
- **后端**：GitHub Actions (Python 脚本)
- **通信**：GitHub REST API
- **配置存储**：localStorage (前端) + GitHub Secrets (Dropbox Token)
- **历史文件存储**：GitHub Repo（通过 Git 提交）

### 运行模式对比

| 模式 | 文件 | 运行方式 | 使用场景 |
|------|------|----------|---------|
| 本地持续运行 | `photo_downloader.py` | `while True` 循环 | 本地开发/测试 |
| GitHub Actions 单次运行 | `github_actions_runner.py` | 执行一次后退出 | 云端定时任务 |

### 关键技术决策

1. **代码复用策略**：
   - 保持 `photo_downloader.py` 不变（向后兼容）
   - 创建新的 `github_actions_runner.py` 复用核心组件
   - 避免破坏现有功能

2. **首次运行标志**：
   - 前端提供 checkbox 让用户选择是否清除历史
   - 存储在 `runtime-config.json` 的 `clearHistory` 字段
   - 仅生效一次，执行后自动重置为 `false`

3. **检查间隔控制**：
   - GitHub Actions cron 固定 5 分钟触发
   - 脚本内部检查用户设定的间隔（如 10、30、60 分钟）
   - 未达到间隔时快速退出（< 5 秒）

4. **配置文件格式**：

```json
{
  "enabled": true/false,           // 是否启用监控
  "interval": 10,                  // 用户设定间隔（分钟）
  "clearHistory": true/false,      // 是否清除历史（首次运行）
  "lastRunTime": "ISO8601",        // 上次运行时间
  "lastRunSuccess": true/false,    // 上次运行结果
  "taskConfig": {
    "targetUrl": "...",            // 目标 URL
    "dropboxPath": "/photos"       // Dropbox 路径
  }
}
```

## 实施细节

### 文件清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| **新增** | `.github/workflows/photo-download.yml` | GitHub Actions 工作流 |
| **新增** | `web/index.html` | 前端主页面 |
| **新增** | `web/app.js` | 前端逻辑（约 450 行）|
| **新增** | `web/style.css` | 样式（约 350 行）|
| **新增** | `github_actions_runner.py` | Actions 专用运行器（约 350 行）|
| **新增** | `runtime-config.json.example` | 配置示例 |
| **更新** | `README.md` | 新增 Web 面板使用指南 |
| **不变** | `photo_downloader.py` | 保持本地运行能力 |
| **不变** | `config.py` | 保持现有配置 |

### 核心功能实现

#### 1. `github_actions_runner.py`

**核心类**：`RuntimeConfig`
- `_load()`: 读取配置文件
- `should_run()`: 检查是否应该执行（enabled + 时间间隔）
- `should_clear_history()`: 检查是否需要清除历史
- `update_after_run()`: 更新运行时间戳和状态

**核心函数**：`commit_changes()`
- 配置 Git 用户信息
- 添加并提交文件
- 推送到远程（带 rebase 和重试）

**主流程**：`run_single_cycle()`
1. 读取 runtime-config.json
2. 检查是否应该运行（enabled + interval）
3. 处理首次运行（清除历史）
4. 初始化组件（History, Downloader, Extractor）
5. 执行下载任务
6. 更新配置并提交到 Git

#### 2. GitHub Actions 工作流

**触发条件**：
- `schedule: '*/5 * * * *'` - 每 5 分钟
- `workflow_dispatch` - 手动触发

**关键步骤**：
- 安装 uv + Python 依赖
- 安装 Playwright 浏览器
- 运行 `github_actions_runner.py`
- 提交更改到仓库（always 执行）

#### 3. 前端控制面板

**核心功能**：

**配置管理**：
- `saveConfig()`: 保存到 localStorage
- `loadConfig()`: 从 localStorage 读取

**监控控制**：
- `startMonitoring()`: 创建/更新 runtime-config.json，设置 enabled=true
- `stopMonitoring()`: 更新 runtime-config.json，设置 enabled=false
- `manualRun()`: 触发 workflow_dispatch

**状态监控**：
- `fetchStatus()`: 读取 runtime-config.json 显示状态
- `fetchLogs()`: 获取最近 5 次 workflow runs

**GitHub API 封装**：
- `githubAPI()`: 统一处理 API 请求、认证、错误

## 用户使用流程

### 首次部署

1. Fork 仓库
2. 部署前端到 Cloudflare Pages（`web` 目录）
3. 获取 GitHub Personal Access Token（repo + workflow）
4. 获取 Dropbox Access Token

### 日常使用

1. 打开 Web 面板
2. 填写配置并保存
3. 首次启动：勾选 "清除历史记录"
4. 点击 "开始监控"
5. 手动配置 GitHub Secret: `DROPBOX_ACCESS_TOKEN`
6. 查看运行日志和状态

### 停止监控

1. 点击 "停止监控"
2. GitHub Actions 仍会每 5 分钟触发，但会快速退出（< 5 秒）

## 成本分析

**GitHub Actions 免费额度**：2000 分钟/月

**消耗估算**（假设每次运行 2 分钟）：

| 用户设定间隔 | 每天运行次数 | 每天消耗 | 每月消耗 | 是否免费 |
|-------------|-------------|---------|---------|---------|
| 10 分钟 | 144 | 288 分钟 | 8640 分钟 | ❌ 超额 |
| 30 分钟 | 48 | 96 分钟 | 2880 分钟 | ❌ 超额 |
| 60 分钟 | 24 | 48 分钟 | 1440 分钟 | ✅ 免费 |

**推荐配置**：间隔 60 分钟，每月消耗约 1440 分钟，充分利用免费额度。

## 技术栈

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| 前端托管 | Cloudflare Pages | 免费、快速、全球 CDN |
| 前端框架 | Vanilla JS | 简单、无构建步骤、加载快 |
| 后端运行 | GitHub Actions | 免费、集成 Git、易部署 |
| API 通信 | GitHub REST API | 官方 API、稳定可靠 |
| 配置存储 | localStorage + GitHub Repo | 前端持久化 + 后端状态同步 |
| 历史文件存储 | Git 提交 | 简单、可追溯、无需额外服务 |

## 安全考虑

1. **Token 存储**：
   - GitHub Token: localStorage（用户本地）
   - Dropbox Token: GitHub Secrets（加密存储）

2. **权限最小化**：
   - GitHub Token 仅需 `repo` + `workflow` 权限
   - Dropbox Token 仅需 `files.content.write` 权限

3. **防止滥用**：
   - 间隔最小 10 分钟
   - 单次运行超时 10 分钟

## 已知限制

1. **Dropbox Secret 配置**：
   - 浏览器无法加密 Secret（需 libsodium.js）
   - 用户需手动在 GitHub Settings 配置

2. **GitHub Actions cron 延迟**：
   - 实际触发可能延迟 ±5 分钟
   - 高峰时段延迟更长

3. **Git 提交冲突**：
   - 如果用户手动修改文件可能冲突
   - 已实现 `git pull --rebase` 自动解决

4. **日志实时性**：
   - 轮询模式，约 5-10 秒延迟
   - 非真正的实时推送

## 扩展可能性

### 未来可优化方向

1. **方案 2：Cloudflare Workers 中间层**
   - 实现真正的实时日志（WebSocket）
   - 自动加密 Dropbox Secret
   - 更好的用户体验

2. **多任务支持**：
   - 监控多个直播页面
   - 独立的配置和历史

3. **通知功能**：
   - 邮件/Webhook 通知下载结果
   - 错误告警

4. **统计分析**：
   - 下载历史图表
   - 存储空间统计

## 实施结果

### 已完成

✅ GitHub Actions 工作流配置
✅ 单次运行模式实现（`github_actions_runner.py`）
✅ Web 控制面板（HTML + JS + CSS）
✅ 配置管理和监控控制
✅ 状态监控和日志显示
✅ README 文档更新
✅ 代码复用，保持向后兼容

### 测试要点

- [ ] 本地运行 `photo_downloader.py` 仍正常工作
- [ ] `github_actions_runner.py` 可独立运行
- [ ] GitHub Actions 手动触发成功
- [ ] Web 面板配置保存/加载
- [ ] 开始/停止监控功能
- [ ] 状态和日志显示
- [ ] Git 提交无冲突

## 总结

本方案成功实现了基于 Web 控制面板的云端自动化下载系统，核心优势：

1. **完全免费**：利用 GitHub Actions + Cloudflare Pages 免费服务
2. **用户友好**：可视化配置，无需命令行操作
3. **节省资源**：单次运行模式，合理利用 Actions 额度
4. **向后兼容**：保留本地运行模式，满足不同使用场景
5. **可扩展**：架构清晰，易于未来优化

**建议用户使用间隔 60 分钟**，既能及时获取新照片，又能充分利用免费额度。
