import asyncio
import logging
import os
import time
from typing import Optional

from playwright.async_api import async_playwright

from .config import (
    TARGET_URL,
    CHECK_INTERVAL,
    PHOTO_DIR,
    DOWNLOADED_HISTORY,
    MAX_CONNECTION_FAILURES,
    HEADLESS,
    TIMEOUT,
    PAGE_RENDER_WAIT,
    DROPBOX_ACCESS_TOKEN,
    DROPBOX_REFRESH_TOKEN,
    DROPBOX_APP_KEY,
    DROPBOX_APP_SECRET,
    DROPBOX_SAVE_PATH,
    SAVE_TO_LOCAL,
    FRESH_START,
)
from .photo_downloader import (
    DownloadHistory,
    PhotoExtractor,
    PhotoDownloader,
    init_dropbox_client,
    ensure_dropbox_path,
    SEPARATOR,
)
from .state import StateManager, now_iso


class Runner:
    """
    管理下载循环，可启动/停止/手动执行。
    """

    def __init__(self, state: StateManager):
        self.state = state
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._loop_index = 0
        self._cleared = False  # FRESH_START 仅首次生效
        self._lock = asyncio.Lock()
        self._active_config: Optional[dict] = None
        self._default_config = {
            "target_url": TARGET_URL,
            "check_interval": CHECK_INTERVAL,
            "dropbox_save_path": DROPBOX_SAVE_PATH,
        }

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def _current_config(self) -> dict:
        return self._active_config or self.state.load_runtime_config() or self._default_config

    async def start(self, config_override: Optional[dict] = None) -> bool:
        if self.is_running():
            return False
        if config_override:
            self._active_config = {
                "target_url": config_override.get("target_url", TARGET_URL),
                "check_interval": int(config_override.get("check_interval", CHECK_INTERVAL)),
                "dropbox_save_path": config_override.get("dropbox_save_path", DROPBOX_SAVE_PATH),
            }
            self.state.save_runtime_config(self._active_config)
        else:
            # 启动时如果没有新配置，尝试加载已有 runtime 配置，否则用默认
            self._active_config = self.state.load_runtime_config() or self._default_config

        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())
        return True

    async def stop(self) -> bool:
        if not self.is_running():
            self._active_config = None
            self.state.clear_runtime_config()
            return False
        self._stop_event.set()
        await self._task
        self._active_config = None
        self.state.clear_runtime_config()
        return True

    async def run_once(self, config_override: Optional[dict] = None) -> dict:
        if config_override:
            self._active_config = {
                "target_url": config_override.get("target_url", TARGET_URL),
                "check_interval": int(config_override.get("check_interval", CHECK_INTERVAL)),
                "dropbox_save_path": config_override.get("dropbox_save_path", DROPBOX_SAVE_PATH),
            }
        else:
            self._active_config = self.state.load_runtime_config() or self._default_config
        async with self._lock:
            return await self._run_cycle()

    async def _loop(self):
        logging.info("后台循环已启动")
        while not self._stop_event.is_set():
            async with self._lock:
                await self._run_cycle()

            # 等待检查间隔（可随时打断）
            interval = int(self._current_config().get("check_interval", CHECK_INTERVAL))
            for _ in range(interval):
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(1)
        logging.info("后台循环已停止")

    async def _run_cycle(self) -> dict:
        cfg = self._current_config()
        start_ts = time.time()
        self._loop_index += 1
        loop_id = self._loop_index
        result: dict = {
            "started_at": now_iso(),
            "ended_at": None,
            "duration_sec": None,
            "success": False,
            "loop_index": loop_id,
            "total_photos": 0,
            "new_photos": 0,
            "download_success": 0,
            "download_failed": 0,
            "dropbox_enabled": False,
            "dropbox_uploaded": 0,
            "dropbox_failed": 0,
            "history_size": 0,
            "last_error": None,
        }

        logging.info(SEPARATOR)
        logging.info("启动单轮扫描/下载")
        logging.info(f"目标URL: {cfg['target_url']}")
        logging.info(f"保存到本地: {PHOTO_DIR}（{'启用' if SAVE_TO_LOCAL else '关闭'}）")

        # FRESH_START: 仅第一次清理
        if FRESH_START and not self._cleared:
            self._cleared = True
            if os.path.exists(DOWNLOADED_HISTORY):
                try:
                    os.remove(DOWNLOADED_HISTORY)
                    logging.info("FRESH_START 已清理历史记录文件")
                except OSError as e:
                    logging.warning(f"清理历史记录失败: {e}")
            if SAVE_TO_LOCAL and os.path.exists(PHOTO_DIR):
                import shutil
                try:
                    shutil.rmtree(PHOTO_DIR)
                    logging.info("FRESH_START 已清理本地照片目录")
                except OSError as e:
                    logging.warning(f"清理照片目录失败: {e}")

        # 初始化历史与组件
        history = DownloadHistory(DOWNLOADED_HISTORY)
        extractor = PhotoExtractor()

        # Dropbox
        dropbox_client = None
        dropbox_path = cfg.get("dropbox_save_path", DROPBOX_SAVE_PATH)
        if DROPBOX_REFRESH_TOKEN and DROPBOX_APP_KEY and DROPBOX_APP_SECRET:
            logging.info("正在初始化 Dropbox (Refresh Token)...")
            dropbox_client = init_dropbox_client(
                refresh_token=DROPBOX_REFRESH_TOKEN,
                app_key=DROPBOX_APP_KEY,
                app_secret=DROPBOX_APP_SECRET,
            )
        elif DROPBOX_ACCESS_TOKEN:
            logging.info("正在初始化 Dropbox (Access Token)...")
            dropbox_client = init_dropbox_client(access_token=DROPBOX_ACCESS_TOKEN)

        if dropbox_client:
            ok = ensure_dropbox_path(dropbox_client, dropbox_path)
            if not ok:
                dropbox_client = None
                logging.warning("Dropbox 路径不可用，已禁用 Dropbox 上传")

        downloader = PhotoDownloader(
            PHOTO_DIR,
            dropbox_client=dropbox_client,
            dropbox_path=dropbox_path,
        )

        connection_failures = 0
        success = False

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=HEADLESS)
                context = await browser.new_context(
                    extra_http_headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    }
                )
                page = await context.new_page()
                page.set_default_timeout(TIMEOUT)

                logging.info("访问页面...")
                await page.goto(cfg["target_url"], wait_until="domcontentloaded")
                await page.wait_for_timeout(PAGE_RENDER_WAIT)

                # 快速扫描指纹
                logging.info("扫描照片指纹...")
                all_fingerprints = await extractor.extract_fingerprints_fast(page)
                total_count = len(all_fingerprints)

                unknown_items = [
                    item for item in all_fingerprints
                    if not history.is_downloaded_by_fingerprint(item["fingerprint"])
                ]
                new_count = len(unknown_items)
                downloaded_count = total_count - new_count

                logging.info("扫描结果:")
                logging.info(f"- 总计: {total_count}")
                logging.info(f"- 已下载: {downloaded_count}")
                logging.info(f"- 新照片: {new_count}")

                success_count = 0
                fail_count = 0

                if new_count > 0:
                    logging.info(f"开始下载 {new_count} 张新照片...")
                    new_photos = await extractor.extract_photo_urls_by_fingerprints(
                        page,
                        [item["fingerprint"] for item in unknown_items],
                    )

                    for idx, photo in enumerate(new_photos, 1):
                        logging.info(f"[{idx}/{new_count}] 下载: {photo['filename']}")
                        ok = downloader.download_photo(photo["url"], photo["filename"])
                        if ok:
                            history.add_download_record(
                                fingerprint=photo["fingerprint"],
                                original_filename=photo["filename"],
                                thumbnail_url=photo["thumbnail_url"],
                            )
                            success_count += 1
                        else:
                            fail_count += 1

                    history.save_history()
                    logging.info(f"下载完成，成功 {success_count}/{new_count}")
                else:
                    logging.info("没有新照片需要下载")
                    history.save_history()  # 确保文件存在

                success = True
                await browser.close()

                # 结果汇总
                result.update(
                    {
                        "total_photos": total_count,
                        "new_photos": new_count,
                        "download_success": success_count,
                        "download_failed": fail_count,
                        "dropbox_enabled": bool(dropbox_client),
                        "dropbox_uploaded": success_count if dropbox_client else 0,
                        "dropbox_failed": fail_count if dropbox_client else 0,
                        "history_size": len(history.downloads),
                    }
                )

        except Exception as e:
            connection_failures += 1
            logging.error(f"任务执行失败: {e}")
            import traceback
            traceback.print_exc()
            result["last_error"] = str(e)
            success = False

        result["success"] = success
        result["ended_at"] = now_iso()
        result["duration_sec"] = round(time.time() - start_ts, 2)
        result["config"] = cfg

        # 写入状态与历史
        self.state.save_status(result)
        self.state.append_history(result)

        # 摘要日志
        logging.info(SEPARATOR)
        logging.info(
            f"本轮结束（success={success}，耗时={result['duration_sec']}s，新照片={result['new_photos']}，"
            f"成功下载={result['download_success']}，失败={result['download_failed']}）"
        )
        logging.info(SEPARATOR)

        return result
