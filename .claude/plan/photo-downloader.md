# PhotoPlus 照片自动下载工具 - 执行计划

## 📋 项目概览

**项目名称**: PhotoPlus 照片自动下载工具
**创建日期**: 2025-11-04
**技术栈**: Python 3.8+ | Playwright | uv
**项目管理**: uv

## 🎯 需求总结

### 核心功能
- 每2分钟自动访问指定网页
- 读取网页上的照片并提取原图URL
- 下载新出现的不重复照片到本地
- 避免下载缩略图，下载原图
- 命令行运行，日志输出到控制台

### 技术要求
- **语言**: Python
- **包管理**: uv
- **浏览器自动化**: Playwright
- **目标网站**: https://live.photoplus.cn/live/1239677?accessFrom=live#/live

### 错误处理策略
- 连接失败：累计10次后停止程序
- 下载失败：单张照片重试5次后跳过
- 自动化失败：打印错误但继续运行
- 不需要额外通知

### 存储与去重
- 存储路径：`./photos/`
- 去重方式：基于文件名
- 文件名规则：保持原始文件名（如 9T1A3072.JPG）

## 🏗️ 技术方案

### 选择的方案：Playwright + Requests 混合方案

**核心流程：**
1. Playwright访问页面并滚动加载所有照片
2. 点击每张照片打开详情
3. 从 `a` 标签的 `href` 属性获取原图URL（无需打开新标签页）
4. 使用 `requests` 直接下载原图
5. 基于文件名去重保存

**DOM结构：**
- 照片列表：`div.photo-content.container li.photo-item`
- 照片元素：`li.photo-item > span`（可点击）
- 原图链接：`div.operate-buttons li.row-all-center a[href]`
- 关闭详情：按 `Escape` 键或点击照片以外区域

**技术优势：**
- ✅ 避免处理浏览器下载对话框
- ✅ 下载速度快（Playwright仅用于获取URL）
- ✅ 文件名控制精确
- ✅ 资源占用适中

## 📦 项目结构

```
photo-download/
├── .venv/               # uv虚拟环境
├── .claude/
│   └── plan/
│       └── photo-downloader.md
├── photos/              # 照片存储目录
├── config.py            # 配置文件
├── photo_downloader.py  # 主程序
├── pyproject.toml       # uv项目配置
├── uv.lock              # 依赖锁定
├── downloaded.json      # 下载历史记录
└── README.md            # 使用文档
```

## 🔧 实现步骤

### ✅ 步骤1：项目初始化
- [x] 使用 `uv init` 初始化项目
- [x] 使用 `uv add` 添加依赖（playwright, requests）
- [x] 安装 Playwright 浏览器：`uv run playwright install chromium`
- [x] 创建 `config.py` 配置文件

**配置项：**
```python
TARGET_URL = "https://live.photoplus.cn/live/1239677?accessFrom=live#/live"
CHECK_INTERVAL = 120
PHOTO_DIR = "./photos"
MAX_CONNECTION_FAILURES = 10
MAX_DOWNLOAD_RETRIES = 5
HEADLESS = True
SCROLL_PAUSE_TIME = 2
```

### ✅ 步骤2：实现 DownloadHistory 类
- [x] 从JSON文件加载历史记录
- [x] 检查文件是否已下载（基于文件名）
- [x] 添加新下载记录
- [x] 保存历史记录到JSON文件

**数据结构：**
```json
{
  "downloaded_files": ["9T1A3072.JPG", "9T1A3073.JPG"],
  "last_update": "2025-11-04 10:30:15"
}
```

### ✅ 步骤3：实现 scroll_to_load_all 函数
- [x] 滚动到页面底部
- [x] 等待内容加载（SCROLL_PAUSE_TIME）
- [x] 比对页面高度判断是否加载完成
- [x] 循环直到没有新内容

**逻辑：**
```python
while True:
    滚动到底部
    等待加载
    if 高度未变化:
        break
```

### ✅ 步骤4：实现 PhotoExtractor 类
- [x] 调用滚动加载所有照片
- [x] 获取所有 `li.photo-item` 元素
- [x] 逐个点击 `span` 元素打开详情
- [x] 定位并提取 `a[href]` 原图链接
- [x] 从URL提取文件名
- [x] 按 `Escape` 关闭详情
- [x] 异常处理和日志记录

**核心方法：**
- `extract_photo_urls(page)`: 返回 `[{url, filename}, ...]`
- `_extract_filename_from_url(url)`: 从URL提取文件名

### ✅ 步骤5：实现 PhotoDownloader 类
- [x] 使用 `requests.get()` 下载图片
- [x] 流式写入文件（chunk_size=8192）
- [x] 重试逻辑（最多5次）
- [x] 每次失败等待2秒
- [x] 详细的日志输出

**核心方法：**
- `download_photo(url, filename)`: 返回 True/False

### ✅ 步骤6：实现 main 主循环
- [x] 初始化所有组件
- [x] 启动 Playwright 浏览器
- [x] 无限循环逻辑：
  - 访问页面（记录失败次数）
  - 提取照片URLs
  - 过滤已下载照片
  - 下载新照片
  - 更新历史记录
  - 等待2分钟
- [x] 连接失败10次退出
- [x] `KeyboardInterrupt` 优雅退出

### ✅ 步骤7：日志系统
- [x] 配置日志格式：`时间 [级别] 消息`
- [x] INFO：正常操作
- [x] WARNING：可恢复错误
- [x] ERROR：严重错误

### ✅ 步骤8：创建文档
- [x] `README.md`：使用说明、配置、常见问题
- [x] 本计划文档

## 🚀 使用方式

```bash
# 安装依赖
uv sync

# 安装浏览器（首次）
uv run playwright install chromium

# 运行程序
uv run python photo_downloader.py

# 停止程序
Ctrl + C
```

## 🎯 成功标准

- [x] 程序能成功访问目标网页
- [x] 能够滚动加载所有照片
- [x] 能够提取原图URL
- [x] 能够下载照片到本地
- [x] 文件名去重机制正常工作
- [x] 错误处理符合预期
- [x] 日志输出清晰可读

## 📝 待优化项

见优化阶段分析。

## 🔍 技术要点

### 关键选择器
```python
PHOTO_ITEM_SELECTOR = "div.photo-content.container li.photo-item"
PHOTO_CLICK_SELECTOR = "span"
VIEW_ORIGINAL_SELECTOR = "div.operate-buttons li.row-all-center a"
```

### 异步编程
- 使用 `async/await` 语法
- `asyncio.run(main())` 运行主函数
- Playwright API 全部为异步

### 错误容忍
- 单张照片失败不影响整体
- 连接失败有重试机制
- 元素未找到跳过继续

## 📊 性能考虑

- **滚动加载**：每次等待2秒确保内容加载完成
- **点击等待**：每次点击后等待1秒确保详情加载
- **下载超时**：30秒超时避免长时间挂起
- **内存管理**：流式下载避免大文件占用内存

---

**执行状态**: ✅ 实现完成
**下一步**: 代码优化与质量审查
