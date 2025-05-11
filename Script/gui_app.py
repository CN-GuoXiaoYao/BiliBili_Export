import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import json
import logging
import os
import queue
import threading
import sys
import subprocess
from pathlib import Path
from datetime import datetime

from download_module import BilibiliDownloader
from merge_module import merge_m4s_files
from reload_module import CacheReloader
from search_module import AdvancedSearchEngine

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class GUIHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.log_queue = log_queue

    def emit(self, record):
        log_entry = self.format(record)
        try:
            self.log_queue.put_nowait(log_entry)
        except queue.Full:
            pass


class AppLogger:
    @classmethod
    def setup(cls, log_queue: queue.Queue):
        gui_handler = GUIHandler(log_queue)
        for name in ['DownloadModule', 'ReloadModule', 'SearchModule']:
            logger = logging.getLogger(name)
            logger.addHandler(gui_handler)
            logger.propagate = False


class BilibiliToolkitGUI:
    QUALITY_OPTIONS = [
        ("8K", 127), ("4K", 126), ("1080P60", 125),
        ("1080P+", 120), ("1080P", 116), ("720P60", 112),
        ("720P", 100), ("480P", 80), ("360P", 16)
    ]

    def __init__(self, root):
        self.bilibilio_url = '感觉不错的话就充个电支持一下吧~'
        self.root = root
        self.config = self.load_config()
        self.log_queue = queue.Queue(maxsize=200)
        self.download_stop_event = threading.Event()
        self.reload_stop_event = threading.Event()
        self.current_reloader = None
        self.download_running = False
        self.reload_running = False
        self.setup_donation_links()

        self.setup_ui()
        AppLogger.setup(self.log_queue)
        self.start_log_poller()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_donation_links(self):
        """在所有页面添加赞助链接"""
        bilibili_uid = "504668072"  # 例如：12345678
        self.bilibili_url = f"https://space.bilibili.com/{bilibili_uid}"

        # 统一样式配置
        self.link_style = {
            "foreground": "#00A1D6",  # B站主题色
            "font": ("微软雅黑", 9, "underline"),
            "cursor": "hand2"
        }

    def add_donation_link(self, parent):
        """在指定父容器添加赞助链接"""
        link_frame = ttk.Frame(parent)
        link_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        label = ttk.Label(
            link_frame,
            text="♥ 作者B站:@郭逍遥",
            **self.link_style
        )
        label.pack(side=tk.RIGHT, padx=10)

        label.bind("<Button-1>", lambda e: self.open_bilibili())
        label.bind("<Enter>", lambda e: label.config(foreground="#FF6699"))
        label.bind("<Leave>", lambda e: label.config(foreground="#00A1D6"))

    def open_bilibili(self):
        """打开B站主页"""
        try:
            import webbrowser
            webbrowser.open_new(self.bilibili_url)
            self.log_message(f"已打开浏览器访问：{self.bilibilio_url}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开链接：{str(e)}")
            logging.error(f"链接打开失败：{str(e)}")

    def setup_ui(self):
        self.root.title("B站缓存工具箱(By.郭逍遥) v1.0")
        self.root.geometry("1200x600")
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.setup_download_tab(notebook)
        self.setup_reload_tab(notebook)
        self.setup_search_tab(notebook)
        self.setup_merge_tab(notebook)
        self.setup_settings_tab(notebook)

        log_frame = ttk.LabelFrame(self.root, text="操作日志")
        log_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_download_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="视频下载")
        frame = ttk.LabelFrame(tab, text="下载配置")
        frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(frame, text="视频URL:").grid(row=0, column=0, padx=5, sticky='w')
        self.url_entry = ttk.Entry(frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, sticky='ew')

        ttk.Label(frame, text="画质选择:").grid(row=1, column=0, padx=5, sticky='w')
        self.quality_var = tk.StringVar(value="720P")
        quality_combo = ttk.Combobox(
            frame, textvariable=self.quality_var,
            values=[q[0] for q in self.QUALITY_OPTIONS], state="readonly", width=15
        )
        quality_combo.grid(row=1, column=1, padx=5, sticky='w')

        self.collection_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="下载合集", variable=self.collection_var).grid(row=2, column=1, sticky='w')

        self.download_progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate", length=400)
        self.download_progress.grid(row=3, column=0, columnspan=2, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=5)
        self.download_btn = ttk.Button(btn_frame, text="开始下载", command=self.start_download)
        self.download_btn.pack(side=tk.LEFT, padx=5)
        self.stop_download_btn = ttk.Button(btn_frame, text="停止下载", command=self.stop_download, state="disabled")
        self.stop_download_btn.pack(side=tk.LEFT, padx=5)
        self.add_donation_link(tab)

        text_frame = ttk.Frame(frame)
        text_frame.grid(row=6, column=1, columnspan=5, pady=5)
        ttk.Label(
            text_frame,
            text="注意：AV号下载的视频有可能下载失败或者合并失败(导致视频大小为0)，\n可以去B站找到正确的BV号(原因可能是AV号获取BV号使用的B站API接口\n问题导致的不一致，但是都能正常访问)，合并错误只会在操作日志中显示",
            foreground="red"
        ).grid(row=2, column=0, columnspan=3, padx=5)

    def setup_reload_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="缓存重载")
        frame = ttk.LabelFrame(tab, text="重载配置")
        frame.pack(pady=10, padx=10, fill=tk.X)

        # 设备类型单选按钮
        device_frame = ttk.Frame(frame)
        device_frame.grid(row=0, column=0, columnspan=2, pady=5, sticky='w')

        self.device_var = tk.StringVar(value="computer")
        ttk.Radiobutton(
            device_frame, text="电脑缓存",
            variable=self.device_var,
            value="computer",
            command=self.toggle_device_input
        ).pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(
            device_frame, text="手机缓存",
            variable=self.device_var,
            value="phone",
            command=self.toggle_device_input
        ).pack(side=tk.LEFT, padx=5)

        # 手机文件选择框
        self.phone_file_frame = ttk.Frame(frame)
        self.phone_file_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')

        self.phone_file_entry = ttk.Entry(self.phone_file_frame, width=50)
        self.phone_file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(
            self.phone_file_frame,
            text="选择缓存文件",
            command=self.select_phone_file
        ).pack(side=tk.LEFT, padx=5)

        config_frame = ttk.Frame(frame)
        config_frame.grid(row=2, column=0, columnspan=3, pady=5, sticky='w')

        # 画质选择
        ttk.Label(config_frame, text="画质选择:").pack(side=tk.LEFT, padx=5)
        self.reload_quality_var = tk.StringVar(value="720P")
        quality_combo = ttk.Combobox(
            config_frame, textvariable=self.reload_quality_var,
            values=[q[0] for q in self.QUALITY_OPTIONS], state="readonly", width=12
        )
        quality_combo.pack(side=tk.LEFT, padx=5)

        # 线程数选择
        ttk.Label(config_frame, text="并发线程:").pack(side=tk.LEFT, padx=5)
        self.thread_var = tk.IntVar(value=self.config.get('thread_count', 1))
        thread_combo = ttk.Combobox(
            config_frame, textvariable=self.thread_var,
            values=[1, 2, 4, 8], state="readonly", width=4
        )
        thread_combo.pack(side=tk.LEFT, padx=5)

        self.reload_progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate", length=400)
        self.reload_progress.grid(row=3, column=0, columnspan=3, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=5)
        self.reload_btn = ttk.Button(btn_frame, text="开始重载", command=self.start_reload)
        self.reload_btn.pack(side=tk.LEFT, padx=5)
        self.stop_reload_btn = ttk.Button(btn_frame, text="停止重载", command=self.stop_reload, state="disabled")
        self.stop_reload_btn.pack(side=tk.LEFT, padx=5)
        self.add_donation_link(tab)

        text_frame = ttk.Frame(frame)
        text_frame.grid(row=6, column=1, columnspan=5, pady=5)
        ttk.Label(
            text_frame,
            text="注意：AV号下载的视频有可能下载失败或者合并失败(导致视频大小为0)，\n可以去B站找到正确的BV号(原因可能是AV号获取BV号使用的B站API接口\n问题导致的不一致，但是都能正常访问)，合并错误只会在操作日志中显示",
            foreground="red"
        ).grid(row=2, column=0, columnspan=3, padx=5)

        # 初始隐藏手机文件框
        self.phone_file_frame.grid_remove()

    def setup_merge_tab(self, notebook):
        """文件合并选项卡"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="文件合并")

        main_frame = ttk.Frame(tab)
        main_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

        # 文件选择部分
        file_frame = ttk.LabelFrame(main_frame, text="选择文件")
        file_frame.pack(fill=tk.X, pady=5)

        # 视频文件
        self.video_path = tk.StringVar()
        ttk.Label(file_frame, text="文件一:").grid(row=0, column=0, padx=5, sticky='w')
        ttk.Entry(file_frame, textvariable=self.video_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(
            file_frame,
            text="浏览",
            command=lambda: self.select_file(self.video_path, [("MP4分段文件", "*.m4s")])
        ).grid(row=0, column=2, padx=5)

        # 音频文件
        self.audio_path = tk.StringVar()
        ttk.Label(file_frame, text="文件二:").grid(row=1, column=0, padx=5, sticky='w')
        ttk.Entry(file_frame, textvariable=self.audio_path, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(
            file_frame,
            text="浏览",
            command=lambda: self.select_file(self.audio_path, [("MP4分段文件", "*.m4s")])
        ).grid(row=1, column=2, padx=5)

        # 输出设置
        output_frame = ttk.LabelFrame(main_frame, text="输出设置")
        output_frame.pack(fill=tk.X, pady=5)

        ttk.Label(output_frame, text="输出目录:").grid(row=0, column=0, padx=5, sticky='w')
        self.merge_output_entry = ttk.Entry(output_frame, width=50)
        self.merge_output_entry.grid(row=0, column=1, padx=5)
        ttk.Button(
            output_frame,
            text="浏览",
            command=lambda: self.select_dir(self.merge_output_entry)
        ).grid(row=0, column=2, padx=5)

        ttk.Label(output_frame, text="输出文件名:").grid(row=1, column=0, padx=5, sticky='w')
        self.merge_filename_entry = ttk.Entry(output_frame, width=50)
        self.merge_filename_entry.grid(row=1, column=1, padx=5)
        # 如果有默认名字可以设置
        self.merge_filename_entry.insert(0, "自定义名称")
        ttk.Label(
            output_frame,
            text="注意，会生成临时文件，合并完成后会清除掉（因为电脑缓存的m4s文件头会多九个0）",
            foreground="red"
        ).grid(row=2, column=0, columnspan=3, padx=5)

        # 合并按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        self.merge_btn = ttk.Button(
            btn_frame,
            text="开始合并",
            command=self.start_merge
        )
        self.merge_btn.pack(side=tk.LEFT, padx=10)

        self.merge_status = ttk.Label(main_frame, text="准备就绪", foreground="gray")
        self.merge_status.pack()

        self.add_donation_link(tab)

        # 初始化输出目录
        self.merge_output_entry.insert(0, self.config.get('output_dir', ''))

    def toggle_device_input(self):
        """切换设备类型显示"""
        if self.device_var.get() == "phone":
            self.phone_file_frame.grid()
        else:
            self.phone_file_frame.grid_remove()

    def select_phone_file(self):
        """选择手机缓存文件"""
        file_path = filedialog.askopenfilename(
            title="选择手机缓存文件",
            filetypes=[("Text files", "*.txt")]
        )
        if file_path:
            self.phone_file_entry.delete(0, tk.END)
            self.phone_file_entry.insert(0, file_path)

    def select_file(self, target_var, filetypes):
        """文件选择方法"""
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            target_var.set(path)

    def setup_search_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="视频搜索")
        frame = ttk.LabelFrame(tab, text="搜索配置")
        frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        search_frame = ttk.Frame(frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="关键词:").pack(side=tk.LEFT, padx=5)
        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", lambda e: self.start_search())
        ttk.Button(search_frame, text="搜索", command=self.start_search).pack(side=tk.LEFT, padx=5)

        self.search_progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate")
        self.search_progress.pack(fill=tk.X, pady=5)

        self.search_results = ttk.Treeview(frame, columns=("title", "path", "bvid"), show="headings")
        self.search_results.heading("title", text="视频标题")
        self.search_results.heading("path", text="原缓存路径")
        self.search_results.heading("bvid", text="BV号")
        self.search_results.column("title", width=400)
        self.search_results.column("path", width=300)
        self.search_results.column("bvid", width=100)
        self.search_results.pack(fill=tk.BOTH, expand=True)
        self.add_donation_link(tab)

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="打开文件夹", command=self.open_selected_folder)
        self.context_menu.add_command(label="重命名标题", command=self.rename_title)
        self.context_menu.add_command(label="删除记录", command=self.delete_record)
        self.search_results.bind("<Button-3>", self.show_context_menu)

    def setup_settings_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="系统设置")
        frame = ttk.LabelFrame(tab, text="配置管理")
        frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="缓存目录:").grid(row=0, column=0, padx=5, sticky='w')
        self.cache_entry = ttk.Entry(frame, width=50)
        self.cache_entry.grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="浏览", command=lambda: self.select_dir(self.cache_entry)).grid(row=0, column=2)

        ttk.Label(frame, text="输出目录:").grid(row=1, column=0, padx=5, sticky='w')
        self.output_entry = ttk.Entry(frame, width=50)
        self.output_entry.grid(row=1, column=1, padx=5)
        ttk.Button(frame, text="浏览", command=lambda: self.select_dir(self.output_entry)).grid(row=1, column=2)

        ttk.Label(frame, text="SESSDATA:").grid(row=2, column=0, padx=5, sticky='w')
        self.sessdata_entry = ttk.Entry(frame, width=50, show="*")
        self.sessdata_entry.grid(row=2, column=1, padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10, sticky='ew')
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5, fill=tk.X,
                                                                              expand=True)
        ttk.Button(btn_frame, text="打开下载记录", command=self.open_download_records).pack(side=tk.LEFT, padx=5,
                                                                                            fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="打开错误日志", command=self.open_error_logs).pack(side=tk.LEFT, padx=5, fill=tk.X,
                                                                                      expand=True)
        ttk.Label(
            frame,
            text="如果觉得本工具不错的话，请支持一下作者哦~(By.郭逍遥)",
            foreground="red"
        ).grid(row=4, column=0, columnspan=3, pady=(10, 0), sticky='w')

        self.cache_entry.insert(0, self.config.get('cache_root', ''))
        self.output_entry.insert(0, self.config.get('output_dir', ''))
        self.sessdata_entry.insert(0, self.config.get('sessdata', ''))
        self.add_donation_link(tab)

    def start_download(self):
        if self.download_running:
            messagebox.showwarning("警告", "当前有下载任务正在运行")
            return

        self.download_stop_event.clear()
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频URL")
            return

        if not os.path.exists(self.config['output_dir']):
            messagebox.showerror("错误", "输出目录不存在！")
            return
        if not os.access(self.config['output_dir'], os.W_OK):
            messagebox.showerror("错误", "输出目录无写入权限！")
            return

        quality = next(q[1] for q in self.QUALITY_OPTIONS if q[0] == self.quality_var.get())

        self.download_running = True
        BilibiliDownloader.start_download(
            url=url,
            quality=quality,
            is_collection=self.collection_var.get(),
            output_dir=self.config['output_dir'],
            cache_root=self.config['cache_root'],
            sessdata=self.config['sessdata'],
            progress_callback=self.update_download_progress,
            log_callback=self.log_message,
            stop_event=self.download_stop_event
        )
        self.toggle_buttons(self.download_btn, self.stop_download_btn, False)

    def start_merge(self):
        # 获取文件路径和输出目录
        video_path = self.video_path.get()
        audio_path = self.audio_path.get()
        output_dir = self.merge_output_entry.get()
        filename = self.merge_filename_entry.get().strip()

        # 校验输入
        if not all([video_path, audio_path, output_dir]):
            messagebox.showwarning("提示", "请填写完整文件路径和输出目录")
            return
        if Path(video_path).resolve() == Path(audio_path).resolve():
            messagebox.showwarning("提示", "视频和音频文件不能相同")
            return

        # 开启后台线程执行合并
        threading.Thread(target=self._do_merge, args=(video_path, audio_path, output_dir, filename)).start()

    def _do_merge(self, video_path, audio_path, output_dir, filename):
        try:
            self._set_merge_ui_state(disabled=True, text="正在合并...", color="blue")
            self.log_message("开始验证文件")
            # 验证文件存在
            for p in [video_path, audio_path]:
                if not Path(p).exists():
                    raise FileNotFoundError(f"文件不存在：{p}")

            # 生成输出路径（用用户自定义的名字）
            if filename:
                save_name = filename + ".mp4"
            else:
                save_name = "合并_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(output_dir) / save_name

            self.log_message(f"输出文件：{output_path}")

            # 调用合并
            self.log_message("开始合并中，请稍候...")
            merged_path = merge_m4s_files([video_path, audio_path], output_dir, filename)

            self.log_message(f"合并成功：{merged_path}")
            self._set_merge_ui_state(text=f"✓ 合并完成：{Path(merged_path).name}", color="green")
            messagebox.showinfo("成功", f"文件已保存到：\n{merged_path}")
        except Exception as e:
            self._set_merge_ui_state(text="合并失败", color="red")
            self.log_message(f"错误：{str(e)}")
            messagebox.showerror("错误", f"合并失败：\n{str(e)}")
        finally:
            self._set_merge_ui_state(disabled=False)

    def _set_merge_ui_state(self, disabled=False, text="准备就绪", color="gray"):
        self.merge_btn.config(state="disabled" if disabled else "normal")
        self.merge_status.config(text=text, foreground=color)
        self.root.update_idletasks()

    def log_message(self, message):
        # 假设你有一个tk.Text控件self.log_box
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def _set_merge_ui_state(self, disabled=False, text="准备就绪", color="gray"):
        """统一更新合并界面状态"""
        self.merge_btn.config(state="disabled" if disabled else "normal")
        self.merge_status.config(text=text, foreground=color)
        self.root.update_idletasks()

    def update_reload_progress(self, value):
        """更新重载进度并处理完成状态"""
        self.reload_progress['value'] = value
        if value >= 100:
            self.root.after(1000, self.reset_reload_ui)  # 1秒后重置
        self.root.update_idletasks()

    def reset_reload_ui(self):
        """重置重载界面状态"""
        self.reload_progress['value'] = 0
        self.toggle_reload_buttons(True)
        self.reload_running = False

    def update_download_progress(self, value):
        self.download_progress['value'] = value
        if value >= 100:
            self.root.after(1000, lambda: self.download_progress.configure(value=0))
        self.download_running = False

    def stop_download(self):
        self.download_stop_event.set()
        self.toggle_buttons(self.download_btn, self.stop_download_btn, True)
        self.download_progress['value'] = 0
        self.download_running = False

    def start_reload(self):
        if self.reload_running:
            messagebox.showwarning("警告", "当前有重载任务正在运行")
            return

        # 手机模式验证
        if self.device_var.get() == "phone":
            phone_file = self.phone_file_entry.get().strip()
            if not phone_file:
                messagebox.showerror("错误", "请选择手机缓存文件")
                return
            if not os.path.isfile(phone_file):
                messagebox.showerror("错误", "选择的文件不存在")
                return

        self.reload_stop_event.clear()
        quality = next(q[1] for q in self.QUALITY_OPTIONS if q[0] == self.reload_quality_var.get())

        self.reload_running = True
        self.current_reloader = CacheReloader(
            config=self.config,
            stop_event=self.reload_stop_event,
            progress_callback=lambda p: self.root.after(0, self.update_reload_progress, p),  # 修改这里
            log_callback=lambda msg: logging.getLogger('ReloadModule').info(msg),
            device_type=self.device_var.get(),
            phone_file=self.phone_file_entry.get() if self.device_var.get() == "phone" else None,
            max_threads=self.thread_var.get()
        )

        reload_thread = threading.Thread(
            target=self.current_reloader.start_reload,
            args=(quality,),
            daemon=True
        )
        reload_thread.start()
        self.toggle_reload_buttons(False)

    def toggle_reload_buttons(self, enable):
        """切换重载按钮状态"""
        self.reload_btn.config(state="normal" if enable else "disabled")
        self.stop_reload_btn.config(state="disabled" if enable else "normal")
        self.root.update_idletasks()

    def update_reload_progress(self, value):
        self.reload_progress['value'] = value
        if value >= 100:
            self.toggle_reload_buttons(True)
            self.reload_running = False
        self.root.update_idletasks()

    def stop_reload(self):
        self.reload_stop_event.set()
        if self.current_reloader:
            self.current_reloader.stop_reload()
        self.toggle_reload_buttons(True)
        self.reload_progress['value'] = 0
        self.reload_running = False

    def start_search(self):
        keyword = self.search_entry.get().strip()
        if not keyword:
            messagebox.showerror("错误", "请输入搜索关键词")
            return

        self.search_progress['value'] = 0
        self.search_results.delete(*self.search_results.get_children())

        def search_task():
            try:
                results = AdvancedSearchEngine.search_cache(
                    keyword=keyword,
                    progress_callback=lambda p: self.root.after(0, lambda: self.search_progress.configure(value=p)),
                    cache_root=self.config['cache_root']
                )
                self.root.after(0, lambda: self.display_results(results))
            except Exception as e:
                self.log_message(f"搜索错误: {str(e)}")
            finally:
                self.root.after(0, self.finish_search)

        threading.Thread(target=search_task, daemon=True).start()

    def display_results(self, results):
        for result in results:
            self.search_results.insert('', 'end', values=(result['title'], result['path'], result['bvid']))
        self.log_message(f"找到 {len(results)} 个匹配结果")

    def finish_search(self):
        self.search_progress['value'] = 100
        self.root.after(1000, lambda: self.search_progress.configure(value=0))

    def toggle_buttons(self, start_btn, stop_btn, enable):
        start_btn.config(state="normal" if enable else "disabled")
        stop_btn.config(state="disabled" if enable else "normal")
        self.root.update_idletasks()

    def log_message(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def load_config(self):
        config_path = Path('config.json')
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'cache_root': '', 'output_dir': '', 'sessdata': ''}

    def save_config(self):
        config = {
            'cache_root': self.cache_entry.get(),
            'output_dir': self.output_entry.get(),
            'sessdata': self.sessdata_entry.get(),
            'thread_count': self.thread_var.get(),
            'download_quality': next(q[1] for q in self.QUALITY_OPTIONS if q[0] == self.quality_var.get()),
            'reload_quality': next(q[1] for q in self.QUALITY_OPTIONS if q[0] == self.reload_quality_var.get())
        }
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        self.config = config
        messagebox.showinfo("成功", "配置已保存")

    def select_dir(self, entry):
        path = filedialog.askdirectory()
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def open_download_records(self):
        record_file = Path(__file__).parent / "downloaded.txt"
        try:
            if record_file.exists():
                if os.name == 'nt':
                    os.startfile(record_file)
                else:
                    opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                    subprocess.call([opener, str(record_file)])
            else:
                messagebox.showinfo("提示", "暂无下载记录")
        except Exception as e:
            messagebox.showerror("错误", f"打开文件失败：{str(e)}")

    def open_error_logs(self):
        error_file = Path(__file__).parent / "errors.log"
        try:
            if error_file.exists():
                if os.name == 'nt':
                    os.startfile(error_file)
                else:
                    opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                    subprocess.call([opener, str(error_file)])
            else:
                messagebox.showinfo("提示", "暂无错误记录")
        except Exception as e:
            messagebox.showerror("错误", f"打开文件失败：{str(e)}")

    def open_selected_folder(self):
        selected = self.search_results.selection()
        if not selected:
            return
        try:
            folder_name = self.search_results.item(selected[0])['values'][1]
            cache_root = self.config.get('cache_root', '')
            full_path = Path(cache_root) / folder_name

            if full_path.exists():
                os.startfile(str(full_path))  # 打开缓存目录
            else:
                messagebox.showerror("错误", f"缓存目录不存在：{full_path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开失败：{str(e)}")
            logging.error(f"打开目录失败：{str(e)}")

    def rename_title(self):
        selected = self.search_results.selection()
        if not selected:
            return

        item = self.search_results.item(selected[0])
        bvid = item['values'][2]
        old_title = item['values'][0]

        new_title = simpledialog.askstring(
            "重命名标题",
            "请输入新的视频标题：",
            initialvalue=old_title,
            parent=self.root
        )

        if new_title and new_title != old_title:
            try:
                record_file = Path(__file__).parent / "downloaded.txt"
                updated_lines = []
                with open(record_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(bvid):
                            parts = line.strip().split("|")
                            if len(parts) >= 3:
                                updated_line = f"{parts[0]}|{parts[1]}|{new_title}\n"
                                updated_lines.append(updated_line)
                            else:
                                updated_lines.append(line)
                        else:
                            updated_lines.append(line)
                with open(record_file, "w", encoding="utf-8") as f:
                    f.writelines(updated_lines)
                self.search_results.item(selected[0], values=(new_title, item['values'][1], bvid))
                logging.getLogger("SearchModule").info(f"成功重命名：{bvid} -> {new_title}")
            except Exception as e:
                messagebox.showerror("错误", f"重命名失败：{str(e)}")
                logging.getLogger("SearchModule").error(f"重命名失败：{str(e)}")

    def delete_record(self):
        selected = self.search_results.selection()
        if not selected:
            return

        bvid = self.search_results.item(selected[0])['values'][2]
        if not messagebox.askyesno("确认删除", f"确定要删除 BV号 {bvid} 的记录吗？", parent=self.root):
            return

        try:
            record_file = Path(__file__).parent / "downloaded.txt"
            remaining_lines = []
            with open(record_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.startswith(bvid):
                        remaining_lines.append(line)
            with open(record_file, "w", encoding="utf-8") as f:
                f.writelines(remaining_lines)
            self.search_results.delete(selected[0])
            logging.getLogger("SearchModule").info(f"成功删除记录：{bvid}")
        except Exception as e:
            messagebox.showerror("错误", f"删除失败：{str(e)}")
            logging.getLogger("SearchModule").error(f"删除记录失败：{str(e)}")

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def start_log_poller(self):
        def poller():
            while True:
                try:
                    msg = self.log_queue.get(timeout=0.1)
                    self.log_message(msg)
                except queue.Empty:
                    if not self.root.winfo_exists():
                        break

        threading.Thread(target=poller, daemon=True).start()

    def on_close(self):
        self.download_stop_event.set()
        self.reload_stop_event.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BilibiliToolkitGUI(root)
    root.mainloop()
