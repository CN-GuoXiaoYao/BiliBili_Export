import os
import subprocess
import tempfile
import logging
from pathlib import Path
from datetime import datetime


def validate_files(file_paths):
    """
    简单验证文件是否存在、权限以及后缀是否为.m4s
    """
    for path in file_paths:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在：{path}")
        if not os.access(str(p), os.R_OK):
            raise PermissionError(f"没有读取权限：{path}")
        if p.suffix.lower() != '.m4s':
            raise ValueError(f"文件后缀不为.m4s：{path}")
    return True


def process_file(file_path, temp_files):
    """
    处理单个文件：检查前导9个零，需要时创建临时文件
    返回处理后的文件路径
    """
    with open(file_path, 'rb') as f:
        head = f.read(9)

    if head == b'0' * 9:
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.m4s')
        temp_path = temp_file.name
        temp_file.close()  # 立即关闭文件句柄以便写入

        try:
            with open(temp_path, 'wb') as f_out, open(file_path, 'rb') as f_in:
                f_in.seek(9)  # 跳过前9字节
                while True:
                    chunk = f_in.read(4096)  # 分块读取避免内存问题
                    if not chunk:
                        break
                    f_out.write(chunk)
            temp_files.append(temp_path)
            return temp_path
        except Exception as e:
            os.remove(temp_path)
            raise RuntimeError(f"处理文件 {file_path} 失败：{e}")
    else:
        return file_path


def merge_m4s_files(file_list, output_dir, output_filename=None):
    """
    使用 ffmpeg 将两个 m4s 文件（视频和音频）合并为一个 MP4 文件。
    自动处理前导9个零且不影响原文件
    """
    temp_files = []  # 用于记录临时文件路径

    try:
        # 验证文件
        validate_files(file_list)
        if len(file_list) != 2:
            raise ValueError("必须提供两个文件：一个视频和一个音频")

        # 处理前导零
        processed_files = [
            process_file(file_list[0], temp_files),
            process_file(file_list[1], temp_files)
        ]

        # 生成输出文件路径
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if output_filename and output_filename.strip():
            filename = output_filename.strip()
        else:
            filename = "合并_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = out_dir / f"{filename}.mp4"

        # 调用 ffmpeg 进行合并
        cmd = [
            'ffmpeg',
            '-v', 'error',
            '-hide_banner',
            '-y',
            '-i', processed_files[0],
            '-i', processed_files[1],
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            str(output_path)
        ]
        subprocess.run(cmd, check=True)

        # 校验输出文件
        if not output_path.exists():
            raise RuntimeError("输出文件不存在")
        if output_path.stat().st_size < 1024:
            raise RuntimeError("输出文件过小，可能失败")
        return str(output_path)

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg处理出错: {e}"
        logging.error(error_msg)
        raise RuntimeError(error_msg)
    finally:
        # 清理临时文件
        for path in temp_files:
            try:
                os.remove(path)
            except Exception as e:
                logging.error(f"删除临时文件失败 {path}: {e}")