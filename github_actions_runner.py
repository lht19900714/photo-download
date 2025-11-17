"""
GitHub Actions 专用运行器
单次运行模式，配合 GitHub Actions 定时触发

与 photo_downloader.py 的区别：
- photo_downloader.py: 本地持续运行模式（while True 循环）
- github_actions_runner.py: 云端单次运行模式（执行一次后退出）

复用策略：
- 导入 photo_downloader.py 中的核心类和函数
- 新增配置文件驱动的运行逻辑
- 新增 Git 提交功能
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 导入现有核心组件
from photo_downloader import (
    DownloadHistory,
    PhotoExtractor,
    PhotoDownloader,
    init_dropbox_client,
    ensure_dropbox_path,
    SEPARATOR
)

from config import (
    TARGET_URL,
    PHOTO_DIR,
    DOWNLOADED_HISTORY,
    HEADLESS,
    TIMEOUT,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Actions 专用配置
RUNTIME_CONFIG_PATH = Path("runtime-config.json")
MAX_RUNTIME_MINUTES = 10


class RuntimeConfig:
    """运行时配置管理器"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load()

    def _load(self) -> dict:
        """读取配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}\n"
                "请通过 Web 面板初始化配置"
            )

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def should_run(self) -> bool:
        """判断是否应该执行任务"""
        # 检查是否启用
        if not self.config.get('enabled', False):
            logging.info("✋ 监控未启用，退出")
            return False

        # 检查时间间隔
        last_run = self.config.get('lastRunTime')
        interval = self.config.get('interval', 10)  # 分钟

        if last_run:
            try:
                # 解析 ISO 格式时间戳
                last_time = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                elapsed = (now - last_time).total_seconds() / 60

                if elapsed < interval:
                    logging.info(
                        f"⏱️  距离上次运行仅 {elapsed:.1f} 分钟，"
                        f"未达到设定间隔 {interval} 分钟，退出"
                    )
                    return False
            except Exception as e:
                logging.warning(f"解析上次运行时间失败: {e}，将继续执行")

        return True

    def should_clear_history(self) -> bool:
        """是否需要清除历史记录（首次运行标志）"""
        return self.config.get('clearHistory', False)

    def get_task_config(self) -> dict:
        """获取任务配置"""
        return self.config.get('taskConfig', {})

    def update_after_run(self, success: bool):
        """更新运行时间戳和状态"""
        self.config['lastRunTime'] = datetime.now(timezone.utc).isoformat()
        self.config['clearHistory'] = False  # 清理标志仅生效一次
        self.config['lastRunSuccess'] = success

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        logging.info(f"✓ 配置已更新: lastRunTime, clearHistory=False, success={success}")


def commit_changes(files: list[str], message: str):
    """提交更改到 Git 仓库"""
    try:
        # 配置 Git 用户（Actions 环境）
        subprocess.run(
            ['git', 'config', 'user.name', 'GitHub Actions Bot'],
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'actions@github.com'],
            check=True,
            capture_output=True
        )

        # 添加文件
        subprocess.run(['git', 'add'] + files, check=True, capture_output=True)

        # 检查是否有变更
        result = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            capture_output=True
        )

        if result.returncode != 0:  # 有变更
            # 提交（添加 [skip ci] 避免触发新的 workflow）
            subprocess.run(
                ['git', 'commit', '-m', f'{message} [skip ci]'],
                check=True,
                capture_output=True
            )

            # 推送（带重试和 rebase）
            for attempt in range(3):
                try:
                    # 先拉取可能的远程变更
                    subprocess.run(
                        ['git', 'pull', '--rebase'],
                        check=True,
                        capture_output=True
                    )
                    # 推送
                    subprocess.run(['git', 'push'], check=True, capture_output=True)
                    logging.info(f"✅ Git 提交成功: {message}")
                    break
                except subprocess.CalledProcessError as e:
                    if attempt == 2:
                        raise
                    logging.warning(f"⚠️ 推送失败，重试 {attempt + 1}/3...")
                    import time
                    time.sleep(2)
        else:
            logging.info("ℹ️  无变更需要提交")

    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Git 提交失败: {e}")
        logging.error(f"标准输出: {e.stdout.decode() if e.stdout else 'N/A'}")
        logging.error(f"错误输出: {e.stderr.decode() if e.stderr else 'N/A'}")
        raise


async def run_single_cycle():
    """执行单次下载循环"""
    from playwright.async_api import async_playwright

    # 1. 读取运行时配置
    logging.info(SEPARATOR)
    logging.info("GitHub Actions Runner - 单次运行模式")
    logging.info(SEPARATOR)

    try:
        runtime_config = RuntimeConfig(RUNTIME_CONFIG_PATH)
    except FileNotFoundError as e:
        logging.error(f"❌ {e}")
        return

    # 2. 检查是否应该运行
    if not runtime_config.should_run():
        return

    logging.info("✅ 满足运行条件，开始执行任务")
    logging.info(f"开始时间: {datetime.now()}")
    logging.info(SEPARATOR)

    # 3. 处理首次运行（清除历史）
    if runtime_config.should_clear_history():
        logging.info("🗑️  检测到 clearHistory 标志，清理历史记录...")
        history_file = Path(DOWNLOADED_HISTORY)
        if history_file.exists():
            history_file.unlink()
            logging.info("✅ 历史记录已清理")
        else:
            logging.info("ℹ️  历史记录文件不存在，跳过清理")

    # 4. 初始化组件
    history = DownloadHistory(DOWNLOADED_HISTORY)

    # 获取任务配置
    task_config = runtime_config.get_task_config()
    target_url = task_config.get('targetUrl', TARGET_URL)

    # 从环境变量读取 Dropbox Token
    dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
    dropbox_path = task_config.get('dropboxPath', '/photos')

    # 初始化 Dropbox 客户端
    dropbox_client = None
    if dropbox_token:
        logging.info("正在初始化 Dropbox 客户端...")
        dropbox_client = init_dropbox_client(dropbox_token)
        if dropbox_client:
            path_ready = ensure_dropbox_path(dropbox_client, dropbox_path)
            if not path_ready:
                logging.warning("⚠️ Dropbox 路径初始化失败，将禁用 Dropbox 功能")
                dropbox_client = None
        else:
            logging.warning("⚠️ Dropbox 客户端初始化失败，将仅使用本地存储")
    else:
        logging.info("ℹ️  未配置 Dropbox Token，跳过 Dropbox 上传")

    downloader = PhotoDownloader(
        PHOTO_DIR,
        dropbox_client=dropbox_client,
        dropbox_path=dropbox_path
    )
    extractor = PhotoExtractor()

    # 打印配置信息
    logging.info(f"目标 URL: {target_url}")
    logging.info(f"历史记录: {len(history.downloads)} 张照片")
    if dropbox_client:
        logging.info(f"Dropbox 存储: {dropbox_path}")
    logging.info(SEPARATOR)

    success = False

    try:
        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                extra_http_headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
            page = await context.new_page()
            page.set_default_timeout(TIMEOUT)

            # 访问页面
            logging.info("📄 正在访问页面...")
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            logging.info("✅ 页面加载成功")

            # 快速扫描所有照片指纹
            logging.info("\n🔍 正在扫描照片指纹...")
            all_fingerprints = await extractor.extract_fingerprints_fast(page)
            total_count = len(all_fingerprints)

            # 识别未下载的照片
            unknown_items = [
                item for item in all_fingerprints
                if not history.is_downloaded_by_fingerprint(item['fingerprint'])
            ]
            new_count = len(unknown_items)
            downloaded_count = total_count - new_count

            logging.info(f"\n📊 扫描结果:")
            logging.info(f"  - 总计: {total_count} 张照片")
            logging.info(f"  - 已下载: {downloaded_count} 张")
            logging.info(f"  - 新照片: {new_count} 张")

            # 下载新照片
            if new_count > 0:
                logging.info(f"\n⬇️  开始下载 {new_count} 张新照片...")

                # 获取新照片的原图 URL
                new_photos = await extractor.extract_photo_urls_by_fingerprints(
                    page,
                    [item['fingerprint'] for item in unknown_items]
                )

                success_count = 0
                for idx, photo in enumerate(new_photos, 1):
                    logging.info(f"\n[{idx}/{new_count}] 下载: {photo['filename']}")

                    # 下载照片
                    download_success = downloader.download_photo(
                        photo['url'],
                        photo['filename']
                    )

                    if download_success:
                        # 记录下载信息
                        history.add_download_record(
                            fingerprint=photo['fingerprint'],
                            original_filename=photo['filename'],
                            thumbnail_url=photo['thumbnail_url']
                        )
                        success_count += 1

                # 保存历史记录
                history.save_history()
                logging.info(f"\n✅ 本次下载完成，成功 {success_count}/{new_count} 张照片")
                logging.info(f"📝 历史记录已更新: {len(history.downloads)} 张照片")
            else:
                logging.info("\n✅ 没有新照片需要下载")

            await browser.close()
            success = True

    except Exception as e:
        logging.error(f"\n❌ 任务执行失败: {e}")
        import traceback
        traceback.print_exc()
        success = False

    finally:
        # 更新运行时配置
        logging.info("\n📝 更新运行时配置...")
        runtime_config.update_after_run(success)

        # 提交更改到 Git
        logging.info("📤 提交更改到 Git...")
        try:
            commit_changes(
                ['runtime-config.json', 'downloaded.json'],
                f'Update download history - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
            )
        except Exception as e:
            logging.error(f"⚠️ Git 提交失败（不影响下载结果）: {e}")

        logging.info(SEPARATOR)
        logging.info(f"任务结束时间: {datetime.now()}")
        logging.info(f"执行结果: {'✅ 成功' if success else '❌ 失败'}")
        logging.info(SEPARATOR)


async def main():
    """主入口"""
    try:
        # 设置超时
        await asyncio.wait_for(
            run_single_cycle(),
            timeout=MAX_RUNTIME_MINUTES * 60
        )
    except asyncio.TimeoutError:
        logging.error(f"❌ 任务超时（超过 {MAX_RUNTIME_MINUTES} 分钟）")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ 未预期错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\n\n⚠️ 收到中断信号，程序已终止")
        sys.exit(0)
