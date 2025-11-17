# 去重逻辑修复方案 - 详细实施计划

## 任务背景

**问题描述：** 程序运行中大量新照片漏下载 (>10张)

**根本原因分析：**
1. **索引机制与动态插入不兼容：** 照片列表支持中间插入，但程序假设仅追加，导致插入位置之前的照片被跳过
2. **文件名去重时机错误：** 跳过已下载照片时仍更新索引，导致后续照片漏检
3. **索引基准不稳定：** 列表长度/顺序变化时，索引值失去参考意义

**解决方案：** 采用方案3 - 基于缩略图URL指纹的去重机制

## DOM结构验证结果

**验证日期：** 2025-11-16

**关键发现：**
- ✅ 所有照片元素(100%)都有缩略图URL: `img[src]`
- ✅ URL格式稳定: `//pb.plusx.cn/plus/immediate/{项目ID}/{时间戳}/{文件名}.jpg~{CDN参数}`
- ✅ 文件名可直接提取作为唯一指纹
- ✅ 无需点击照片即可获取指纹

**性能预估：**
- 当前方案：100张照片需点击100次 (~150秒)
- 新方案：100张照片中80张已下载，仅需点击20次 (~5秒扫描 + 30秒点击 = 35秒)
- **性能提升：77%**

## 实施计划

### 阶段1: 数据结构设计与迁移准备

#### 1.1 新数据结构设计

**旧格式 (v1):**
```json
{
  "downloaded_files": ["2:30721.jpg", "3:6470.jpg"],
  "last_processed_index": 5,
  "last_update": "2025-11-16 23:13:15"
}
```

**新格式 (v2):**
```json
{
  "version": "2.0",
  "downloads": {
    "1060536x354blur2.jpg": {
      "original_filename": "2:30721.jpg",
      "thumbnail_url": "//pb.plusx.cn/plus/immediate/35272685/2025111623814917/1060536x354blur2.jpg~...",
      "download_time": "2025-11-16 23:13:15"
    },
    "124536x354.jpg": {
      "original_filename": "3:6470.jpg",
      "thumbnail_url": "//pb.plusx.cn/.../124536x354.jpg~...",
      "download_time": "2025-11-16 23:13:16"
    }
  },
  "last_update": "2025-11-16 23:13:16"
}
```

**字段说明：**
- `version`: 数据格式版本号
- `downloads`: 指纹到下载信息的映射
  - Key: 缩略图文件名（指纹）
  - Value: 下载元数据
    - `original_filename`: 原图实际文件名（保存到photos/的文件名）
    - `thumbnail_url`: 缩略图完整URL（用于调试）
    - `download_time`: 下载时间戳

#### 1.2 数据迁移工具类实现

**文件：** `photo_downloader.py`

**新增类：** `HistoryMigrator`

```python
class HistoryMigrator:
    """历史数据格式迁移工具"""

    @staticmethod
    def detect_version(data: dict) -> str:
        """检测数据版本"""
        if 'version' in data:
            return data['version']
        elif 'downloaded_files' in data:
            return '1.0'
        return 'unknown'

    @staticmethod
    def migrate_from_v1(old_data: dict) -> dict:
        """
        从v1格式迁移到v2

        迁移策略：
        - downloaded_files中的文件名作为original_filename
        - 指纹使用 "migrated_{文件名}" 格式（无法回溯缩略图URL）
        - thumbnail_url留空
        - download_time使用迁移时间
        """
        pass  # 详细实现见代码
```

**预期输出：**
```
[INFO] 检测到旧格式数据 (v1.0)
[INFO] 正在迁移 5 条历史记录...
[INFO] ✓ 数据迁移完成，已升级到 v2.0
```

---

### 阶段2: 核心类重构

#### 2.1 重构 `DownloadHistory` 类

**文件：** `photo_downloader.py` (第46-93行)

**修改清单：**

| 修改类型 | 旧代码 | 新代码 |
|---------|--------|--------|
| 属性删除 | `self.downloaded_files: Set[str]` | (删除) |
| 属性删除 | `self.last_processed_index: int` | (删除) |
| 属性新增 | - | `self.downloads: Dict[str, Dict]` |
| 属性新增 | - | `self.version: str = "2.0"` |
| 方法修改 | `_load_history()` | 加入版本检测和迁移逻辑 |
| 方法修改 | `save_history()` | 保存新格式数据 |
| 方法删除 | `is_downloaded(filename: str)` | (删除) |
| 方法新增 | - | `is_downloaded_by_fingerprint(fingerprint: str)` |
| 方法删除 | `add_downloaded(filename: str)` | (删除) |
| 方法新增 | - | `add_download_record(fingerprint, filename, thumbnail_url)` |
| 方法删除 | `update_processed_index(index: int)` | (删除) |

**新方法接口定义：**

```python
def is_downloaded_by_fingerprint(self, fingerprint: str) -> bool:
    """检查指纹是否已下载"""
    return fingerprint in self.downloads

def add_download_record(self, fingerprint: str, original_filename: str, thumbnail_url: str):
    """添加下载记录"""
    self.downloads[fingerprint] = {
        "original_filename": original_filename,
        "thumbnail_url": thumbnail_url,
        "download_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
```

**迁移逻辑集成：**

```python
def _load_history(self):
    """从JSON文件加载历史记录（自动迁移旧格式）"""
    if not os.path.exists(self.history_file):
        return

    try:
        with open(self.history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 检测版本
        version = HistoryMigrator.detect_version(data)

        if version == '1.0':
            logging.info("检测到旧格式数据，正在迁移...")
            data = HistoryMigrator.migrate_from_v1(data)
            logging.info("✓ 数据迁移完成")

        # 加载新格式数据
        self.version = data.get('version', '2.0')
        self.downloads = data.get('downloads', {})

    except Exception as e:
        logging.warning(f"加载历史记录失败: {e}")
```

---

#### 2.2 扩展 `PhotoExtractor` 类

**文件：** `photo_downloader.py` (第145-234行)

**新增方法1: `extract_fingerprints_fast()`**

```python
async def extract_fingerprints_fast(self, page: Page) -> List[Dict[str, str]]:
    """
    快速提取所有照片的指纹（无需点击）

    实现步骤：
    1. 滚动加载所有照片
    2. 获取所有照片元素
    3. 逐个读取 img[src] 属性
    4. 调用 _extract_filename_from_thumbnail() 提取指纹
    5. 返回指纹列表

    返回格式:
    [
        {
            "index": 0,
            "fingerprint": "1060536x354blur2.jpg",
            "thumbnail_url": "//pb.plusx.cn/.../1060536x354blur2.jpg~..."
        },
        ...
    ]
    """
    # 详细实现见代码
```

**性能特点：**
- 每张照片仅需一次DOM属性读取 (~0.01秒)
- 100张照片总耗时 ~1-2秒
- 相比点击方式提升 99% 性能

**新增方法2: `_extract_filename_from_thumbnail()`**

```python
def _extract_filename_from_thumbnail(self, url: str) -> str:
    """
    从缩略图URL提取文件名作为指纹

    输入示例:
    //pb.plusx.cn/plus/immediate/35272685/2025111623814917/1060536x354blur2.jpg~tplv-9lv23dm2t1-wm-display...

    处理步骤:
    1. 修复相对协议URL (// -> https://)
    2. 去除query参数 (?之后的部分)
    3. 分割路径 (按 / 分割)
    4. 取最后一段: "1060536x354blur2.jpg~tplv-..."
    5. 去除CDN后缀 (~之后的部分)

    输出: "1060536x354blur2.jpg"
    """
    # 详细实现见代码
```

**边界情况处理：**
- URL为空 → 返回空字符串，触发降级逻辑
- URL格式异常 → 捕获异常，返回降级指纹
- 文件名包含特殊字符 → 保留原样（已验证兼容）

**修改方法3: `extract_photo_urls()` → `extract_photo_urls_by_fingerprints()`**

**旧接口：**
```python
async def extract_photo_urls(self, page: Page, start_index: int = 0) -> List[Dict]:
    """从start_index开始提取所有照片URL"""
```

**新接口：**
```python
async def extract_photo_urls_by_fingerprints(
    self,
    page: Page,
    target_fingerprints: List[str]
) -> List[Dict[str, str]]:
    """
    仅对指定指纹的照片获取原图URL

    参数:
        target_fingerprints: 需要处理的指纹列表

    实现逻辑:
    1. 获取所有照片元素
    2. 遍历照片元素，读取缩略图URL
    3. 提取指纹，检查是否在 target_fingerprints 中
    4. 如果在列表中，点击获取原图URL
    5. 如果不在，跳过（无需任何操作）

    返回格式:
    [
        {
            "fingerprint": "1060536x354blur2.jpg",
            "url": "https://原图URL",
            "filename": "2:30721.jpg",
            "thumbnail_url": "//缩略图URL"
        },
        ...
    ]
    """
    # 详细实现见代码
```

**性能优化：**
- 已下载照片：0次点击（仅读取DOM）
- 未下载照片：1次点击
- 总耗时 = 扫描时间 + (新照片数量 × 1.5秒)

---

### 阶段3: 主流程逻辑改造

#### 3.1 修改 `main()` 函数

**文件：** `photo_downloader.py` (第387-420行)

**旧逻辑流程图：**
```
访问页面 → 从last_processed_index开始提取URL →
文件名去重 → 下载 → 更新索引 → 保存历史
```

**新逻辑流程图：**
```
访问页面 → 快速扫描所有指纹(~2秒) →
识别未下载指纹 → 仅对新照片点击获取URL →
下载 → 记录指纹+文件名 → 保存历史
```

**详细代码对比：**

**旧代码 (第387-420行):**
```python
# 2. 从上次处理的位置开始提取照片URL（增量提取）
new_photos = await extractor.extract_photo_urls(page, history.last_processed_index)

# 3. 下载新照片
if new_photos:
    logging.info(f"\n开始下载 {len(new_photos)} 张新照片...")
    success_count = 0

    for idx, photo in enumerate(new_photos, 1):
        # 跳过已下载的照片（断点续传）
        if history.is_downloaded(photo['filename']):
            logging.info(f"\n[{idx}/{len(new_photos)}] 跳过已下载: {photo['filename']}")
            history.update_processed_index(photo['index'])
            continue

        logging.info(f"\n[{idx}/{len(new_photos)}] 下载: {photo['filename']}")
        success = downloader.download_photo(photo['url'], photo['filename'])

        if success:
            history.add_downloaded(photo['filename'])
            success_count += 1

        # 更新已处理的索引（无论下载成功与否）
        history.update_processed_index(photo['index'])

    # 4. 保存历史记录
    history.save_history()
    logging.info(f"\n✓ 本次下载完成，成功 {success_count}/{len(new_photos)} 张照片")
    logging.info(f"已处理到第 {history.last_processed_index} 张照片")
else:
    logging.info("\n没有新照片需要下载")
```

**新代码:**
```python
# 2. 快速扫描所有照片指纹（无点击开销）
logging.info("\n正在扫描照片指纹...")
all_fingerprints = await extractor.extract_fingerprints_fast(page)
total_count = len(all_fingerprints)
logging.info(f"✓ 扫描完成，发现 {total_count} 张照片")

# 3. 识别未下载的照片
unknown_items = [
    item for item in all_fingerprints
    if not history.is_downloaded_by_fingerprint(item['fingerprint'])
]
new_count = len(unknown_items)
downloaded_count = total_count - new_count

logging.info(f"  - 已下载: {downloaded_count} 张")
logging.info(f"  - 新照片: {new_count} 张")

# 4. 仅对新照片获取原图URL并下载
if new_count > 0:
    logging.info(f"\n开始下载 {new_count} 张新照片...")

    # 获取新照片的原图URL
    new_photos = await extractor.extract_photo_urls_by_fingerprints(
        page,
        [item['fingerprint'] for item in unknown_items]
    )

    success_count = 0
    for idx, photo in enumerate(new_photos, 1):
        logging.info(f"\n[{idx}/{new_count}] 下载: {photo['filename']}")

        # 下载照片
        success = downloader.download_photo(photo['url'], photo['filename'])

        if success:
            # 记录下载信息（指纹+原图文件名+缩略图URL）
            history.add_download_record(
                fingerprint=photo['fingerprint'],
                original_filename=photo['filename'],
                thumbnail_url=photo['thumbnail_url']
            )
            success_count += 1

    # 5. 保存历史记录
    history.save_history()
    logging.info(f"\n✓ 本次下载完成，成功 {success_count}/{new_count} 张照片")
else:
    logging.info("\n没有新照片需要下载")
```

**日志输出示例：**
```
正在扫描照片指纹...
✓ 扫描完成，发现 100 张照片
  - 已下载: 80 张
  - 新照片: 20 张

开始下载 20 张新照片...

[1/20] 下载: 9T1A3143.JPG
✓ 下载成功: 9T1A3143.JPG

[2/20] 下载: 9T1A3144.JPG
✓ 下载成功: 9T1A3144.JPG
...
```

---

### 阶段4: 配置与日志优化

#### 4.1 添加调试配置

**文件：** `config.py` (第33行之后)

**新增内容：**
```python
# ============ 指纹提取配置 ============
# 是否启用详细的指纹提取日志（调试用）
DEBUG_FINGERPRINT_EXTRACTION = False
# 启用后会输出每张照片的指纹提取详情
```

**使用示例：**
```python
if DEBUG_FINGERPRINT_EXTRACTION:
    logging.debug(f"照片 #{idx} 指纹: {fingerprint} (来源: {thumbnail_url})")
```

#### 4.2 日志输出优化

**优化点：**
1. 删除所有 `last_processed_index` 相关日志
2. 新增指纹扫描进度提示
3. 区分"扫描阶段"和"下载阶段"

**修改位置：**
- `photo_downloader.py:344-346` (启动信息)
- `photo_downloader.py:418` (完成信息)

---

### 阶段5: 降级机制与容错

#### 5.1 缩略图URL不可用时的降级处理

**场景：**
- 网站DOM结构变化，缩略图URL不可用
- 照片元素缺少img标签

**降级策略：**
1. 第一次尝试失败 → 警告日志，使用时间戳+索引生成临时指纹
2. 临时指纹格式: `fallback_{timestamp}_{index}`
3. 所有照片使用临时指纹 → 退化为方案1（全量点击）

**实现位置：** `PhotoExtractor._extract_filename_from_thumbnail()`

```python
def _extract_filename_from_thumbnail(self, url: str, fallback_index: int = None) -> str:
    """提取指纹，失败时使用降级方案"""
    try:
        if not url:
            raise ValueError("URL为空")

        # 正常提取逻辑
        if url.startswith('//'):
            url = 'https:' + url

        path = url.split('?')[0]
        filename_with_cdn = path.split('/')[-1]

        if '~' in filename_with_cdn:
            filename = filename_with_cdn.split('~')[0]
        else:
            filename = filename_with_cdn

        if not filename:
            raise ValueError("提取的文件名为空")

        return filename

    except Exception as e:
        logging.warning(f"缩略图URL提取失败: {e}，使用降级指纹")

        # 降级方案
        if fallback_index is not None:
            return f"fallback_{int(time.time())}_{fallback_index}"
        return f"fallback_{int(time.time())}_{random.randint(1000, 9999)}"
```

**降级日志示例：**
```
[WARNING] 缩略图URL提取失败: URL为空，使用降级指纹
[INFO] 降级到全量点击模式，性能将受影响
```

---

### 阶段6: 测试验证计划

#### 6.1 数据迁移测试

**测试步骤：**
1. 备份当前 `downloaded.json` → `downloaded.json.backup`
2. 运行新版本程序
3. 检查日志是否显示迁移信息
4. 验证新 `downloaded.json` 格式

**预期输出：**
```
[INFO] 检测到旧格式数据，正在迁移...
[INFO] ✓ 迁移 5 条历史记录
[INFO] ✓ 数据迁移完成
```

**验证点：**
- [ ] 新JSON包含 `version: "2.0"`
- [ ] 所有旧文件名都在 `downloads` 中
- [ ] 指纹格式为 `migrated_{原文件名}`

#### 6.2 新照片检测测试

**测试步骤：**
1. 清空 `downloaded.json` 和 `photos/` 目录
2. 运行程序，等待下载完成（假设下载5张）
3. 等待网站新增照片（或手动模拟）
4. 再次运行程序

**预期输出：**
```
第1次运行:
扫描到 5 张照片
  - 已下载: 0 张
  - 新照片: 5 张
开始下载 5 张新照片...
✓ 本次下载完成，成功 5/5 张照片

第2次运行（新增2张照片）:
扫描到 7 张照片
  - 已下载: 5 张
  - 新照片: 2 张
开始下载 2 张新照片...
✓ 本次下载完成，成功 2/2 张照片
```

**验证点：**
- [ ] 第2次运行点击次数 = 2次（仅新照片）
- [ ] 日志显示已下载数量正确
- [ ] `photos/` 目录包含7张照片

#### 6.3 照片插入/删除场景测试

**测试场景1: 中间插入**
1. 下载照片 A, B, C, D, E（列表：[A, B, C, D, E]）
2. 网站在B和C之间插入照片X, Y（列表：[A, B, X, Y, C, D, E]）
3. 运行程序

**预期结果：**
- 扫描到7张照片，5张已下载，2张新照片
- 仅下载X, Y
- A, B, C, D, E不重复下载

**测试场景2: 列表重排**
1. 下载照片 A, B, C（列表：[A, B, C]）
2. 网站按时间倒序排列（列表：[C, B, A]）
3. 运行程序

**预期结果：**
- 扫描到3张照片，3张已下载，0张新照片
- 无任何下载操作

**验证点：**
- [ ] 无论顺序如何，指纹匹配正确
- [ ] 无重复下载
- [ ] 无漏下载

---

## 实施时间估算

| 阶段 | 预估时间 |
|-----|---------|
| 阶段1: 数据结构设计与迁移 | 30分钟 |
| 阶段2: 核心类重构 | 60分钟 |
| 阶段3: 主流程改造 | 30分钟 |
| 阶段4: 配置与日志优化 | 15分钟 |
| 阶段5: 降级机制 | 20分钟 |
| 阶段6: 测试验证 | 30分钟 |
| **总计** | **~3小时** |

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|-----|------|------|---------|
| 缩略图URL格式变化 | 低 | 高 | 降级到全量点击模式 |
| 数据迁移失败 | 低 | 中 | 自动备份旧数据，失败时恢复 |
| 新逻辑引入bug | 中 | 中 | 完善测试用例，分阶段验证 |
| 性能不及预期 | 低 | 低 | 已通过DOM分析验证可行性 |

---

## 成功标准

✅ **功能完整性：**
- 所有新照片都能被检测并下载
- 已下载照片不会重复下载
- 照片插入/删除/重排不影响去重准确性

✅ **性能指标：**
- 100张照片扫描时间 < 5秒
- 已下载照片无点击开销
- 总体性能提升 > 70%

✅ **兼容性：**
- 旧数据自动迁移无损
- 降级机制保证鲁棒性

---

## 实施后验证清单

- [ ] 数据迁移测试通过
- [ ] 新照片检测测试通过
- [ ] 照片插入场景测试通过
- [ ] 照片重排场景测试通过
- [ ] 性能指标达标
- [ ] 降级机制验证通过
- [ ] 日志输出清晰准确
- [ ] 无已知bug

---

**计划创建时间：** 2025-11-17
**计划状态：** 待用户批准
