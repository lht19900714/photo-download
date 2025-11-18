"""配置文件（支持环境变量覆盖，适合服务器部署）"""

import os


def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# 目标网站（通常由前端在启动任务时注入）
TARGET_URL = os.getenv("TARGET_URL", "")

# 检查间隔（秒，前端启动前填写）
CHECK_INTERVAL = _as_int(os.getenv("CHECK_INTERVAL"), 60)

# 存储路径
PHOTO_DIR = os.getenv("PHOTO_DIR", "./photos")
DOWNLOADED_HISTORY = os.getenv("DOWNLOADED_HISTORY", "./downloaded.json")

# 错误处理
MAX_CONNECTION_FAILURES = _as_int(os.getenv("MAX_CONNECTION_FAILURES"), 10)
MAX_DOWNLOAD_RETRIES = _as_int(os.getenv("MAX_DOWNLOAD_RETRIES"), 5)

# Playwright配置
HEADLESS = _as_bool(os.getenv("HEADLESS"), True)
TIMEOUT = _as_int(os.getenv("TIMEOUT"), 30000)  # 毫秒
SCROLL_PAUSE_TIME = _as_int(os.getenv("SCROLL_PAUSE_TIME"), 2)  # 秒
MAX_SCROLL_ATTEMPTS = _as_int(os.getenv("MAX_SCROLL_ATTEMPTS"), 50)

# 等待时间配置（毫秒）
PHOTO_DETAIL_LOAD_WAIT = _as_int(os.getenv("PHOTO_DETAIL_LOAD_WAIT"), 1000)
PHOTO_CLOSE_WAIT = _as_int(os.getenv("PHOTO_CLOSE_WAIT"), 500)
PAGE_RENDER_WAIT = _as_int(os.getenv("PAGE_RENDER_WAIT"), 3000)

# DOM选择器
PHOTO_ITEM_SELECTOR = os.getenv("PHOTO_ITEM_SELECTOR", "div.photo-content.container li.photo-item")
PHOTO_CLICK_SELECTOR = os.getenv("PHOTO_CLICK_SELECTOR", "span")  # li.photo-item内的span元素
VIEW_ORIGINAL_SELECTOR = os.getenv("VIEW_ORIGINAL_SELECTOR", "div.operate-buttons li.row-all-center a")

# ============ 数据管理配置 ============
# 是否为全新页面（清除所有历史数据）
# ⚠️ 设置为 True 将删除历史记录和已下载照片（不可恢复）
# 默认 False，避免服务器长跑时误删
FRESH_START = _as_bool(os.getenv("FRESH_START"), False)

# ============ 指纹提取配置 ============
DEBUG_FINGERPRINT_EXTRACTION = _as_bool(os.getenv("DEBUG_FINGERPRINT_EXTRACTION"), True)

# ============ Dropbox 云盘存储配置 ============
# Access Token（旧方式，4小时有效期）或 Refresh Token 模式三件套
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN", "")
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", "")
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY", "")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "")

# Dropbox 存储路径（前端启动前填写）
DROPBOX_SAVE_PATH = os.getenv("DROPBOX_SAVE_PATH", "")

# 是否同时保存到本地 photos/ 目录
SAVE_TO_LOCAL = _as_bool(os.getenv("SAVE_TO_LOCAL"), False)
