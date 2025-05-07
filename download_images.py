import argparse
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

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


def sanitize_filename(filename):
    """处理非法文件名并限制长度"""
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    return filename[:255]  # 防止超长文件名


def get_image_attributes(img_tag):
    """获取图片标签的有效属性"""
    for attr in ['data-src', 'src', 'data-original']:  # 常见懒加载属性
        if img_tag.get(attr):
            return attr, img_tag[attr]
    return None, None


def main():
    parser = argparse.ArgumentParser(description='增强版图片下载工具')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()

    # 设置下载目录
    base_dir = Path.cwd() if args.debug else Path.home() / 'Desktop'
    download_dir = base_dir / 'imgDownload'
    download_dir.mkdir(parents=True, exist_ok=True)

    print("开源地址：https://github.com/yuanze31/HTML-img-downloader")
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
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').split(';')[0].lower()

            if 'text/html' in content_type:
                soup = BeautifulSoup(response.content, 'lxml')
                for img in soup.find_all('img'):
                    attr_name, src = get_image_attributes(img)
                    if not src or src.startswith('data:'):
                        continue

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

    # 下载图片增强逻辑
    success_count = 0
    with tqdm(total=len(image_urls), desc="下载进度", unit='img') as pbar:
        for img_url in image_urls:
            try:
                # 添加防盗链处理
                headers = HEADERS.copy()
                headers['Referer'] = urlparse(img_url).scheme + '://' + urlparse(img_url).netloc

                response = requests.get(img_url, headers=headers, stream=True, timeout=15)
                response.raise_for_status()

                # 扩展名处理逻辑
                content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
                ext = MIME_TO_EXT.get(content_type, None)

                # 备用扩展名检测
                if not ext:
                    if response.url.endswith(('.jpg', '.jpeg')):
                        ext = 'jpg'
                    elif response.url.endswith('.png'):
                        ext = 'png'
                    else:
                        ext = 'bin'

                # 文件名生成策略
                url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
                parsed = urlparse(img_url)
                filename = sanitize_filename(os.path.basename(parsed.path)) or f'img_{url_hash}'
                root, _ = os.path.splitext(filename)
                base_name = f"{root}.{ext}" if ext else root

                # 冲突解决
                counter = 1
                while (download_dir / base_name).exists():
                    base_name = f"{root}_{counter}.{ext}" if ext else f"{root}_{counter}"
                    counter += 1

                # 保存文件
                with open(download_dir / base_name, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                success_count += 1
            except Exception as e:
                print(f"❌ 下载失败 [{img_url[:50]}...]: {str(e)}")
            finally:
                pbar.update(1)

    print(f"\n✅ 下载完成！成功下载 {success_count}/{len(image_urls)} 张图片")
    if success_count < len(image_urls):
        print("提示：部分失败可能由于：\n1. 需要登录\n2. 动态加载内容\n3. 特殊反爬机制")


if __name__ == "__main__":
    main()
