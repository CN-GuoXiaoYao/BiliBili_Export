# download_module.py
import subprocess
import threading
import logging
import requests
from pathlib import Path
import re
import os
import json
from urllib.parse import unquote
from datetime import datetime

download_logger = logging.getLogger('DownloadModule')

class BilibiliDownloader:
    @staticmethod
    def _get_bvid_from_url(url: str) -> str:
        match = re.search(r"BV[0-9A-Za-z]{10}", url)
        return match.group(0) if match else ""

    @staticmethod
    def _get_record_path():
        return Path(__file__).parent / "downloaded.txt"

    @staticmethod
    def _record_download(bvid: str, folder_name: str, title: str):
        record_file = BilibiliDownloader._get_record_path()
        try:
            if not record_file.exists():
                record_file.touch(mode=0o666, exist_ok=True)
            with open(record_file, "a+", encoding="utf-8") as f:
                f.seek(0)
                existing = f.read()
                if bvid and bvid not in existing:
                    f.write(f"{bvid}|{folder_name}|{title}\n")
                    os.fsync(f.fileno())
                    download_logger.info(f"成功记录视频号: {bvid}, 存储方式: {folder_name}, 标题: {title}")
        except Exception as e:
            download_logger.error(f"记录失败: {str(e)}")

    @staticmethod
    def _log_error(bvid: str, title: str, error_msg: str):
        error_file = Path(__file__).parent / "errors.log"
        try:
            with open(error_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ")
                f.write(f"BV号: {bvid} | 标题: {title} | 错误信息: {error_msg}\n")
        except Exception as e:
            logging.error(f"错误日志写入失败: {str(e)}")

    @staticmethod
    def is_downloaded(bvid: str) -> bool:
        record_file = BilibiliDownloader._get_record_path()
        try:
            with open(record_file, "r", encoding="utf-8") as f:
                return bvid in f.read()
        except FileNotFoundError:
            return False
        except Exception as e:
            download_logger.error(f"读取失败: {str(e)}")
            return False

    @staticmethod
    def _get_bilibili_title(bvid: str) -> str:
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 0:
                return data["data"]["title"]
            download_logger.warning(f"API返回错误: {data}")
        except Exception as e:
            download_logger.error(f"获取标题失败: {str(e)}")
        return "未知标题"

    @staticmethod
    def download_video(url, quality, is_collection, output_dir, cache_root, sessdata, progress_callback, log_callback, stop_event):
        if "%" in sessdata:
            sessdata = unquote(sessdata)
            log_callback("检测到URL编码的SESSDATA，已自动解码")

        cmd = [
            "yutto",
            "-c", sessdata,
            "-q", str(quality),
            "-d", output_dir,
            url
        ]

        if is_collection:
            cmd.append("-b")

        log_callback(f"执行命令: {' '.join(cmd)}")
        bvid = BilibiliDownloader._get_bvid_from_url(url)
        success = False
        title = "未知标题"

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                text=True,
                bufsize=1
            )

            while True:
                if stop_event.is_set():
                    log_callback("用户中止下载")
                    proc.terminate()
                    break

                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break

                if line:
                    log_callback(f"[下载进度] {line.strip()}")

            stderr = proc.stderr.read()
            if stderr:
                log_callback(f"[错误详情] {stderr}")
                if "Session expired" in stderr:
                    log_callback("错误：SESSDATA已过期！")
                elif "404" in stderr:
                    log_callback("错误：视频不存在！")

            if proc.returncode == 0:
                log_callback("下载成功完成")
                success = True
            else:
                log_callback(f"下载失败，错误码：{proc.returncode}")
                BilibiliDownloader._log_error(bvid, title, f"错误码: {proc.returncode}")

        except Exception as e:
            error_msg = f"致命错误：{str(e)}"
            log_callback(error_msg)
            title = BilibiliDownloader._get_bilibili_title(bvid) or "未知标题"
            BilibiliDownloader._log_error(bvid, title, error_msg)
        finally:
            if success and bvid:
                title = BilibiliDownloader._get_bilibili_title(bvid)
                BilibiliDownloader._record_download(bvid, "网络", title)

    @staticmethod
    def _get_cache_folder_name(cache_root: str, bvid: str) -> str:
        cache_dir = Path(cache_root)
        for entry in cache_dir.glob("**/.videoInfo"):
            folder = entry.parent
            if not folder.name.isdigit():
                continue
            try:
                with open(entry, "r", encoding="utf-8") as f:
                    info = json.load(f)
                    if info.get("bvid") == bvid:
                        return folder.name
            except Exception as e:
                download_logger.warning(f"解析失败: {str(e)}")
        return "未知文件夹"

    @staticmethod
    def start_download(url, quality, is_collection, output_dir, cache_root, sessdata, progress_callback, log_callback, stop_event):
        thread = threading.Thread(
            target=BilibiliDownloader.download_video,
            args=(url, quality, is_collection, output_dir, cache_root, sessdata, progress_callback, log_callback, stop_event),
            daemon=True
        )
        thread.start()
        return thread