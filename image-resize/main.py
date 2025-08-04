import os
import sys
import stat
from PIL import Image, ImageSequence


def resize_image(image, target_width):
    """缩放图像到目标宽度，保持宽高比"""
    w, h = image.size
    if w == target_width:
        return image
    new_height = int(h * target_width / w)
    return image.resize((target_width, new_height), Image.LANCZOS)


def process_file(input_path, output_path, target_width):
    """处理单个图像文件并保存到输出路径"""
    img = None
    try:
        # 创建输出目录（如果不存在）
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 打开图像文件
        img = Image.open(input_path)
        original_format = img.format.upper() if img.format else None

        # 处理动画图像（GIF/WEBP）
        if getattr(img, 'is_animated', False) and original_format in ('GIF', 'WEBP'):
            frames = []
            durations = []
            disposals = []
            transparency = img.info.get('transparency', None)
            background = img.info.get('background', None)

            # 处理每一帧
            for i, frame in enumerate(ImageSequence.Iterator(img)):
                # 将帧转换为RGBA以保留透明度
                frame_rgba = frame.convert('RGBA')
                resized_frame = resize_image(frame_rgba, target_width)
                frames.append(resized_frame)
                durations.append(frame.info.get('duration', 100))
                disposals.append(frame.disposal_method if hasattr(frame, 'disposal_method') else 1)

            # 保存动画
            save_args = {
                    'format': original_format,
                    'save_all': True,
                    'append_images': frames[1:],
                    'duration': durations,
                    'loop': img.info.get('loop', 0),
                    'disposal': disposals,
                    }

            # 添加透明度和背景信息（如果存在）
            if transparency is not None:
                save_args['transparency'] = transparency
            if background is not None:
                save_args['background'] = background

            frames[0].save(output_path, **save_args)

        # 处理静态图像
        else:
            # 确定输出格式
            output_format = 'JPEG' if original_format in ('JPEG', 'JFIF') else original_format

            # 缩放图像并转换为合适的颜色模式
            if output_format == 'JPEG':
                # 对于JPEG，转换为RGB模式
                resized_img = resize_image(img.convert('RGB'), target_width)
            else:
                # 对于其他格式，保留RGBA模式
                resized_img = resize_image(img.convert('RGBA'), target_width)

            # 保存图像
            save_args = {
                    'format': output_format
                    }
            if output_format == 'JPEG':
                save_args['quality'] = 100  # 设置JPEG质量
            resized_img.save(output_path, **save_args)

        return True
    except Exception as e:
        print(f"处理文件 {os.path.basename(input_path)} 时出错: {str(e)}")
        return False
    finally:
        if img:
            img.close()


def should_exclude_dir(dir_name):
    """检查是否应该排除该目录"""
    return dir_name.startswith('output_') and dir_name[7:].isdigit()


def main():
    """主函数"""
    print("处理当前文件夹及其子文件夹下的所有图片")
    # 获取目标宽度
    width_input = input("请输入目标宽度（回车默认680）: ").strip()
    target_width = 680 if width_input == "" else int(width_input)

    # 创建输出目录名称
    output_dir_name = f"output_{target_width}"

    # 获取当前工作目录（处理打包环境）
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
    else:
        current_dir = os.getcwd()

    # 创建输出目录
    output_dir = os.path.join(current_dir, output_dir_name)
    os.makedirs(output_dir, exist_ok=True)

    # 支持的图像扩展名
    valid_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.jfif'}

    # 收集所有图像文件（排除输出目录）
    image_files = []
    total_count = 0

    for root, dirs, files in os.walk(current_dir):
        # 排除输出目录及其子目录
        # 注意：修改dirs列表，使得后续遍历跳过排除的目录
        dirs[:] = [d for d in dirs if not should_exclude_dir(d)]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_exts:
                input_path = os.path.join(root, file)
                # 计算相对路径
                rel_path = os.path.relpath(input_path, current_dir)
                output_path = os.path.join(output_dir, rel_path)

                # 只处理不在输出目录中的文件（这里通过排除目录已经避免，但双重保险）
                # 因为输出目录已经被排除，所以这里不需要再判断
                image_files.append((input_path, output_path))
                total_count += 1

    # 处理所有图像文件
    processed_count = 0

    print(f"找到 {total_count} 个图像文件，开始处理...")

    for i, (input_path, output_path) in enumerate(image_files, 1):
        # 显示进度
        file_name = os.path.basename(input_path)
        print(f"[{i}/{total_count}] {file_name}")

        # 处理文件
        if process_file(input_path, output_path, target_width):
            processed_count += 1

    print(f"成功处理 {processed_count}/{total_count} 个文件")
    print(f"结果已保存到: {output_dir}")
    print(f"---即当前目录下 output_{target_width} 文件夹---")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        import traceback

        traceback.print_exc()

    # 打包环境下安全暂停
    if getattr(sys, 'frozen', False):
        input("\n按回车键退出程序...")
