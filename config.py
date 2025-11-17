"""配置文件"""

# 目标网站
TARGET_URL = "https://live.photoplus.cn/live/pc/93374906/#/live"  # https://live.photoplus.cn/live/1239677?accessFrom=live#/live

# 检查间隔（秒）
CHECK_INTERVAL = 20  # 2分钟

# 存储路径
PHOTO_DIR = "./photos"
DOWNLOADED_HISTORY = "./downloaded.json"

# 错误处理
MAX_CONNECTION_FAILURES = 10  # 连接失败上限
MAX_DOWNLOAD_RETRIES = 5      # 单张照片下载重试次数

# Playwright配置
HEADLESS = True               # 无头模式
TIMEOUT = 30000               # 30秒超时（毫秒）
SCROLL_PAUSE_TIME = 2         # 滚动后等待时间（秒）
MAX_SCROLL_ATTEMPTS = 50      # 最大滚动次数（防止无限循环）

# 等待时间配置（毫秒）
PHOTO_DETAIL_LOAD_WAIT = 1000  # 照片详情加载等待
PHOTO_CLOSE_WAIT = 500         # 关闭详情等待
PAGE_RENDER_WAIT = 3000        # 页面初始渲染等待

# DOM选择器
PHOTO_ITEM_SELECTOR = "div.photo-content.container li.photo-item"
PHOTO_CLICK_SELECTOR = "span"  # li.photo-item内的span元素
VIEW_ORIGINAL_SELECTOR = "div.operate-buttons li.row-all-center a"

# ============ 数据管理配置 ============
# 是否为全新页面（清除所有历史数据）
# ⚠️  警告: 设置为 True 将删除所有历史记录和已下载照片（不可恢复）
# ⚠️  仅在需要重新下载全新页面时才设置为 True
# True: 删除 downloaded.json 和 photos/ 目录下所有照片
# False: 继续使用现有历史记录（默认）
FRESH_START = True

# ============ 指纹提取配置 ============
# 是否启用详细的指纹提取日志（调试用）
# True: 输出每张照片的指纹提取详情
# False: 仅输出汇总信息（默认）
DEBUG_FINGERPRINT_EXTRACTION = True

# ============ Dropbox 云盘存储配置 ============
# Dropbox 访问令牌配置说明：
# 1. 访问 https://www.dropbox.com/developers/apps 创建应用
# 2. 在应用设置中生成 Access Token
# 3. 将生成的 Token 填入下方 DROPBOX_ACCESS_TOKEN
# 4. 配置云盘存储路径 DROPBOX_SAVE_PATH（路径会自动创建）
# 5. 根据需求设置 SAVE_TO_LOCAL 控制是否同时保存本地副本
#
# ⚠️  安全提示：请勿将包含 Token 的配置文件提交到公开代码仓库

# Dropbox 访问令牌（留空则禁用 Dropbox 功能，仅本地下载）
DROPBOX_ACCESS_TOKEN = ""

# Dropbox 存储路径（云盘中的目录路径，会自动创建）
DROPBOX_SAVE_PATH = "/PhotoPlus/photos"

# 是否同时保存到本地 photos/ 目录
# True: 同时保存到 Dropbox 和本地（双重备份）
# False: 仅保存到 Dropbox（节省本地空间）
SAVE_TO_LOCAL = False
