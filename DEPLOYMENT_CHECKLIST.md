# 部署检查清单

## ✅ 部署前准备

### 1. .gitignore 文件配置
- [x] ✅ 已添加 `photos/` 目录（本地照片不需要提交）
- [x] ❌ **已移除** `runtime-config.json`（必须提交到 github_action 分支）
- [x] ❌ **已移除** `downloaded.json`（必须提交到 github_action 分支）
- [ ] **重要**：检查 `config.py` 中的 Dropbox Token 是否需要移除

**重要说明**：
- `runtime-config.json` 和 `downloaded.json` **不应该**在 .gitignore 中
- 这两个文件必须提交到 `github_action` 分支
- GitHub Actions 每次运行都会读取和更新这些文件
- 如果忽略它们，会导致：
  - ❌ 无法判断运行状态（runtime-config.json）
  - ❌ 重复下载所有照片（downloaded.json）

### 2. 创建 github_action 分支
```bash
# 在本地创建并推送 github_action 分支
git checkout -b github_action
git push -u origin github_action
```

### 3. 验证分支配置
- [ ] `.github/workflows/photo-download.yml` 存在于 `github_action` 分支
- [ ] workflow 文件中指定了 `github_action` 分支
- [ ] `web/app.js` 中的分支引用已改为 `github_action`

---

## 🌐 部署步骤

### Step 1: 部署前端到 Cloudflare Pages
- [ ] 访问 [Cloudflare Pages](https://pages.cloudflare.com/)
- [ ] 连接 GitHub 仓库
- [ ] 构建配置：
  - 构建命令：（留空）
  - 输出目录：`web`
  - **生产分支**：`github_action`
- [ ] 记录部署后的 URL

### Step 2: 获取 GitHub Personal Access Token
- [ ] 访问 [Token 设置](https://github.com/settings/tokens/new)
- [ ] 勾选权限：`repo` + `workflow`
- [ ] 复制并保存 Token（只显示一次）

### Step 3: 获取 Dropbox Access Token
- [ ] 访问 [Dropbox Console](https://www.dropbox.com/developers/apps)
- [ ] 创建应用并生成 Token
- [ ] 复制并保存 Token

### Step 4: 配置 Web 面板
- [ ] 打开部署的 URL
- [ ] 填写所有配置信息
- [ ] 点击"保存配置"
- [ ] 首次运行时勾选"清除历史记录"
- [ ] 点击"开始监控"

### Step 5: 配置 GitHub Secret
- [ ] 访问仓库 Settings → Secrets and variables → Actions
- [ ] 添加 Secret：
  - Name: `DROPBOX_ACCESS_TOKEN`
  - Value: (Dropbox Token)
- [ ] 保存

---

## 🔍 验证部署

### 测试 Web 面板
- [ ] 配置能正常保存和加载
- [ ] 点击"立即执行一次"能触发 Actions
- [ ] 状态显示正常
- [ ] 日志能正常显示

### 测试 GitHub Actions
- [ ] 访问仓库 Actions 标签页
- [ ] 查看"Photo Download Monitor"工作流
- [ ] 确认定时任务已启用（绿色圆点）
- [ ] 手动触发一次验证运行

### 验证下载功能
- [ ] 查看 Actions 运行日志
- [ ] 确认照片下载成功
- [ ] 检查 Dropbox 中的照片
- [ ] 确认 `runtime-config.json` 和 `downloaded.json` 已更新

---

## ⚠️ 安全检查

### 敏感信息保护
- [ ] ⚠️ **重要**：`config.py` 包含 Dropbox Token，确认是否需要从仓库中移除
  ```bash
  # 如果需要移除（推荐）
  git rm --cached config.py
  echo "config.py" >> .gitignore
  git commit -m "Remove sensitive config file"
  ```
- [ ] GitHub Token 仅存储在浏览器 localStorage
- [ ] Dropbox Token 已配置到 GitHub Secrets
- [ ] 确认没有其他敏感信息在仓库中

### Token 权限检查
- [ ] GitHub Token 权限最小化（仅 `repo` + `workflow`）
- [ ] Dropbox Token 权限最小化（仅 `files.content.write`）

---

## 📊 监控和维护

### 定期检查
- [ ] 每周查看 GitHub Actions 运行情况
- [ ] 检查 Actions 消耗时间（避免超出免费额度）
- [ ] 验证 Dropbox 存储空间充足

### 成本优化
- [ ] 根据实际需求调整检查间隔
  - 10 分钟：每月 8640 分钟 ❌ 超额
  - 30 分钟：每月 2880 分钟 ❌ 超额
  - **60 分钟**：每月 1440 分钟 ✅ **推荐**

### 故障排查
如遇问题，查看：
1. GitHub Actions 运行日志
2. Web 面板的运行日志区域
3. 仓库的 `runtime-config.json` 文件状态

---

## 📝 注意事项

### 状态文件管理（重要）

#### runtime-config.json
- ❌ **不要**手动创建（首次由 Web 面板自动创建）
- ✅ **必须提交**到 github_action 分支
- ✅ Web 面板通过 GitHub API 读取和更新
- ✅ GitHub Actions 读取此文件判断是否运行

**生命周期**：
1. 用户点击"开始监控" → Web 面板通过 API 创建并提交到 github_action 分支
2. GitHub Actions 每 5 分钟读取此文件 → 检查 enabled 和 interval
3. Actions 运行后更新 lastRunTime → 提交到 github_action 分支
4. 下次运行时读取上次的时间戳 → 判断是否满足间隔

#### downloaded.json
- ❌ **不要**添加到 .gitignore
- ✅ **必须提交**到 github_action 分支
- ✅ 记录所有已下载照片的指纹
- ✅ GitHub Actions 读取此文件避免重复下载

**生命周期**：
1. 首次运行时不存在 → 自动创建空历史
2. 每次下载照片后添加指纹记录 → 提交到 github_action 分支
3. 下次运行时读取历史 → 跳过已下载的照片
4. 如果勾选"清除历史"→ Actions 删除此文件 → 重新下载所有照片

### 分支管理
- `main` 分支：代码开发和稳定版本
- `github_action` 分支：自动化运行专用
- 更新代码：在 `main` 开发 → 合并到 `github_action`

### 更新代码流程
```bash
# 在 main 分支开发
git checkout main
git add .
git commit -m "Update feature"
git push

# 合并到 github_action 分支
git checkout github_action
git merge main
git push
```

---

## ✅ 部署完成

完成以上所有步骤后，您的 PhotoPlus 自动下载系统将：
- ✅ 每小时（或您设定的间隔）自动检查新照片
- ✅ 自动下载并上传到 Dropbox
- ✅ 通过 Web 面板查看状态和日志
- ✅ 完全运行在云端，无需本地保持运行

**祝您使用愉快！** 📸
