"""PhotoPlus 直播照片自动下载工具"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Optional

import requests
from playwright.async_api import async_playwright, Page

try:
    import dropbox
    import dropbox.exceptions
    DROPBOX_AVAILABLE = True
except ImportError:
    DROPBOX_AVAILABLE = False
    logging.warning("Dropbox SDK未安装，Dropbox功能将不可用")

from config import (
    TARGET_URL,
    CHECK_INTERVAL,
    PHOTO_DIR,
    DOWNLOADED_HISTORY,
    MAX_CONNECTION_FAILURES,
    MAX_DOWNLOAD_RETRIES,
    HEADLESS,
    TIMEOUT,
    SCROLL_PAUSE_TIME,
    MAX_SCROLL_ATTEMPTS,
    PHOTO_DETAIL_LOAD_WAIT,
    PHOTO_CLOSE_WAIT,
    PAGE_RENDER_WAIT,
    PHOTO_ITEM_SELECTOR,
    PHOTO_CLICK_SELECTOR,
    VIEW_ORIGINAL_SELECTOR,
    FRESH_START,
    DEBUG_FINGERPRINT_EXTRACTION,
    DROPBOX_ACCESS_TOKEN,
    DROPBOX_SAVE_PATH,
    SAVE_TO_LOCAL,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 常量
SEPARATOR = "=" * 60


# ============ Dropbox 辅助函数 ============

def init_dropbox_client(access_token: str = None,
                        refresh_token: str = None,
                        app_key: str = None,
                        app_secret: str = None) -> Optional[object]:
    """
    初始化 Dropbox 客户端，支持两种认证方式

    方式 1（推荐）：使用 Refresh Token（适合长期运行）
        - refresh_token: Dropbox Refresh Token
        - app_key: Dropbox App Key
        - app_secret: Dropbox App Secret

    方式 2（旧方式）：使用 Access Token（4小时有效期）
        - access_token: Dropbox Access Token

    Args:
        access_token: Dropbox 访问令牌（旧方式，可选）
        refresh_token: Dropbox 刷新令牌（新方式，推荐）
        app_key: Dropbox App Key（新方式需要）
        app_secret: Dropbox App Secret（新方式需要）

    Returns:
        Dropbox 客户端实例，如果初始化失败则返回 None
    """
    if not DROPBOX_AVAILABLE:
        logging.error("Dropbox SDK 未安装，无法使用 Dropbox 功能")
        logging.error("请运行: uv add dropbox")
        return None

    # 优先使用 Refresh Token（推荐方式）
    if refresh_token and app_key and app_secret:
        logging.info("📋 使用 Refresh Token 认证（推荐方式）")
        try:
            client = dropbox.Dropbox(
                oauth2_refresh_token=refresh_token,
                app_key=app_key,
                app_secret=app_secret
            )
            # 验证 Token 有效性
            account = client.users_get_current_account()
            logging.info(f"✅ Dropbox 认证成功: {account.name.display_name}")
            return client
        except dropbox.exceptions.AuthError as e:
            logging.error(f"Dropbox Refresh Token 认证失败: {e}")
            logging.error("请检查 DROPBOX_REFRESH_TOKEN、DROPBOX_APP_KEY 和 DROPBOX_APP_SECRET 配置")
            return None
        except Exception as e:
            logging.error(f"Dropbox 客户端初始化失败: {e}")
            return None

    # 降级使用 Access Token（旧方式，4小时有效期）
    elif access_token:
        logging.warning("⚠️ 使用 Access Token 认证（4小时有效期，不推荐）")
        logging.warning("⚠️ 建议切换到 Refresh Token 以支持长期运行")
        try:
            client = dropbox.Dropbox(access_token)
            # 验证 Token 有效性
            account = client.users_get_current_account()
            logging.info(f"✅ Dropbox 认证成功: {account.name.display_name}")
            return client
        except dropbox.exceptions.AuthError as e:
            logging.error(f"Dropbox 认证失败: {e}")
            logging.error("请检查 DROPBOX_ACCESS_TOKEN 配置是否正确")
            logging.error("如果 Token 已过期（4小时），请切换到 Refresh Token 方式")
            return None
        except Exception as e:
            logging.error(f"Dropbox 客户端初始化失败: {e}")
            return None

    else:
        logging.info("ℹ️ 未配置 Dropbox 认证信息，跳过 Dropbox 功能")
        return None


def ensure_dropbox_path(client: object, path: str) -> bool:
    """
    确保 Dropbox 路径存在，不存在则创建

    Args:
        client: Dropbox 客户端实例
        path: Dropbox 路径（如 /PhotoPlus/photos）

    Returns:
        True 表示路径可用，False 表示路径创建失败
    """
    if not client:
        return False

    try:
        # 尝试获取路径元数据
        client.files_get_metadata(path)
        logging.info(f"Dropbox 路径已存在: {path}")
        return True
    except dropbox.exceptions.ApiError as e:
        # 路径不存在，尝试创建
        if isinstance(e.error, dropbox.files.GetMetadataError):
            try:
                client.files_create_folder_v2(path)
                logging.info(f"✓ 已创建 Dropbox 目录: {path}")
                return True
            except dropbox.exceptions.ApiError as create_error:
                logging.error(f"创建 Dropbox 目录失败: {create_error}")
                return False
        else:
            logging.error(f"检查 Dropbox 路径失败: {e}")
            return False
    except Exception as e:
        logging.error(f"Dropbox 路径操作失败: {e}")
        return False


class DownloadHistory:
    """
    管理已下载文件记录 (v2.0 - 基于指纹去重)

    数据格式:
    {
        "version": "2.0",
        "downloads": {
            "指纹(缩略图文件名)": {
                "original_filename": "原图文件名.jpg",
                "thumbnail_url": "缩略图URL",
                "download_time": "2025-11-17 10:30:00"
            },
            ...
        },
        "last_update": "2025-11-17 10:30:00"
    }
    """

    def __init__(self, history_file: str):
        self.history_file = history_file
        self.version: str = "2.0"
        self.downloads: Dict[str, Dict] = {}  # 指纹 -> 下载信息映射
        self._load_history()

    def _load_history(self):
        """从JSON文件加载历史记录（仅支持v2.0格式）"""
        if not os.path.exists(self.history_file):
            logging.info("历史记录文件不存在，将创建新文件")
            return

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查版本
            version = data.get('version', 'unknown')
            if version != '2.0':
                logging.warning(f"不兼容的数据格式版本: {version}，将创建新的历史记录")
                self.downloads = {}
                return

            # 加载v2.0格式数据
            self.downloads = data.get('downloads', {})
            logging.info(f"已加载 {len(self.downloads)} 条历史记录")

        except Exception as e:
            logging.warning(f"加载历史记录失败: {e}，将创建新的历史记录")
            self.downloads = {}

    def save_history(self):
        """保存历史记录到JSON文件（v2.0格式）"""
        try:
            data = {
                'version': self.version,
                'downloads': self.downloads,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存历史记录失败: {e}")

    def is_downloaded_by_fingerprint(self, fingerprint: str) -> bool:
        """检查指纹是否已下载"""
        return fingerprint in self.downloads

    def add_download_record(self, fingerprint: str, original_filename: str, thumbnail_url: str):
        """
        添加新下载记录

        Args:
            fingerprint: 照片指纹（缩略图文件名）
            original_filename: 原图文件名（保存到photos/的文件名）
            thumbnail_url: 缩略图URL
        """
        self.downloads[fingerprint] = {
            "original_filename": original_filename,
            "thumbnail_url": thumbnail_url,
            "download_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


async def scroll_to_load_all(page: Page):
    """滚动照片容器直到所有照片加载完成"""
    logging.info("开始滚动加载所有照片...")

    # 获取照片容器元素
    container_selector = "div.photo-content.container"
    container = page.locator(container_selector).first

    # 等待容器加载
    await container.wait_for(timeout=10000)

    # 改用照片元素数量判断
    last_photo_count = 0
    scroll_count = 0
    no_change_count = 0  # 连续未变化次数

    while scroll_count < MAX_SCROLL_ATTEMPTS:
        # 滚动容器到底部（而不是整个页面）
        await container.evaluate("""
            (element) => {
                element.scrollTop = element.scrollHeight;
            }
        """)
        scroll_count += 1

        # 等待内容加载
        await asyncio.sleep(SCROLL_PAUSE_TIME)

        # 检查照片元素数量
        current_photo_count = await page.locator(PHOTO_ITEM_SELECTOR).count()

        if current_photo_count > last_photo_count:
            # 有新照片加载
            logging.info(f"滚动中... ({scroll_count} 次) - 当前 {current_photo_count} 张照片")
            last_photo_count = current_photo_count
            no_change_count = 0
        else:
            # 照片数量未变化
            no_change_count += 1
            logging.info(f"滚动中... ({scroll_count} 次) - 照片数量未变化 ({no_change_count}/3)")

            # 连续3次未变化则认为加载完成
            if no_change_count >= 3:
                logging.info(f"✓ 滚动完成，共滚动 {scroll_count} 次，总计 {current_photo_count} 张照片")
                break

    if scroll_count >= MAX_SCROLL_ATTEMPTS:
        logging.warning(f"达到最大滚动次数 {MAX_SCROLL_ATTEMPTS}，停止滚动（当前 {last_photo_count} 张照片）")


class PhotoExtractor:
    """提取页面上所有照片的原图URL（基于指纹去重）"""

    def _extract_filename_from_thumbnail(self, url: str, fallback_index: int = None) -> str:
        """
        从缩略图URL提取文件名作为指纹

        Args:
            url: 缩略图URL (例如: //pb.plusx.cn/plus/immediate/35272685/2025111623814917/1060536x354blur2.jpg~tplv-...)
            fallback_index: 降级时使用的索引（可选）

        Returns:
            文件名指纹 (例如: "1060536x354blur2.jpg")
        """
        try:
            if not url:
                raise ValueError("URL为空")

            # 修复相对协议URL
            if url.startswith('//'):
                url = 'https:' + url

            # 去除query参数
            path = url.split('?')[0]

            # 先去除CDN后缀（~之后的所有内容），再提取文件名
            # URL格式: //pb.plusx.cn/.../filename.jpg~tplv-.../wst/3:480:1000:gif.avif
            # 必须先按~分割，否则会错误提取到水印参数部分
            if '~' in path:
                path = path.split('~')[0]

            # 提取路径最后一段（真正的文件名）
            filename = path.split('/')[-1]

            if not filename:
                raise ValueError("提取的文件名为空")

            return filename

        except Exception as e:
            logging.warning(f"缩略图URL提取失败: {e}，使用降级指纹")
            # 降级方案：使用时间戳+索引
            import random
            if fallback_index is not None:
                return f"fallback_{int(time.time())}_{fallback_index}"
            return f"fallback_{int(time.time())}_{random.randint(1000, 9999)}"

    async def extract_fingerprints_fast(self, page: Page) -> List[Dict[str, str]]:
        """
        快速提取所有照片的指纹（无需点击）

        Returns:
            [
                {
                    "index": 0,
                    "fingerprint": "1060536x354blur2.jpg",
                    "thumbnail_url": "//pb.plusx.cn/.../1060536x354blur2.jpg~..."
                },
                ...
            ]
        """
        # 1. 滚动加载所有照片
        await scroll_to_load_all(page)

        # 2. 获取所有照片元素
        photo_items = await page.locator(PHOTO_ITEM_SELECTOR).all()
        total_count = len(photo_items)

        logging.info(f"开始快速扫描 {total_count} 张照片的指纹...")

        fingerprints = []

        # 3. 逐个读取缩略图URL并提取指纹
        for idx, photo_item in enumerate(photo_items):
            try:
                # 读取img元素的src属性（无需点击）
                img_elem = photo_item.locator("img").first
                thumbnail_url = await img_elem.get_attribute("src")

                if thumbnail_url:
                    # 提取指纹
                    fingerprint = self._extract_filename_from_thumbnail(thumbnail_url, fallback_index=idx)

                    fingerprints.append({
                        "index": idx,
                        "fingerprint": fingerprint,
                        "thumbnail_url": thumbnail_url
                    })

                    # 调试日志
                    if DEBUG_FINGERPRINT_EXTRACTION:
                        logging.debug(f"  照片 #{idx+1}: 指纹={fingerprint}, URL={thumbnail_url[:80]}...")
                else:
                    logging.warning(f"照片 #{idx+1} 缩略图URL为空，使用降级指纹")
                    fingerprint = self._extract_filename_from_thumbnail("", fallback_index=idx)
                    fingerprints.append({
                        "index": idx,
                        "fingerprint": fingerprint,
                        "thumbnail_url": ""
                    })

            except Exception as e:
                logging.warning(f"提取照片 #{idx+1} 指纹失败: {e}，使用降级指纹")
                fingerprint = self._extract_filename_from_thumbnail("", fallback_index=idx)
                fingerprints.append({
                    "index": idx,
                    "fingerprint": fingerprint,
                    "thumbnail_url": ""
                })

        logging.info(f"✓ 指纹扫描完成，共 {len(fingerprints)} 张照片")
        return fingerprints

    async def extract_photo_urls_by_fingerprints(
        self,
        page: Page,
        target_fingerprints: List[str]
    ) -> List[Dict[str, str]]:
        """
        仅对指定指纹的照片获取原图URL（按需点击）

        Args:
            page: Playwright页面对象
            target_fingerprints: 需要处理的指纹列表

        Returns:
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
        if not target_fingerprints:
            logging.info("目标指纹列表为空，无需提取")
            return []

        # 1. 获取所有照片元素（已通过滚动加载）
        photo_items = await page.locator(PHOTO_ITEM_SELECTOR).all()

        logging.info(f"开始获取 {len(target_fingerprints)} 张新照片的原图URL...")

        # 创建指纹集合用于快速查找
        target_set = set(target_fingerprints)
        photo_urls = []
        processed_count = 0

        # 2. 遍历所有照片元素，仅点击目标指纹的照片
        for idx, photo_item in enumerate(photo_items):
            try:
                # 读取缩略图URL并提取指纹
                img_elem = photo_item.locator("img").first
                thumbnail_url = await img_elem.get_attribute("src")
                fingerprint = self._extract_filename_from_thumbnail(thumbnail_url, fallback_index=idx)

                # 检查是否在目标列表中
                if fingerprint not in target_set:
                    continue  # 跳过已下载的照片（无需点击）

                processed_count += 1

                # 点击照片内的span元素打开详情
                span_elem = photo_item.locator(PHOTO_CLICK_SELECTOR).first
                await span_elem.click()

                # 等待详情加载
                await page.wait_for_timeout(PHOTO_DETAIL_LOAD_WAIT)

                # 定位view original链接
                link_elem = page.locator(VIEW_ORIGINAL_SELECTOR).first

                # 等待链接出现
                await link_elem.wait_for(timeout=5000)

                # 获取href属性
                original_url = await link_elem.get_attribute("href")

                if original_url:
                    # 修复相对协议URL（//开头的URL需要添加https:）
                    if original_url.startswith('//'):
                        original_url = 'https:' + original_url

                    # 从URL提取文件名
                    filename = self._extract_filename_from_url(original_url)
                    photo_urls.append({
                        'fingerprint': fingerprint,
                        'url': original_url,
                        'filename': filename,
                        'thumbnail_url': thumbnail_url or ""
                    })
                    logging.info(f"[{processed_count}/{len(target_fingerprints)}] 提取: {filename} (指纹: {fingerprint})")

                # 关闭详情（使用Escape键）
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(PHOTO_CLOSE_WAIT)

            except Exception as e:
                logging.warning(f"提取照片 #{idx+1} 失败: {e}")
                # 尝试关闭可能打开的详情
                try:
                    await page.keyboard.press("Escape")
                except Exception as close_error:
                    logging.debug(f"关闭详情失败（可忽略）: {close_error}")
                continue

        logging.info(f"✓ 原图URL提取完成，成功 {len(photo_urls)}/{len(target_fingerprints)} 张")
        return photo_urls

    def _extract_filename_from_url(self, url: str) -> str:
        """从URL提取文件名"""
        # 从URL中提取文件名，去除查询参数
        filename = url.split('/')[-1].split('?')[0]

        # 处理CDN处理后的文件名（如：9T1A3143.JPG~tplv-xxx.JPG）
        # 保留~之前的原始文件名
        if '~' in filename:
            filename = filename.split('~')[0]

        return filename


class PhotoDownloader:
    """下载照片（支持本地存储和 Dropbox 云盘）"""

    def __init__(self, photo_dir: str, dropbox_client: Optional[object] = None, dropbox_path: str = ""):
        """
        初始化下载器

        Args:
            photo_dir: 本地存储目录
            dropbox_client: Dropbox 客户端实例（可选）
            dropbox_path: Dropbox 存储路径（可选）
        """
        self.photo_dir = photo_dir
        self.dropbox_client = dropbox_client
        self.dropbox_path = dropbox_path

        # 创建本地照片目录（如果需要本地存储）
        if SAVE_TO_LOCAL:
            os.makedirs(photo_dir, exist_ok=True)

    def download_photo(self, url: str, filename: str) -> bool:
        """
        下载单张照片到内存，然后根据配置保存到 Dropbox 和/或本地

        Args:
            url: 照片 URL
            filename: 文件名

        Returns:
            True 表示下载成功，False 表示失败
        """
        photo_data = None

        # 1. 下载照片到内存
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            try:
                response = requests.get(url, timeout=30, stream=True)
                response.raise_for_status()

                # 下载到内存缓冲区
                photo_data = BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        photo_data.write(chunk)

                logging.info(f"✓ 下载到内存: {filename} ({photo_data.tell()} 字节)")
                break  # 下载成功，跳出重试循环

            except Exception as e:
                if attempt < MAX_DOWNLOAD_RETRIES:
                    logging.warning(
                        f"✗ 下载失败 (尝试 {attempt}/{MAX_DOWNLOAD_RETRIES}): {filename} - {e}"
                    )
                    time.sleep(2)
                else:
                    logging.error(f"✗ 下载失败已跳过: {filename} - {e}")
                    return False

        if not photo_data:
            return False

        # 2. 上传到 Dropbox（如果配置）
        if self.dropbox_client:
            upload_success = self._upload_to_dropbox(photo_data, filename)
            if not upload_success:
                logging.warning(f"Dropbox 上传失败: {filename}")
                return False  # 上传失败则跳过此照片

        # 3. 保存到本地（如果配置）
        if SAVE_TO_LOCAL:
            self._save_to_local(photo_data, filename)

        return True

    def _upload_to_dropbox(self, photo_data: BytesIO, filename: str) -> bool:
        """
        上传照片到 Dropbox，支持重试

        Args:
            photo_data: 照片数据（BytesIO 对象）
            filename: 文件名

        Returns:
            True 表示上传成功，False 表示失败
        """
        if not self.dropbox_client:
            return False

        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            try:
                # 重置指针到开头
                photo_data.seek(0)

                # 构建 Dropbox 文件路径
                dropbox_file_path = f"{self.dropbox_path}/{filename}"

                # 上传文件
                self.dropbox_client.files_upload(
                    photo_data.read(),
                    dropbox_file_path,
                    mode=dropbox.files.WriteMode.overwrite
                )

                logging.info(f"✓ 已上传到 Dropbox: {dropbox_file_path}")
                return True

            except Exception as e:
                if attempt < MAX_DOWNLOAD_RETRIES:
                    logging.warning(
                        f"✗ Dropbox 上传失败 (尝试 {attempt}/{MAX_DOWNLOAD_RETRIES}): {filename} - {e}"
                    )
                    time.sleep(2)
                else:
                    logging.error(f"✗ Dropbox 上传失败已跳过: {filename} - {e}")

        return False

    def _save_to_local(self, photo_data: BytesIO, filename: str) -> bool:
        """
        保存照片到本地文件系统

        Args:
            photo_data: 照片数据（BytesIO 对象）
            filename: 文件名

        Returns:
            True 表示保存成功，False 表示失败
        """
        try:
            # 重置指针到开头
            photo_data.seek(0)

            # 构建本地文件路径
            file_path = os.path.join(self.photo_dir, filename)

            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(photo_data.read())

            logging.info(f"✓ 已保存到本地: {file_path}")
            return True

        except Exception as e:
            logging.error(f"✗ 保存到本地失败: {filename} - {e}")
            return False


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


async def main():
    """主程序循环"""

    # 系统环境初始化（根据配置决定是否清除历史数据）
    initialize_environment()

    # 初始化 Dropbox 客户端
    dropbox_client = None
    if DROPBOX_ACCESS_TOKEN:
        logging.info("正在初始化 Dropbox 客户端...")
        dropbox_client = init_dropbox_client(DROPBOX_ACCESS_TOKEN)
        if dropbox_client:
            # 确保 Dropbox 路径存在
            path_ready = ensure_dropbox_path(dropbox_client, DROPBOX_SAVE_PATH)
            if not path_ready:
                logging.warning("Dropbox 路径初始化失败，将禁用 Dropbox 功能")
                dropbox_client = None
        else:
            logging.warning("Dropbox 客户端初始化失败，将仅使用本地存储")

    # 初始化组件
    history = DownloadHistory(DOWNLOADED_HISTORY)
    downloader = PhotoDownloader(
        PHOTO_DIR,
        dropbox_client=dropbox_client,
        dropbox_path=DROPBOX_SAVE_PATH
    )
    extractor = PhotoExtractor()

    connection_failures = 0

    # 打印启动信息
    logging.info(SEPARATOR)
    logging.info("PhotoPlus 照片自动下载工具启动 (v2.0 - 指纹去重)")
    logging.info(f"目标URL: {TARGET_URL}")
    logging.info(f"检查间隔: {CHECK_INTERVAL}秒")

    # 存储配置信息
    if dropbox_client:
        logging.info(f"Dropbox 存储: 已启用 → {DROPBOX_SAVE_PATH}")
        if SAVE_TO_LOCAL:
            logging.info(f"本地存储: 已启用 → {PHOTO_DIR}")
        else:
            logging.info(f"本地存储: 已禁用（仅保存到 Dropbox）")
    else:
        logging.info(f"Dropbox 存储: 未配置")
        logging.info(f"本地存储: {PHOTO_DIR}")

    logging.info(f"已加载历史记录: {len(history.downloads)} 张照片")
    logging.info(SEPARATOR)

    # 启动Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        # 禁用浏览器缓存，确保每次获取最新数据
        context = await browser.new_context(
            extra_http_headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
        page = await context.new_page()

        # 设置超时时间
        page.set_default_timeout(TIMEOUT)

        try:
            loop_count = 0  # 循环计数器
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

                    connection_failures = 0  # 重置失败计数
                    if loop_count == 1:
                        logging.info("✓ 页面首次加载成功")
                    else:
                        logging.info(f"✓ 页面刷新成功（第 {loop_count} 次循环）")

                    # 2. 快速扫描所有照片指纹（无点击开销）
                    logging.info("\n正在扫描照片指纹...")
                    all_fingerprints = await extractor.extract_fingerprints_fast(page)
                    total_count = len(all_fingerprints)

                    # 3. 识别未下载的照片
                    unknown_items = [
                        item for item in all_fingerprints
                        if not history.is_downloaded_by_fingerprint(item['fingerprint'])
                    ]
                    new_count = len(unknown_items)
                    downloaded_count = total_count - new_count

                    logging.info(f"\n扫描结果:")
                    logging.info(f"  - 总计: {total_count} 张照片")
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
                            success = downloader.download_photo(
                                photo['url'],
                                photo['filename']
                            )

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
                        logging.info(f"历史记录已更新: {len(history.downloads)} 张照片")
                    else:
                        logging.info("\n没有新照片需要下载")

                    # 6. 等待下一次检查
                    logging.info(f"\n等待 {CHECK_INTERVAL} 秒后进行下一次检查...")
                    logging.info(SEPARATOR)
                    await asyncio.sleep(CHECK_INTERVAL)

                except Exception as e:
                    connection_failures += 1
                    logging.error(
                        f"\n✗ 访问失败 ({connection_failures}/{MAX_CONNECTION_FAILURES}): {e}"
                    )

                    if connection_failures >= MAX_CONNECTION_FAILURES:
                        logging.error("连接失败次数达到上限，程序退出")
                        break

                    logging.info(f"等待10秒后重试...")
                    await asyncio.sleep(10)

        except KeyboardInterrupt:
            logging.info("\n\n收到中断信号，正在优雅退出...")

        finally:
            await browser.close()
            logging.info("程序已退出")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已终止")
