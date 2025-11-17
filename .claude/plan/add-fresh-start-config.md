# 任务执行计划：添加 FRESH_START 配置选项

## 📋 任务信息

- **任务名称**: 添加系统启动时清除历史数据的配置选项
- **创建时间**: 2025-11-16
- **执行状态**: ✅ 已完成

---

## 🎯 需求上下文

### 用户需求

在系统启动时增加一个配置选项 flag，这个 flag 如果是 true，代表此次运行的是一个新的页面，所以所有的历史记录都需要清除，包括所有的下载的照片都要清除。如果 flag 是 false 或者没有设置，则说明这是继续运行之前的页面。

### 需求细化（通过问答确认）

1. **配置方式**: 通过配置文件 `config.py` 设置
2. **安全确认**: 不需要二次确认提示，直接执行
3. **错误处理**: 清理失败则终止程序并显示错误信息

### 需求完整性评分

- **目标清晰度**: 3/3 分 - 目标明确
- **预期结果**: 3/3 分 - 结果明确
- **范围边界**: 2/2 分 - 范围清晰
- **约束条件**: 2/2 分 - 约束明确

**总分**: 10/10 - 需求完整

---

## 💡 方案设计

### 方案对比

#### 方案 1: 主函数内联清理逻辑
- ❌ 违反单一职责原则
- ❌ 代码可读性差
- ❌ 不易测试

#### 方案 2: 独立初始化函数 + 配置驱动（已采用）
- ✅ 符合 SOLID、KISS 原则
- ✅ 职责单一，逻辑清晰
- ✅ 易于测试和维护
- ✅ 错误处理集中

#### 方案 3: DownloadHistory 类内部处理
- ❌ 违反单一职责原则
- ❌ 增加类耦合度
- ❌ 初始化有副作用

### 最终方案

采用**方案 2**，新增独立的 `initialize_environment()` 函数，在 `main()` 函数开始处调用。

---

## 📐 详细执行步骤

### 步骤 1: 在 config.py 中添加 FRESH_START 配置项

**文件**: `config.py`

**修改内容**:
```python
# ============ 数据管理配置 ============
# 是否为全新页面（清除所有历史数据）
# ⚠️  警告: 设置为 True 将删除所有历史记录和已下载照片（不可恢复）
# ⚠️  仅在需要重新下载全新页面时才设置为 True
# True: 删除 downloaded.json 和 photos/ 目录下所有照片
# False: 继续使用现有历史记录（默认）
FRESH_START = False
```

**预期结果**: ✅ 配置项添加成功，默认值为 False

---

### 步骤 2: 在 photo_downloader.py 中导入 sys 模块

**文件**: `photo_downloader.py`

**修改内容**: 在导入语句中添加 `sys`
```python
import sys
```

**预期结果**: ✅ sys 模块导入成功

---

### 步骤 3: 在 photo_downloader.py 中导入 FRESH_START 配置

**文件**: `photo_downloader.py`

**修改内容**: 在 `from config import` 语句中添加 `FRESH_START`

**预期结果**: ✅ FRESH_START 配置导入成功

---

### 步骤 4: 新增 initialize_environment() 函数

**文件**: `photo_downloader.py`

**位置**: 在 `main()` 函数之前（第 275 行）

**功能实现**:
```python
def initialize_environment() -> None:
    """
    系统环境初始化

    根据 config.FRESH_START 配置决定是否清除历史数据:
    - True: 删除 downloaded.json 和 photos/ 目录下所有照片文件
    - False: 保持现有数据不变

    Raises:
        SystemExit: 清理失败时终止程序（退出码 1）
    """
    if not FRESH_START:
        logging.info("继续使用现有历史记录")
        return

    logging.info("⚠️  FRESH_START 模式已启用，开始清理历史数据...")

    try:
        # 1. 删除历史记录文件
        if os.path.exists(DOWNLOADED_HISTORY):
            os.remove(DOWNLOADED_HISTORY)
            logging.info(f"✓ 已删除历史记录文件: {DOWNLOADED_HISTORY}")
        else:
            logging.info(f"- 历史记录文件不存在，跳过: {DOWNLOADED_HISTORY}")

        # 2. 删除 photos 目录下所有照片文件
        if os.path.exists(PHOTO_DIR):
            deleted_count = 0
            for filename in os.listdir(PHOTO_DIR):
                file_path = os.path.join(PHOTO_DIR, filename)
                # 只删除文件，保留子目录
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            logging.info(f"✓ 已删除 {deleted_count} 张历史照片")
        else:
            logging.info(f"- 照片目录不存在，跳过: {PHOTO_DIR}")

        logging.info("✅ 历史数据清理完成，将从全新状态启动")

    except PermissionError as e:
        logging.error(f"❌ 清理失败: 文件权限不足 - {e}")
        sys.exit(1)
    except OSError as e:
        logging.error(f"❌ 清理失败: 文件系统错误 - {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ 清理失败: 未知错误 - {e}")
        sys.exit(1)
```

**预期结果**: ✅ 函数添加成功，包含完整错误处理

---

### 步骤 5: 在 main() 函数中调用 initialize_environment()

**文件**: `photo_downloader.py`

**位置**: `main()` 函数开始处

**修改内容**:
```python
async def main():
    """主程序循环"""

    # 系统环境初始化（根据配置决定是否清除历史数据）
    initialize_environment()

    # 初始化组件
    history = DownloadHistory(DOWNLOADED_HISTORY)
    # ... 原有代码
```

**预期结果**: ✅ 调用添加成功，在组件初始化之前执行

---

## 🧪 测试计划

### 测试场景 1: FRESH_START = False（默认行为）

**前置条件**:
- `downloaded.json` 存在
- `photos/` 目录包含照片文件

**执行命令**:
```bash
uv run python photo_downloader.py
```

**预期输出**:
```
继续使用现有历史记录
```

**预期结果**:
- ✅ 历史记录保持不变
- ✅ 照片文件保持不变
- ✅ 程序从上次位置继续

---

### 测试场景 2: FRESH_START = True（清理模式）

**配置修改**:
```python
# config.py
FRESH_START = True
```

**执行命令**:
```bash
uv run python photo_downloader.py
```

**预期输出**:
```
⚠️  FRESH_START 模式已启用，开始清理历史数据...
✓ 已删除历史记录文件: ./downloaded.json
✓ 已删除 X 张历史照片
✅ 历史数据清理完成，将从全新状态启动
```

**预期结果**:
- ✅ `downloaded.json` 被删除
- ✅ `photos/` 目录清空
- ✅ 程序从第 0 张照片开始提取

---

### 测试场景 3: 清理失败（权限错误）

**模拟条件**:
```bash
chmod 444 downloaded.json  # 设置为只读
```

**预期输出**:
```
❌ 清理失败: 文件权限不足 - [PermissionError: ...]
```

**预期结果**:
- ✅ 程序立即终止，退出码为 1
- ✅ 不执行后续逻辑

---

## 📊 代码质量检查

- ✅ **KISS 原则**: 实现简单直接
- ✅ **YAGNI 原则**: 仅实现需求功能
- ✅ **DRY 原则**: 无重复代码
- ✅ **单一职责**: 函数职责明确
- ✅ **错误处理**: 三层异常捕获
- ✅ **日志完整**: 关键操作有日志
- ✅ **向后兼容**: 现有代码零修改
- ✅ **安全默认值**: FRESH_START = False

---

## 📝 修改文件清单

| 文件 | 修改类型 | 行数变化 |
|------|---------|---------|
| `config.py` | 新增配置 | +7 行 |
| `photo_downloader.py` | 导入 sys | +1 行 |
| `photo_downloader.py` | 导入 FRESH_START | +1 行 |
| `photo_downloader.py` | 新增函数 | +49 行 |
| `photo_downloader.py` | 调用函数 | +2 行 |

**总计**: 2 个文件，+60 行代码

---

## ⚠️ 风险提示

1. **数据不可恢复**: `FRESH_START = True` 后，历史数据和照片将被永久删除
2. **配置误操作**: 建议在修改配置前仔细检查
3. **文件权限**: 需要对 `downloaded.json` 和 `photos/` 目录有写权限

---

## ✅ 执行结果

所有步骤已成功执行，功能实现完成。

### 验证检查

- ✅ 配置项添加成功
- ✅ 导入语句正确
- ✅ 初始化函数实现完整
- ✅ main() 函数调用正确
- ✅ 错误处理完善
- ✅ 日志输出合理
- ✅ 代码符合最佳实践

---

## 📚 使用说明

### 启用全新页面模式

1. 编辑 `config.py` 文件
2. 将 `FRESH_START = False` 改为 `FRESH_START = True`
3. 运行程序: `uv run python photo_downloader.py`
4. 程序将清除所有历史数据并从头开始下载

### 恢复默认模式

1. 编辑 `config.py` 文件
2. 将 `FRESH_START = True` 改为 `FRESH_START = False`
3. 运行程序，将继续使用历史记录

---

**任务完成时间**: 2025-11-16
**执行状态**: ✅ 成功
