import hashlib
import os
import re
import ssl
import sys
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


def normalize_url(url):
    """规范化URL，确保有协议"""
    url = url.strip()
    if re.match(r'^https?://', url, re.IGNORECASE):
        return url
    if url.startswith('//'):
        return 'https:' + url
    return 'https://' + url


def main():
    # 创建下载目录
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    download_dir = os.path.join(desktop, "0000网页图片下载")
    os.makedirs(download_dir, exist_ok=True)

    # 简化用户输入
    print("=" * 50)
    print("网页图片下载工具")
    print("=" * 50)
    raw_url = input("请输入网页链接，只支持一条链接（输入后按回车开始下载）:\n> ").strip()

    if not raw_url:
        print("未输入链接，程序已退出")
        return

    # 规范化URL
    url = normalize_url(raw_url)
    print(f"规范化后的URL: {url}")

    print("正在分析网页内容...")
    image_urls = []

    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=10) as response:
            content_type = response.info().get('Content-Type', '').split(';')[0].lower()
            base_url = response.url  # 获取最终URL（考虑重定向）

            if 'text/html' in content_type:
                html = response.read().decode('utf-8', errors='ignore')
                for src in extract_image_sources(html):
                    # 协议相对路径处理
                    if src.startswith('//'):
                        src = f'https:{src}'
                    # 根路径相对路径处理
                    elif src.startswith('/'):
                        parsed = urlparse(base_url)
                        src = f"{parsed.scheme}://{parsed.netloc}{src}"
                    # 微信特殊处理
                    elif 'mmbiz.' in src and not src.startswith(('http:', 'https:')):
                        src = f'https:{src}' if src.startswith('//') else f'https://{src}'

                    absolute_url = urljoin(base_url, src)
                    image_urls.append(absolute_url)

            elif content_type.startswith('image/'):
                image_urls.append(base_url)
            else:
                print(f"跳过非媒体内容：{url}")
                return

    except Exception as e:
        print(f"处理链接失败: {str(e)}")
        return

    success_count = 0
    total = len(image_urls)

    if total == 0:
        print("未找到任何图片")
        return

    print(f"发现 {total} 张图片，开始下载...")

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
                save_path = os.path.join(download_dir, base_name)
                counter = 1
                while os.path.exists(save_path):
                    base_name = f"{root}_{counter}.{ext}"
                    save_path = os.path.join(download_dir, base_name)
                    counter += 1

                # 流式下载
                with open(save_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

                success_count += 1
                print(f"\r下载进度: {i}/{total} (成功: {success_count})", end='')
        except Exception as e:
            print(f"\r下载失败 [{i}/{total}]: {str(e)[:50]}")

    print(f"\n\n成功下载 {success_count}/{total} 张图片")
    print(f"已保存到: {download_dir}")

    if success_count < total:
        print("\n部分图片下载失败可能由于：")
        print("1. 需要登录才能查看的图片")
        print("2. 动态加载的内容（如JavaScript生成的图片）")
        print("3. 网站的特殊保护机制")
        print("\n但是她就不需要关心为什么了，只需要找他就好了")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        # 忽略sys.exit调用
        pass
    except:
        # 打印异常信息
        import traceback

        traceback.print_exc()

    # 打包环境下安全暂停
    if getattr(sys, 'frozen', False):
        input("\n按回车键退出程序...")
