# 📸 照片自动下载工具

自动下载 PhotoPlus 直播网站的照片到本地的智能工具。

## ✨ 功能特性

- ⏰ **定时检查**: 每2分钟自动检查新照片
- 🎯 **智能滚动**: 自动滚动加载所有照片
- 🔄 **去重机制**: 智能去重，避免重复下载
- ☁️ **云盘存储**: 支持 Dropbox 云盘自动上传（可选）
- 💾 **灵活存储**: 支持仅云盘、仅本地或双重备份模式
- 📦 **现代化管理**: 使用 uv 进行快速依赖管理
- 🚀 **稳定可靠**: 基于 Playwright 的浏览器自动化
- 📝 **详细日志**: 实时控制台日志输出
- 🛡️ **错误处理**: 完善的重试和容错机制

## 🔧 前置要求

- Python 3.8+
- uv 包管理器

## 📦 安装

### 1. 安装 uv（如果未安装）

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 安装项目依赖

```bash
# 进入项目目录
cd photo-download

# uv会自动创建虚拟环境并安装依赖
uv sync

# 安装Playwright浏览器（首次运行需要）
uv run playwright install chromium
```

## 🚀 使用方法

本工具提供两种运行模式：

1. **🌐 Web 控制面板模式**（推荐）- 通过网页控制 GitHub Actions 定时运行
2. **💻 本地持续运行模式** - 在本地电脑持续运行脚本

---

## 🌐 Web 控制面板模式（推荐）

### 特性

- ✅ 完全免费（使用 GitHub Actions + Cloudflare Pages）
- ✅ 无需本地运行，云端自动执行
- ✅ 可视化配置界面
- ✅ 实时查看运行状态和日志
- ✅ 支持启动/停止监控
- ✅ 灵活设置检查间隔

### 快速开始

#### 1. 准备 GitHub 仓库

1. **Fork 本仓库**到您的 GitHub 账户
2. **创建 github_action 分支**（GitHub Actions 将在此分支运行）：
   ```bash
   git checkout -b github_action
   git push -u origin github_action
   ```
3. **设置默认分支**（可选）：
   - 访问仓库 Settings → Branches
   - 将 Default branch 设置为 `github_action`

#### 2. 部署前端控制面板

**方案 A: Cloudflare Pages（推荐）**

1. 访问 [Cloudflare Pages](https://pages.cloudflare.com/)
2. 点击 "Create a project" → 连接您的 GitHub 仓库
3. 构建配置：
   - 构建命令：（留空）
   - 构建输出目录：`web`
   - **生产分支**：`github_action`（重要！）
4. 点击 "Save and Deploy"
5. 部署完成后获得访问 URL：`https://your-project.pages.dev`

**方案 B: GitHub Pages**

1. 进入仓库 Settings → Pages
2. Source: Deploy from a branch
3. Branch: `github_action` / Folder: `/web`
4. Save 后获得 URL：`https://username.github.io/photo-download`

#### 3. 获取 GitHub Personal Access Token

1. 访问 [GitHub Token 设置页面](https://github.com/settings/tokens/new)
2. Note: `PhotoPlus Downloader`
3. Expiration: No expiration（推荐）
4. 勾选权限：
   - ✅ `repo` (完整仓库访问)
   - ✅ `workflow` (触发 GitHub Actions)
5. 点击 "Generate token" 并**复制保存 Token**

#### 4. 配置 GitHub Secrets（Dropbox 认证）

⚠️ **重要说明**：Dropbox 现在推荐使用 **Refresh Token** 而不是 Access Token，以支持长期运行的自动化任务。

**方式 1：使用 Refresh Token（推荐，永久有效）**

1. **获取 Dropbox Refresh Token**：

   a. 访问 [Dropbox App Console](https://www.dropbox.com/developers/apps)

   b. 如果没有应用，创建新应用：
      - 点击 "Create app"
      - 选择 **Scoped access**
      - 选择 **Full Dropbox**
      - 输入应用名称（如：`PhotoPlus Downloader`）

   c. 进入应用设置页面：
      - 切换到 **Permissions** 标签页
      - 勾选 `files.content.write` 和 `files.content.read`
      - 点击 "Submit"

   d. 切换到 **Settings** 标签页：
      - 找到 **OAuth 2** 部分
      - 复制 **App key**（保存备用）
      - 复制 **App secret**（保存备用）
      - 在 **Generated access token** 区域，点击 "Generate" 按钮
      - 选择 **"Generate refresh token"**（而不是 access token）
      - 复制生成的 **Refresh Token**

2. **配置到 GitHub Secrets**：

   访问 GitHub 仓库的 **Settings → Secrets and variables → Actions**，添加以下 3 个 Secrets：

   | Secret 名称 | 值 | 说明 |
   |------------|---|------|
   | `DROPBOX_REFRESH_TOKEN` | `your_refresh_token` | 步骤 1d 生成的 Refresh Token |
   | `DROPBOX_APP_KEY` | `your_app_key` | 步骤 1d 的 App key |
   | `DROPBOX_APP_SECRET` | `your_app_secret` | 步骤 1d 的 App secret |

**方式 2：使用 Access Token（旧方式，4小时有效期，不推荐）**

仅作为临时测试使用，不适合长期运行：

1. 访问 [Dropbox App Console](https://www.dropbox.com/developers/apps)
2. 进入应用的 Settings 标签页
3. 在 **Generated access token** 区域，点击 "Generate"
4. 复制生成的 Access Token
5. 在 GitHub Secrets 中添加：
   - Name: `DROPBOX_ACCESS_TOKEN`
   - Value: 粘贴 Access Token

⚠️ **注意**：Access Token 仅有 4 小时有效期，过期后需要重新生成，不适合自动化场景。

#### 5. 使用 Web 控制面板

1. 打开部署好的 Web 面板 URL
2. 填写配置信息：
   - **GitHub Personal Access Token**: 步骤 3 获取的 Token
   - **GitHub 仓库**: 格式 `username/photo-download`
   - **PhotoPlus 直播页面 URL**: 目标直播页面完整 URL
   - **Dropbox 存储路径**: 默认 `/photos`（自动创建）
   - **检查间隔**: 建议 60 分钟（默认值，最小 10 分钟）
3. **首次运行**：勾选 "清除历史记录" checkbox
4. 点击 **"▶️ 开始监控"**（配置会自动保存）

✅ 完成！GitHub Actions 将按设定间隔自动执行下载任务。

### 运行逻辑

```
每 5 分钟（GitHub Actions cron）在 github_action 分支触发
    ↓
检查 runtime-config.json
    ↓
enabled = false? → 退出（< 5秒，不消耗额度）
    ↓
距离上次运行 < 设定间隔? → 退出（< 5秒）
    ↓
执行下载任务（github_actions_runner.py）
    ↓
下载新照片 → 上传 Dropbox
    ↓
更新 runtime-config.json 和 downloaded.json
    ↓
提交更改到 github_action 分支
```

### 重要说明

**为什么使用 github_action 分支？**

1. **隔离运行环境**：
   - `main` 分支保持代码稳定
   - `github_action` 分支专门用于自动化运行
   - 配置文件（`runtime-config.json`、`downloaded.json`）的自动提交不会污染主分支历史

2. **避免频繁提交**：
   - GitHub Actions 每次运行都会提交配置更新
   - 使用单独分支可以保持主分支的提交历史清晰

3. **灵活控制**：
   - 可以在 `main` 分支开发新功能
   - `github_action` 分支专注于稳定运行
   - 需要更新代码时，从 `main` 合并到 `github_action`

**注意事项**：
- ⚠️ 首次使用前，必须先创建 `github_action` 分支
- ⚠️ GitHub Actions 定时任务（cron）仅在有 workflow 文件的分支上运行
- ⚠️ Web 面板和 Actions 都操作 `github_action` 分支
- ⚠️ `runtime-config.json` 和 `downloaded.json` **不应该**在 .gitignore 中
  - 这两个文件必须提交到 `github_action` 分支
  - Actions 需要读取这些文件保持状态
  - 如果忽略它们会导致无法正常工作

### GitHub Actions 成本估算

- **免费额度**: 2000 分钟/月
- **预估消耗**（以间隔 10 分钟为例）:
  - 每次运行耗时: ~2 分钟（包括安装依赖、下载照片）
  - 每天运行次数: 144 次（24小时 × 6次/小时）
  - 每天消耗: 144 × 2 = **288 分钟**
  - 每月消耗: 288 × 30 = **8640 分钟** ⚠️ **超出免费额度**

**建议调整**：
- **间隔 30 分钟**: 每月 960 分钟 ✅ 在免费额度内
- **间隔 60 分钟**: 每月 480 分钟 ✅ 充分利用免费额度

### 监控状态

在 Web 面板可以查看：
- ✅ 监控状态（运行中/已停止）
- ✅ 上次运行时间
- ✅ 下次预计运行时间
- ✅ 运行结果（成功/失败）
- ✅ 最近 5 次运行日志

### 故障排查

**Q: Actions 运行但没有下载照片**
- 检查 `runtime-config.json` 中 `enabled` 是否为 `true`
- 检查是否满足设定的时间间隔
- 查看 Actions 日志了解详细错误

**Q: Git 提交失败**
- 检查 GitHub Token 是否有 `repo` 权限
- 检查仓库是否有分支保护规则

**Q: Dropbox 上传失败**
- **如果提示 `expired_access_token`**：说明使用的是短期 Access Token（4小时有效期），请切换到 Refresh Token 方式
- **如果提示 `Unable to refresh access token`**：检查是否正确配置了 `DROPBOX_REFRESH_TOKEN`、`DROPBOX_APP_KEY` 和 `DROPBOX_APP_SECRET`
- 检查 Permissions 是否勾选了 `files.content.write`
- 查看 Actions 日志中的详细错误信息

**Q: 如何重置并重新下载所有照片？**
- 勾选 "清除历史记录" checkbox
- 点击 "开始监控"（即使已经在运行）
- 下次运行时会自动删除 `downloaded.json` 并重新开始

---

## 💻 本地持续运行模式

### 启动程序

```bash
uv run python photo_downloader.py
```

### 下载 Picsum 随机图片

如果只想快速获取 50 张来自 [picsum.photos](https://picsum.photos/) 的随机图片，并保存到 `test_photo/` 目录，可以运行：

```bash
uv run python picsum_downloader.py --count 50 --dest test_photo
```

可选参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--width` | 200 | 图片宽度（px） |
| `--height` | 300 | 图片高度（px） |
| `--delay` | 0.1 | 每次下载之间的延迟，避免请求过快 |
| `--retries` | 3 | 单张图片下载失败后的重试次数 |

脚本会自动创建目标目录，文件名包含时间戳与随机后缀，防止覆盖。
### 预期输出

**示例 1：仅本地存储（默认）**

```
============================================================
PhotoPlus 照片自动下载工具启动 (v2.0 - 指纹去重)
目标URL: https://live.photoplus.cn/live/1239677?accessFrom=live#/live
检查间隔: 120秒
Dropbox 存储: 未配置
本地存储: ./photos
已加载历史记录: 0 张照片
============================================================

正在访问页面...
✓ 页面首次加载成功
开始滚动加载所有照片...
✓ 滚动完成，共滚动 3 次，总计 15 张照片
✓ 指纹扫描完成，共 15 张照片

扫描结果:
  - 总计: 15 张照片
  - 已下载: 0 张
  - 新照片: 2 张

开始下载 2 张新照片...
[1/2] 下载: 9T1A3072.JPG
✓ 下载到内存: 9T1A3072.JPG (2456789 字节)
✓ 已保存到本地: ./photos/9T1A3072.JPG

[2/2] 下载: 9T1A3073.JPG
✓ 下载到内存: 9T1A3073.JPG (2345678 字节)
✓ 已保存到本地: ./photos/9T1A3073.JPG

✓ 本次下载完成，成功 2/2 张照片

等待 120 秒后进行下一次检查...
============================================================
```

**示例 2：Dropbox 云盘存储**

```
============================================================
PhotoPlus 照片自动下载工具启动 (v2.0 - 指纹去重)
目标URL: https://live.photoplus.cn/live/1239677?accessFrom=live#/live
检查间隔: 120秒
正在初始化 Dropbox 客户端...
✓ 已创建 Dropbox 目录: /PhotoPlus/photos
Dropbox 存储: 已启用 → /PhotoPlus/photos
本地存储: 已禁用（仅保存到 Dropbox）
已加载历史记录: 0 张照片
============================================================

正在访问页面...
✓ 页面首次加载成功
...

[1/2] 下载: 9T1A3072.JPG
✓ 下载到内存: 9T1A3072.JPG (2456789 字节)
✓ 已上传到 Dropbox: /PhotoPlus/photos/9T1A3072.JPG

[2/2] 下载: 9T1A3073.JPG
✓ 下载到内存: 9T1A3073.JPG (2345678 字节)
✓ 已上传到 Dropbox: /PhotoPlus/photos/9T1A3073.JPG

✓ 本次下载完成，成功 2/2 张照片
============================================================
```

### 停止程序

按 `Ctrl + C` 优雅停止程序。

## ⚙️ 配置说明

所有配置项在 `config.py` 文件中，可根据需要调整：

### 基础配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `TARGET_URL` | `https://live.photoplus.cn/...` | 目标网站URL |
| `CHECK_INTERVAL` | `120` | 检查间隔（秒） |
| `PHOTO_DIR` | `./photos` | 本地照片存储目录 |
| `MAX_CONNECTION_FAILURES` | `10` | 连接失败上限 |
| `MAX_DOWNLOAD_RETRIES` | `5` | 单张照片重试次数 |
| `HEADLESS` | `True` | 无头模式（True=后台运行） |
| `SCROLL_PAUSE_TIME` | `2` | 滚动等待时间（秒） |

### Dropbox 云盘配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DROPBOX_ACCESS_TOKEN` | `""` | Dropbox 访问令牌（留空禁用云盘功能） |
| `DROPBOX_SAVE_PATH` | `"/PhotoPlus/photos"` | Dropbox 云盘存储路径 |
| `SAVE_TO_LOCAL` | `True` | 是否同时保存到本地 |

#### 如何配置 Dropbox

**1. 获取 Access Token**

- 访问 [Dropbox App Console](https://www.dropbox.com/developers/apps)
- 点击 "Create App"
- 选择 "Scoped access" → "Full Dropbox" → 输入应用名称
- 在应用设置页面，找到 "Generated access token" 区域
- 点击 "Generate" 生成访问令牌
- 复制生成的 Token

**2. 配置文件设置**

```python
# config.py
DROPBOX_ACCESS_TOKEN = "sl.xxxxxxxxxxxxxxxxxxxxxx"  # 粘贴您的 Token
DROPBOX_SAVE_PATH = "/PhotoPlus/photos"            # 云盘存储路径（会自动创建）
SAVE_TO_LOCAL = True                                # True=同时保存本地，False=仅云盘
```

**3. 存储模式说明**

| 模式 | 配置示例 | 行为 |
|------|---------|------|
| **仅云盘存储** | `DROPBOX_ACCESS_TOKEN="your_token"`<br>`SAVE_TO_LOCAL=False` | 照片仅上传到 Dropbox，不占用本地空间 |
| **双重备份** | `DROPBOX_ACCESS_TOKEN="your_token"`<br>`SAVE_TO_LOCAL=True` | 同时保存到 Dropbox 和本地 photos/ 目录 |
| **仅本地存储** | `DROPBOX_ACCESS_TOKEN=""`<br>（留空） | 仅保存到本地（默认行为，向后兼容） |

**示例：调整检查间隔为5分钟**

```python
# config.py
CHECK_INTERVAL = 300  # 5分钟
```

## 📁 目录结构

```
photo-download/
├── .github/
│   └── workflows/
│       └── photo-download.yml    # GitHub Actions 工作流
├── .venv/                         # 虚拟环境（自动创建）
├── web/                           # Web 控制面板
│   ├── index.html                 # 前端页面
│   ├── app.js                     # 前端逻辑
│   └── style.css                  # 样式文件
├── photos/                        # 下载的照片存储目录
├── config.py                      # 配置文件
├── photo_downloader.py            # 本地持续运行模式
├── github_actions_runner.py       # GitHub Actions 单次运行模式
├── pyproject.toml                 # 项目依赖配置
├── uv.lock                        # 依赖锁定文件
├── runtime-config.json            # 运行时配置（Web 面板创建）
├── runtime-config.json.example    # 配置文件示例
├── downloaded.json                # 已下载文件记录（自动生成）
└── README.md                      # 本文档
```

## 🛡️ 错误处理

| 错误类型 | 处理策略 |
|---------|---------|
| **连接失败** | 累计10次后程序自动退出 |
| **下载失败** | 单张照片重试5次后跳过 |
| **元素未找到** | 记录警告日志，跳过该照片继续处理 |
| **页面加载超时** | 自动重试，计入连接失败次数 |

## 💡 常见问题

### Q: 首次运行速度较慢？
A: Playwright 首次需要下载浏览器文件（约200MB），后续运行会快很多。

### Q: 如何查看已下载的照片？
A:
- **本地存储**: 照片保存在 `./photos/` 目录下
- **Dropbox 存储**: 登录 Dropbox 网页版或客户端，进入配置的路径（如 `/PhotoPlus/photos`）

### Q: 如何清空下载历史重新下载？
A: 删除 `downloaded.json` 文件即可，程序会重新下载所有照片。

### Q: Dropbox 上传失败怎么办？
A: 请检查：
1. **Token 是否有效**: 访问 Dropbox App Console 检查 Token 状态
2. **网络连接**: 确保能正常访问 Dropbox API（国内可能需要代理）
3. **存储空间**: 检查 Dropbox 账户是否有足够的剩余空间
4. **查看日志**: 程序会输出详细的错误信息，可根据提示排查

### Q: 如何仅使用 Dropbox 不保存本地？
A: 在 `config.py` 中设置：
```python
DROPBOX_ACCESS_TOKEN = "your_token"  # 填入有效 Token
SAVE_TO_LOCAL = False                # 设置为 False
```

### Q: Dropbox Token 安全吗？
A: **安全提示**：
- ⚠️ Access Token 拥有完整的 Dropbox 访问权限，请妥善保管
- ⚠️ 不要将包含 Token 的 `config.py` 提交到公开代码仓库
- ✅ 建议将 `config.py` 添加到 `.gitignore` 中
- ✅ 如 Token 泄露，请立即在 Dropbox App Console 撤销并重新生成

### Q: 程序占用资源太高？
A: 可以在 `config.py` 中：
- 增加 `CHECK_INTERVAL` 延长检查间隔
- 调整 `SCROLL_PAUSE_TIME` 减少滚动等待时间

### Q: 如何在后台运行？
A: **Linux/macOS:**
```bash
nohup uv run python photo_downloader.py > output.log 2>&1 &
```

**Windows:**
```powershell
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python photo_downloader.py"
```

### Q: 如何查看更详细的错误信息？
A: 修改 `photo_downloader.py` 中的日志级别：
```python
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG
    ...
)
```

## 🔧 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.8+ | 编程语言 |
| uv | latest | 包管理器 |
| Playwright | 1.40+ | 浏览器自动化 |
| requests | 2.31+ | HTTP下载 |
| dropbox | 12.0+ | Dropbox 云盘 API（可选） |

## 📝 开发说明

### 项目结构说明

- **DownloadHistory**: 管理已下载文件记录，使用JSON持久化
- **PhotoExtractor**: 负责页面滚动、元素定位、URL提取
- **PhotoDownloader**: 处理文件下载和重试逻辑
- **scroll_to_load_all**: 智能滚动直到加载所有内容
- **main**: 异步主循环，协调各组件工作

### 核心流程

```
启动程序
  ↓
初始化组件（历史记录、下载器、提取器、Dropbox客户端）
  ↓
启动Playwright浏览器
  ↓
┌────────────────────────┐
│ 主循环（每2分钟）       │
├────────────────────────┤
│ 1. 访问目标页面        │
│ 2. 滚动加载所有照片     │
│ 3. 逐个提取原图URL      │
│ 4. 过滤已下载照片       │
│ 5. 下载新照片到内存     │
│ 6. 上传到Dropbox（可选）│
│ 7. 保存到本地（可选）   │
│ 8. 更新历史记录        │
│ 9. 等待下次检查        │
└────────────────────────┘
  ↓
错误处理（重试/跳过/退出）
```

### DOM选择器

```python
# 照片列表项
PHOTO_ITEM_SELECTOR = "div.photo-content.container li.photo-item"

# 照片点击元素
PHOTO_CLICK_SELECTOR = "span"  # li.photo-item内的span

# 原图链接
VIEW_ORIGINAL_SELECTOR = "div.operate-buttons li.row-all-center a"
```

## 📄 许可证

本项目仅供学习交流使用，请遵守目标网站的使用条款。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**⭐ 如果这个工具对您有帮助，请给个Star！**
