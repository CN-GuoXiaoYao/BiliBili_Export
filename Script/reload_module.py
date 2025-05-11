import os
import subprocess
import logging
import threading
from pathlib import Path
import json
from datetime import datetime
import traceback
import requests

from download_module import BilibiliDownloader
from concurrent.futures import ThreadPoolExecutor, as_completed


class CacheReloader:
    def __init__(self, config, stop_event, progress_callback, log_callback,
                 device_type="computer", phone_file=None, max_threads=1):
        self.config = config
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.device_type = device_type
        self.phone_file = phone_file
        self.max_threads = max_threads
        self.active_process = None
        self.lock = threading.Lock()
        self.total_files = 0
        self.processed_files = 0
        self.active_processes = {}

    @staticmethod
    def _log_error(bvid: str, error_msg: str):
        error_file = Path(__file__).parent / "errors.log"
        try:
            with open(error_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ")
                f.write(f"[重载失败] BV号: {bvid} | 错误信息: {error_msg}\n")
        except Exception as e:
            logging.error(f"错误日志写入失败: {str(e)}")

    def _av_to_bvid(self, av_id: str):
        """将AV号转换为BVID"""
        api_url = f"https://api.bilibili.com/x/web-interface/view?aid={av_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }

        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != 0:
                self.log_callback(f"AV{av_id}转换失败：{data.get('message', '未知错误')}")
                return None, None

            video_info = data.get('data', {})
            return video_info.get('bvid'), video_info.get('title', '未知标题')

        except Exception as e:
            self.log_callback(f"AV{av_id}转换异常：{str(e)}")
            return None, None

    def _execute_command(self, cmd, bvid, task_id):
        """修改为支持多任务标识"""
        try:
            self.log_callback(f"开始处理：{bvid} (任务ID: {task_id})")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                text=True
            )

            # 记录进程到字典
            with self.lock:
                self.active_processes[task_id] = process

            while True:
                if self.stop_event.is_set():
                    self.log_callback(f"用户终止：{bvid} (任务ID: {task_id})")
                    process.terminate()
                    break

                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break

                if output:
                    self.log_callback(f"[任务{task_id}] {output.strip()}")

            return process.poll()
        finally:
            with self.lock:
                if task_id in self.active_processes:
                    del self.active_processes[task_id]
                self.processed_files += 1
                progress = int((self.processed_files / self.total_files) * 100) if self.total_files > 0 else 0
                self.progress_callback(progress)

    def _process_task(self, task_data):
        """统一任务处理方法"""
        if self.stop_event.is_set():
            return

        task_id, identifier, is_av = task_data
        try:
            if is_av:
                av_id = identifier
                bvid, title = self._av_to_bvid(av_id)
                if not bvid:
                    raise ValueError(f"无效AV号: {av_id}")
                identifier = bvid
            else:
                entry_path = Path(self.config['cache_root']) / identifier
                info = self._get_video_info(entry_path / ".videoInfo")
                if not info or 'bvid' not in info:
                    raise ValueError(f"无效缓存目录: {identifier}")
                title = info.get('title', '未知标题')
                bvid = info['bvid']

            cmd = [
                "yutto",
                "-c", self.config['sessdata'],
                "-q", str(self.quality),  # 新增质量参数存储
                "-d", self.config['output_dir'],
                f"https://www.bilibili.com/video/{bvid}"
            ]

            return_code = self._execute_command(cmd, bvid, task_id)

            if return_code == 0:
                folder_name = f"文件下载_{identifier}" if is_av else identifier
                BilibiliDownloader._record_download(bvid, folder_name, title)
            else:
                error_msg = f"处理失败：{bvid} (错误码: {return_code})"
                self.log_callback(error_msg)
                self._log_error(bvid, error_msg)

        except Exception as e:
            error_msg = f"任务失败：{identifier} ({str(e)})"
            self.log_callback(error_msg)
            self._log_error(bvid if 'bvid' in locals() else "未知", error_msg)

    def _prepare_tasks(self):
        """准备任务队列"""
        tasks = []
        if self.device_type == "computer":
            cache_dir = Path(self.config['cache_root'])
            entries = [entry for entry in os.listdir(cache_dir)
                       if (cache_dir / entry).is_dir() and entry.isdigit()]
            self.total_files = len(entries)
            tasks = [(idx, entry, False) for idx, entry in enumerate(entries)]
        else:
            with open(self.phone_file, 'r', encoding='utf-8') as f:
                av_list = [line.strip().lower().lstrip('av') for line in f if line.strip()]
            self.total_files = len(av_list)
            tasks = [(idx, av_id, True) for idx, av_id in enumerate(av_list)]
        return tasks

    def _process_computer_cache(self, quality):
        """处理电脑缓存模式（原有逻辑不变）"""
        cache_dir = Path(self.config['cache_root'])
        entries = [entry for entry in os.listdir(cache_dir) if (cache_dir / entry).is_dir() and entry.isdigit()]
        self.total_files = len(entries)
        self.processed_files = 0

        for entry in entries:
            if self.stop_event.is_set():
                break

            entry_path = cache_dir / entry
            info = self._get_video_info(entry_path / ".videoInfo")
            if not info or 'bvid' not in info:
                continue

            cmd = [
                "yutto",
                "-c", self.config['sessdata'],
                "-q", str(quality),
                "-d", self.config['output_dir'],
                f"https://www.bilibili.com/video/{info['bvid']}"
            ]

            return_code = self._execute_command(cmd, info['bvid'])
            if return_code == 0:
                title = info.get('title', '未知标题')
                folder_name = entry
                BilibiliDownloader._record_download(info['bvid'], folder_name, title)
            else:
                error_msg = f"处理失败：{info['bvid']} (错误码: {return_code})"
                self.log_callback(error_msg)
                self._log_error(info['bvid'], error_msg)

    def _process_phone_cache(self, quality):
        """处理手机缓存模式（新逻辑）"""
        try:
            with open(self.phone_file, 'r', encoding='utf-8') as f:
                av_list = [line.strip().lower().lstrip('av') for line in f if line.strip()]

            self.total_files = len(av_list)
            self.processed_files = 0

            for av_id in av_list:
                if self.stop_event.is_set():
                    break

                # 转换AV号为BVID
                bvid, title = self._av_to_bvid(av_id)
                if not bvid:
                    self.log_callback(f"跳过无效AV号：{av_id}")
                    error_msg = f"处理失败：{av_id} (无效AV号)"
                    self.log_callback(error_msg)
                    self._log_error(bvid, 'AV' + error_msg)
                    continue

                # 构建下载命令（复用电脑模式逻辑）
                cmd = [
                    "yutto",
                    "-c", self.config['sessdata'],
                    "-q", str(quality),
                    "-d", self.config['output_dir'],
                    f"https://www.bilibili.com/video/{bvid}"
                ]

                return_code = self._execute_command(cmd, bvid)
                if return_code == 0:
                    folder_name = f"文件下载_{av_id}"
                    BilibiliDownloader._record_download(bvid, folder_name, title)
                else:
                    error_msg = f"处理失败：{bvid} (错误码: {return_code})"
                    self.log_callback(error_msg)
                    self._log_error(bvid, error_msg)

        except Exception as e:
            error_msg = f"手机缓存处理失败：{str(e)}\n{traceback.format_exc()}"
            self.log_callback(error_msg)
            self._log_error("未知", error_msg)
            raise

    def start_reload(self, quality):
        """重构后的启动方法"""
        self.quality = quality  # 存储质量参数
        try:
            # 验证必要参数
            if self.device_type == "computer":
                if not Path(self.config['cache_root']).exists():
                    raise FileNotFoundError("电脑缓存目录不存在")
            else:
                if not Path(self.phone_file).exists():
                    raise FileNotFoundError("手机缓存文件不存在")

            # 准备任务队列
            tasks = self._prepare_tasks()
            if not tasks:
                self.log_callback("没有需要处理的任务")
                return

            # 使用线程池执行
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                self.executor = executor
                futures = [executor.submit(self._process_task, task) for task in tasks]

                # 等待任务完成或停止事件
                for future in as_completed(futures):
                    if self.stop_event.is_set():
                        self._stop_all_processes()
                        break

        except Exception as e:
            error_msg = f"重载异常：{str(e)}\n{traceback.format_exc()}"
            self.log_callback(error_msg)
            self._log_error("未知", error_msg)
        finally:
            self.progress_callback(100)
            self.log_callback("重载任务结束")
            self.executor = None

    def _stop_all_processes(self):
        """停止所有运行中的进程"""
        with self.lock:
            for task_id, process in self.active_processes.items():
                try:
                    process.terminate()
                    self.log_callback(f"已终止任务ID: {task_id}")
                except ProcessLookupError:
                    pass
            self.active_processes.clear()

    def stop_reload(self):
        """增强停止方法"""
        self.stop_event.set()
        self._stop_all_processes()
        if self.executor:
            self.executor.shutdown(wait=False)

    @staticmethod
    def _get_video_info(path):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except Exception as e:
            logging.error(f"视频信息解析失败：{str(e)}")
            return None
