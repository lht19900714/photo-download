# 解决照片获取问题 - 强制页面刷新方案

**创建时间:** 2025-11-16
**状态:** 待实施
**方案选择:** 方案1 - 强制页面刷新 + 禁用缓存

---

## 问题描述

### 现象
- 系统首次运行时能准确获取页面上所有照片
- 等待间隔后再次检查时无法获取新上传的照片
- 重启系统后又能完整获取所有照片（包括新上传的）

### 用户环境
- 内存/浏览器资源：无限制
- 照片上传频率：约1分钟/张
- 检查间隔：60秒

---

## 问题根因分析

### 根本原因1: 页面缓存问题
**位置:** `photo_downloader.py:306`

当前代码：
```python
await page.goto(TARGET_URL, wait_until="networkidle")
```

**问题:**
- `page.goto()` 可能使用浏览器缓存，不强制从服务器获取最新数据
- 动态加载的照片依赖JavaScript渲染，缓存的HTML不包含新上传的照片

### 根本原因2: 增量索引机制缺陷
**位置:** `photo_downloader.py:313`

当前逻辑：
```python
new_photos = await extractor.extract_photo_urls(page, history.last_processed_index)
```

**问题:**
- `start_index` 持续增长（如从0→15→30）
- 如果页面使用缓存，`total_count` 不更新（仍为15）
- `range(start_index, total_count)` 变为空（如range(30, 15)）
- 导致无照片被提取

### 根本原因3: 滚动加载失效
**位置:** `photo_downloader.py:93-141`

**问题:**
- 滚动逻辑假设滚动会触发新内容加载
- 如果页面数据来自缓存，滚动不会触发服务器请求
- 快速达到"连续3次未变化"条件，提前终止

### 为什么重启后恢复正常
- 重启后 `last_processed_index` 重置为0
- 首次 `page.goto()` 必定从服务器获取最新数据
- 能正常提取所有照片

---

## 解决方案对比

### 方案1: 强制页面刷新 + 禁用缓存 ⭐ 已选择
- **优点:** 实施简单，仅需修改1-2处代码
- **缺点:** 增量索引逻辑可能仍失效，每次重新加载完整页面

### 方案2: 废弃增量索引 + 全量提取
- **优点:** 逻辑简单可靠，不会漏照片
- **缺点:** 每次都点击所有照片元素，效率较低

### 方案3: JavaScript动态刷新
- **优点:** 刷新速度快
- **缺点:** 依赖网站内部API，实施复杂

### 方案4: 混合方案（推荐但未选择）
- **优点:** 最可靠，双重保障
- **缺点:** 性能稍差

---

## 实施计划（方案1）

### 步骤1: 禁用浏览器缓存策略

**文件:** `photo_downloader.py`
**位置:** 约294-295行

**当前代码:**
```python
browser = await p.chromium.launch(headless=HEADLESS)
context = await browser.new_context()
```

**修改为:**
```python
browser = await p.chromium.launch(headless=HEADLESS)
context = await browser.new_context(
    extra_http_headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
)
```

**作用:** 禁用浏览器缓存，强制每次从服务器获取资源

---

### 步骤2: 修改主循环页面访问逻辑

**文件:** `photo_downloader.py`
**位置:** 约302-310行

**当前代码:**
```python
while True:
    try:
        # 1. 访问页面
        logging.info("\n正在访问页面...")
        await page.goto(TARGET_URL, wait_until="networkidle")
        await page.wait_for_timeout(PAGE_RENDER_WAIT)

        connection_failures = 0
        logging.info("✓ 页面加载成功")
```

**修改为:**
```python
loop_count = 0  # 在while循环前添加计数器

while True:
    try:
        # 1. 访问/刷新页面
        if loop_count == 0:
            # 首次访问
            logging.info("\n正在访问页面...")
            await page.goto(TARGET_URL, wait_until="networkidle")
        else:
            # 后续刷新
            logging.info("\n正在刷新页面...")
            await page.reload(wait_until="networkidle")

        loop_count += 1
        await page.wait_for_timeout(PAGE_RENDER_WAIT)

        connection_failures = 0
        if loop_count == 1:
            logging.info("✓ 页面首次加载成功")
        else:
            logging.info(f"✓ 页面刷新成功（第 {loop_count} 次循环）")
```

**作用:**
- 首次使用 `goto()` 正常加载
- 后续使用 `reload()` 强制刷新
- 日志区分首次和刷新行为

---

### 步骤3: 验证修复效果

**测试步骤:**
1. 删除 `downloaded.json`（可选，便于观察完整流程）
2. 运行 `uv run python photo_downloader.py`
3. 观察首次循环日志：应显示"页面首次加载成功"
4. 等待60秒观察第二次循环：
   - 日志应显示"正在刷新页面..."和"页面刷新成功（第2次循环）"
   - 应能检测到新上传的照片

**成功标准:**
- 每次循环都能检测到新上传的照片
- `发现 X 张照片，其中 Y 张为新照片` 中的Y值随时间增长

---

## 风险和缓解措施

### 风险1: reload() 兼容性问题
- **概率:** 低
- **影响:** 页面刷新失败
- **缓解:** 如失败可回退使用 `page.goto()`

### 风险2: 增量索引仍失效
- **概率:** 中
- **影响:** 可能仍无法获取新照片
- **缓解:** 如方案1效果不佳，切换到方案4（强制刷新 + 全量提取）

### 风险3: 网络超时
- **概率:** 低
- **影响:** 触发异常处理
- **缓解:** 现有异常处理机制已覆盖

---

## 后续优化建议

如果方案1效果不理想，建议按优先级尝试：

1. **立即优化:** 切换到方案4（添加 `start_index=0` 参数）
2. **性能优化:** 仅点击文件名不在历史中的照片（避免重复点击）
3. **深度优化:** 逆向分析网站API，实现JavaScript动态刷新（方案3）

---

## 涉及的代码文件

| 文件 | 函数/类 | 行号范围 | 修改类型 |
|------|--------|---------|---------|
| `photo_downloader.py` | `main()` | 294-295 | 修改浏览器上下文创建 |
| `photo_downloader.py` | `main()` | 302-310 | 修改页面访问逻辑 |

**总代码改动量:** 约10行（新增5行，修改5行）

---

## 实施注意事项

1. ✅ 保留原有增量索引逻辑
2. ✅ 向后兼容首次运行场景
3. ✅ 添加循环次数日志便于调试
4. ✅ 建议测试时先删除 `downloaded.json`
5. ⚠️ 刷新会导致页面重新加载所有资源（预计2-5秒）

---

## 参考文档

- Playwright API: `page.reload()` - https://playwright.dev/python/docs/api/class-page#page-reload
- HTTP Cache Headers - https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
