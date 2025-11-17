# Dropbox 云盘集成功能实施计划

## 📋 任务概述

**目标：** 为 PhotoPlus 照片下载工具添加 Dropbox 云盘存储支持

**需求：**
- 支持将照片上传到 Dropbox 云盘
- 配置项控制是否同时保存本地副本
- 可自定义 Dropbox 存储路径（自动创建）
- 保持现有增量下载和历史记录机制

## 🎯 选定方案

**方案二：直接增强式**
- 在现有 `PhotoDownloader` 类中直接添加 Dropbox 上传逻辑
- 符合 KISS 和 YAGNI 原则
- 修改点集中，易于维护

## 📝 详细执行步骤

### 步骤1：添加依赖包
- **命令：** `uv add dropbox`
- **预期：** dropbox SDK 添加到 pyproject.toml

### 步骤2：扩展配置文件 (config.py)
新增配置项：
```python
# Dropbox配置
DROPBOX_ACCESS_TOKEN = ""  # Dropbox访问令牌
DROPBOX_SAVE_PATH = "/PhotoPlus/photos"  # Dropbox存储路径
SAVE_TO_LOCAL = True  # 是否同时保存到本地
```

### 步骤3：创建 Dropbox 辅助函数 (photo_downloader.py)
- `init_dropbox_client(access_token)` - 初始化客户端
- `ensure_dropbox_path(client, path)` - 确保路径存在

### 步骤4：扩展 PhotoDownloader 类
- 修改 `__init__` 添加 dropbox_client 和 dropbox_path 参数
- 重构 `download_photo` 方法：下载→上传Dropbox→保存本地（可选）
- 新增 `_upload_to_dropbox` 方法（支持重试）
- 新增 `_save_to_local` 方法

### 步骤5：修改 main() 函数
- 初始化 Dropbox 客户端
- 确保 Dropbox 路径存在
- 将客户端传递给 PhotoDownloader

### 步骤6：更新依赖导入
- 添加 `from io import BytesIO`
- 添加 `import dropbox` 和 `import dropbox.exceptions`

## 🎯 预期行为

### 场景1：仅 Dropbox 存储
- `DROPBOX_ACCESS_TOKEN` 已配置
- `SAVE_TO_LOCAL = False`
- 照片仅上传到 Dropbox

### 场景2：双重存储
- `DROPBOX_ACCESS_TOKEN` 已配置
- `SAVE_TO_LOCAL = True`
- 照片同时保存到 Dropbox 和本地

### 场景3：仅本地（向后兼容）
- `DROPBOX_ACCESS_TOKEN = ""`
- 行为与原版一致

## ⚠️ 风险应对

| 风险 | 应对措施 |
|------|---------|
| API限流 | 使用重试机制（5次） |
| 内存占用 | BytesIO 暂存，单张照片<10MB可接受 |
| Token泄露 | 配置文件添加安全提示 |
| 路径不存在 | 自动创建路径 |

## ✅ 质量检查点

- [ ] Dropbox 配置项正确添加
- [ ] dropbox 依赖已安装
- [ ] Dropbox 路径自动创建
- [ ] 三种场景均正常工作
- [ ] 上传失败正确跳过并记录
- [ ] downloaded.json 正常更新

## 📊 修改统计

- **修改文件：** 2个（config.py, photo_downloader.py）
- **新增文件：** 0个
- **预计代码量：** ~100行

## 🔧 技术细节

### 下载流程变更

**原流程：**
```
下载 → 保存到本地文件
```

**新流程：**
```
下载到内存(BytesIO) → 上传Dropbox（可选） → 保存本地（可选）
```

### 认证方式

使用 Access Token 直接认证（用户配置在 config.py）

---

**创建时间：** 2025-11-17
**状态：** 执行中
