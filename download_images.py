import argparse
import hashlib
import os
import re
import ssl
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

# 扩展MIME类型映射
MIME_TO_EXT = {
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'image/svg+xml': 'svg',
        'image/bmp': 'bmp',
        }

# 通用浏览器头
HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }

# 禁用SSL验证
ssl._create_default_https_context = ssl._create_unverified_context


def sanitize_filename(filename):
    """处理非法文件名并限制长度"""
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    return filename[:255]


def extract_image_sources(html):
    """使用正则表达式提取图片源"""
    img_tags = re.findall(r'<img\s+[^>]*>', html, re.IGNORECASE)
    sources = []

    for tag in img_tags:
        # 按属性优先级提取
        for attr in ['data-src', 'src', 'data-original']:
            match = re.search(rf'{attr}=["\'](.*?)["\']', tag, re.IGNORECASE)
            if match and not match.group(1).startswith('data:'):
                sources.append(match.group(1))
                break
    return sources


def main():
    parser = argparse.ArgumentParser(description='轻量版图片下载工具')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()

    base_dir = Path.cwd() if args.debug else Path.home() / 'Desktop'
    download_dir = base_dir / 'imgDownload'
    download_dir.mkdir(parents=True, exist_ok=True)

    print("请输入多个链接（每行一个，{}结束输入）：".format("按Ctrl+D" if os.name == 'posix' else "按Ctrl+Z后回车"))
    urls = []
    try:
        while True:
            line = input()
            if line.strip():
                urls.append(line.strip())
    except EOFError:
        pass

    image_urls = []
    for url in urls:
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=10) as response:
                content_type = response.info().get('Content-Type', '').split(';')[0].lower()

                if 'text/html' in content_type:
                    html = response.read().decode('utf-8', errors='ignore')
                    for src in extract_image_sources(html):
                        # 处理微信公众号特殊格式
                        if 'mp.weixin.qq.com' in url:
                            if src.startswith('//'):
                                src = f'https:{src}'
                            elif src.startswith('/'):
                                src = f'https://mp.weixin.qq.com{src}'

                        absolute_url = urljoin(url, src)
                        image_urls.append(absolute_url)
                elif content_type.startswith('image/'):
                    image_urls.append(url)
                else:
                    print(f"⚠ 跳过非媒体内容：{url}")

        except Exception as e:
            print(f"❌ 处理链接失败 [{url}]: {str(e)}")

    success_count = 0
    total = len(image_urls)
    print(f"开始下载{total}张图片...")

    for i, img_url in enumerate(image_urls, 1):
        try:
            # 添加防盗链处理
            headers = HEADERS.copy()
            headers['Referer'] = urlparse(img_url).scheme + '://' + urlparse(img_url).netloc

            req = Request(img_url, headers=headers)
            with urlopen(req, timeout=15) as response:
                # 扩展名处理
                content_type = response.info().get('Content-Type', '').split(';')[0].lower()
                ext = MIME_TO_EXT.get(content_type)

                # 备用扩展名检测
                if not ext:
                    parsed = urlparse(img_url)
                    file_ext = os.path.splitext(parsed.path)[1][1:].lower()
                    ext = file_ext if file_ext in MIME_TO_EXT.values() else 'bin'

                # 文件名生成
                url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
                filename = sanitize_filename(os.path.basename(urlparse(img_url).path)) or f'img_{url_hash}'
                root = os.path.splitext(filename)[0]
                base_name = f"{root}.{ext}"

                # 冲突解决
                counter = 1
                while (download_dir / base_name).exists():
                    base_name = f"{root}_{counter}.{ext}"
                    counter += 1

                # 流式下载
                with open(download_dir / base_name, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

                success_count += 1
                print(f"\r✅ 成功下载 {i}/{total}", end='')
        except Exception as e:
            print(f"\r❌ 下载失败 [{i}/{total}]: {str(e)[:50]}")

    print(f"\n✅ 下载完成！成功下载 {success_count}/{total} 张图片")
    if success_count < total:
        print("提示：失败可能由于：\n1. 需要登录\n2. 动态加载内容\n3. 特殊反爬机制")


if __name__ == "__main__":
    main()
