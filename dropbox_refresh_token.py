"""Dropbox Refresh Token 获取脚本

用法:
1) 确保已安装 Dropbox SDK: `uv add dropbox` 或 `pip install dropbox`
2) 在本地运行（可打开浏览器的机器）:
   python dropbox_refresh_token.py
3) 按提示输入 app key / app secret（或通过环境变量提供）
4) 打开输出的授权链接，在浏览器登录并允许权限
5) 将网页显示的 code 粘贴回终端，即可获得 refresh_token

拿到 refresh_token 后，将其与 app key、app secret 一起配置到服务器的环境变量或安全配置文件中。
"""

import os
import sys

try:
    import dropbox
except ImportError:
    print("缺少依赖: dropbox")
    print("请先安装: uv add dropbox 或 pip install dropbox")
    sys.exit(1)


# 默认权限需要包含 account_info.read，否则 SDK 无法调用 users_get_current_account
DEFAULT_SCOPES = ["files.content.write", "files.content.read", "account_info.read"]


def prompt(prompt_text: str, default: str | None = None) -> str:
    value = input(f"{prompt_text}{' [' + default + ']' if default else ''}: ").strip()
    return value or (default or "")


def main():
    app_key = os.environ.get("DROPBOX_APP_KEY") or prompt("请输入 Dropbox App Key")
    app_secret = os.environ.get("DROPBOX_APP_SECRET") or prompt("请输入 Dropbox App Secret")

    if not app_key or not app_secret:
        print("App Key 和 App Secret 不能为空")
        sys.exit(1)

    auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(
        consumer_key=app_key,
        consumer_secret=app_secret,
        token_access_type="offline",  # 请求 refresh_token
        scope=DEFAULT_SCOPES,
    )

    authorize_url = auth_flow.start()
    print("\n1) 请在浏览器中打开以下链接，登录并授权：\n")
    print(authorize_url)

    auth_code = input("\n2) 授权完成后，复制网页显示的 code 并粘贴到这里: ").strip()
    if not auth_code:
        print("授权 code 为空，已退出")
        sys.exit(1)

    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:
        print(f"获取 token 失败: {e}")
        sys.exit(1)

    print("\n✅ 获取成功，请妥善保存以下信息：\n")
    print(f"app_key: {app_key}")
    print(f"app_secret: {app_secret}")
    print(f"refresh_token (长期可复用): {oauth_result.refresh_token}")
    print(f"access_token (短期，仅参考): {oauth_result.access_token}")
    print("\n请在服务器的环境变量或配置文件中填入 refresh_token、app_key、app_secret。")


if __name__ == "__main__":
    main()
