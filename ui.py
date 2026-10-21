import customtkinter as ctk
import os
import shutil
from tkinter import messagebox
from core import MinecraftLauncherCore

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DnDWrapper = TkinterDnD.DnDWrapper
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    DnDWrapper = object

# 设置全局外观主题
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TrashLauncherApp(ctk.CTk, DnDWrapper):
    def __init__(self):
        super().__init__()
        if TkinterDnD is not None:
            self.TkdndVersion = TkinterDnD._require(self)
        
        # 窗口基础设置
        self.title("TrashLauncher v1.0 - 垃圾启动器")
        self.geometry("850x520")
        self.minsize(700, 400)
        
        # 实例化核心逻辑类
        self.core = MinecraftLauncherCore()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 全局设置的运行时状态
        defaults = {
            "java_path": self.detect_java_path(),
            "version_isolation": True,
            "auto_memory": False,
            "memory": 4096,
            "launcher_visibility": "游戏结束后重新打开",
            "resolution_width": 1280,
            "resolution_height": 720,
            "fullscreen": False,
            "show_log": True,
            "process_priority": "高",
            "server_address": "",
            "jvm_args": "",
            "game_args": "",
            "pre_launch_command": "",
            "post_exit_command": "",
            "environment": "",
            "download_source": "原版",
            "download_manifest_url": "",
            "download_concurrency": 8,
        }
        self.default_settings = dict(defaults)
        self.settings = self.core.load_config(self.default_settings)
        self.java_installations = self.core.discover_java_installations()
        self.java_expanded = True
        
        # 跟踪侧边栏折叠状态
        self.is_sidebar_expanded = True

        # 网格布局：左侧菜单列，右侧主界面
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 构建界面组件
        self.create_sidebar()
        self.create_main_content()

        self.settings_frame = None
        self._closing = False
        self._config_error_poll_id = self.after(100, self.poll_config_errors)

    def create_sidebar(self):
        """ 创建左侧菜单栏（修复内边距和对齐偏移） """
        self.sidebar_frame = ctk.CTkFrame(self, width=160, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False) # 防止内部组件撑开宽度

        # 顶部的折叠切换按钮 [≡]
        self.toggle_btn = ctk.CTkButton(
            self.sidebar_frame, 
            text="≡", 
            width=40, 
            font=("Microsoft YaHei UI", 16),
            command=self.toggle_sidebar
        )
        self.toggle_btn.pack(pady=15, padx=15, anchor="w")

        # 菜单选项按钮（微调 padx 和 anchor，解决偏移问题）
        btn_configs = [
            ("📁 版本管理", self.on_menu_versions),
            ("🌐 下载资源", self.on_menu_downloads),
            ("⚙️ 游戏设置", self.on_menu_settings),
            ("🗑️ 关于项目", self.on_menu_about)
        ]

        self.menu_buttons = []
        for text, cmd in btn_configs:
            btn = ctk.CTkButton(
                self.sidebar_frame, 
                text=text, 
                anchor="w", 
                fg_color="transparent", 
                hover_color=("#dbdbdb", "#2b2b2b"),
                font=("Microsoft YaHei UI", 12),  # 显式指定标准字体，解决字体发粗/加重问题
                command=cmd
            )
            btn.pack(pady=6, padx=12, fill="x")
            self.menu_buttons.append(btn)

    def create_main_content(self):
        """ 创建右侧主界面 """
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # 顶部：版本选择区域
        self.top_bar_frame = ctk.CTkFrame(self.main_frame, fg_color=("#f0f0f0", "#2b2b2b"))
        self.top_bar_frame.pack(fill="x", pady=(0, 15), padx=5)

        self.version_label = ctk.CTkLabel(
            self.top_bar_frame, 
            text="当前版本: Minecraft 1.20.4", 
            font=("Microsoft YaHei UI", 13)
        )
        self.version_label.pack(side="left", padx=15, pady=12)

        self.change_version_btn = ctk.CTkButton(
            self.top_bar_frame, 
            text="更换版本", 
            width=90, 
            font=("Microsoft YaHei UI", 12),
            command=self.on_change_version_click
        )
        self.change_version_btn.pack(side="right", padx=15, pady=12)

        # 中部：宣传图/动态背景区域
        self.banner_frame = ctk.CTkFrame(self.main_frame, fg_color=("#d1d1d1", "#1a1a1a"), height=220)
        self.banner_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.banner_frame.pack_propagate(False)

        self.banner_text = ctk.CTkLabel(
            self.banner_frame, 
            text="[ TrashLauncher 动态宣传图/背景区域 ]\n(这里以后可以放游戏壁纸或更新公告)", 
            font=("Microsoft YaHei UI", 13),
            text_color=("gray50", "gray50")
        )
        self.banner_text.place(relx=0.5, rely=0.5, anchor="center")

        # 下部：玩家信息与内存设置栏
        self.info_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.info_bar.pack(fill="x", pady=10, padx=5)

        self.player_info_lbl = ctk.CTkLabel(self.info_bar, text="玩家名: TrashPlayer (离线模式)", font=("Microsoft YaHei UI", 12))
        self.player_info_lbl.pack(side="left")

        self.memory_lbl = ctk.CTkLabel(self.info_bar, text="内存分配: 4096 MB", font=("Microsoft YaHei UI", 12))
        self.memory_lbl.pack(side="right")

        # 底部：启动大按钮
        self.launch_btn = ctk.CTkButton(
            self.main_frame, 
            text="启 动 游 戏", 
            height=50, 
            font=("Microsoft YaHei UI", 16, "bold"),
            fg_color="#2fa572", 
            hover_color="#248f5e",
            command=self.on_launch_click
        )
        self.launch_btn.pack(fill="x", pady=(5, 5), padx=5)

    def toggle_sidebar(self):
        """ 侧边栏折叠/展开动画逻辑 """
        if self.is_sidebar_expanded:
            self.sidebar_frame.configure(width=60)
            self.menu_buttons[0].configure(text="📁")
            self.menu_buttons[1].configure(text="🌐")
            self.menu_buttons[2].configure(text="⚙️")
            self.menu_buttons[3].configure(text="🗑️")
            self.is_sidebar_expanded = False
        else:
            self.sidebar_frame.configure(width=160)
            self.menu_buttons[0].configure(text="📁 版本管理")
            self.menu_buttons[1].configure(text="🌐 下载资源")
            self.menu_buttons[2].configure(text="⚙️ 游戏设置")
            self.menu_buttons[3].configure(text="🗑️ 关于项目")
            self.is_sidebar_expanded = True

    # --- 按钮对应的事件处理（调用 Core 逻辑） ---

    def on_change_version_click(self):
        """ 点击更换版本按钮 """
        new_ver = self.core.change_version()
        self.version_label.configure(text=f"当前版本: Minecraft {new_ver}")

    def on_launch_click(self):
        """ 点击启动游戏大按钮 """
        self.core.launch_game(
            player_name="TrashPlayer",
            version_id="1.20.4",
            max_memory=str(self.settings["memory"]),
        )

    def on_menu_versions(self):
        print("[UI] 切换到: 版本管理视图")

    def on_menu_downloads(self):
        print("[UI] 切换到: 下载资源视图")

    def on_menu_settings(self):
        self.show_settings()

    def on_menu_about(self):
        print("[UI] 切换到: 关于项目视图")

    def show_settings(self):
        """显示全局设置，并把高级设置直接放在同一页下方。"""
        self.main_frame.grid_remove()
        self.sidebar_frame.grid_remove()
        if self.settings_frame is None:
            self.create_settings_view()
        self.settings_frame.grid()

    def create_settings_view(self):
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.settings_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.settings_frame.grid_remove()
        self.settings_frame.grid_rowconfigure(1, weight=1)
        self.settings_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.settings_frame, height=62, corner_radius=0, fg_color="#3f73aa")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkButton(
            header, text="←", width=48, height=42, font=("Microsoft YaHei UI", 26),
            fg_color="transparent", hover_color="#315f91", command=self.show_home,
        ).pack(side="left", padx=(10, 2), pady=10)
        ctk.CTkLabel(
            header, text="设置", font=("Microsoft YaHei UI", 20, "bold"), text_color="white",
        ).pack(side="left", padx=8)

        self.settings_frame.grid_columnconfigure(0, weight=0, minsize=190)
        self.settings_frame.grid_columnconfigure(1, weight=1)
        settings_nav = ctk.CTkFrame(self.settings_frame, corner_radius=0, fg_color=("#f1f4f8", "#252b31"))
        settings_nav.grid(row=1, column=0, sticky="nsew")
        settings_nav.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            settings_nav, text="设置", anchor="w", font=("Microsoft YaHei UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 14))
        self.settings_game_button = ctk.CTkButton(
            settings_nav, text="游戏设置", anchor="w", height=42,
            command=lambda: self.show_settings_page("game"),
        )
        self.settings_game_button.grid(row=1, column=0, sticky="ew", padx=12, pady=5)
        self.settings_launcher_button = ctk.CTkButton(
            settings_nav, text="启动器设置", anchor="w", height=42,
            fg_color="transparent", text_color=("#333333", "#dddddd"),
            hover_color=("#dce8f5", "#343d46"),
            command=lambda: self.show_settings_page("launcher"),
        )
        self.settings_launcher_button.grid(row=2, column=0, sticky="ew", padx=12, pady=5)

        self.settings_pages = ctk.CTkFrame(self.settings_frame, corner_radius=0, fg_color="transparent")
        self.settings_pages.grid(row=1, column=1, sticky="nsew")
        self.settings_pages.grid_rowconfigure(0, weight=1)
        self.settings_pages.grid_columnconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(self.settings_pages, fg_color=("#e8eef5", "#202830"))
        self.game_settings_page = content
        content.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        content.grid_columnconfigure(0, weight=0, minsize=220)
        content.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            content, text="全局游戏设置", anchor="w",
            font=("Microsoft YaHei UI", 18, "bold"), text_color="#2f6da8",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=22, pady=(20, 8))

        self.add_java_setting(content, 1)
        self.add_setting_switch(content, 2, "版本隔离", "version_isolation", "为每个游戏版本使用独立文件夹")
        self.add_memory_setting(content, 3)
        self.add_setting_combo(
            content, 4, "启动器可见性", "launcher_visibility",
            ["游戏结束后重新打开", "游戏启动后隐藏", "始终保持显示"],
        )
        self.add_resolution_setting(content, 5)
        self.add_setting_switch(content, 6, "查看日志", "show_log", "启动时显示游戏日志")
        self.add_setting_combo(content, 7, "进程优先级", "process_priority", ["高", "普通", "低"])
        self.add_setting_entry(content, 8, "服务器地址", "server_address", "默认，启动游戏后可直接进入对应服务器")

        ctk.CTkLabel(
            content, text="高级设置", anchor="w",
            font=("Microsoft YaHei UI", 18, "bold"), text_color="#2f6da8",
        ).grid(row=9, column=0, columnspan=2, sticky="w", padx=22, pady=(28, 8))
        advanced = ctk.CTkFrame(content, fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        advanced.grid(row=10, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 24))
        advanced.grid_columnconfigure(1, weight=1)
        self.add_setting_entry(advanced, 0, "游戏参数", "game_args", "例如：--demo")
        self.add_setting_entry(advanced, 1, "游戏启动前执行命令", "pre_launch_command", "可留空")
        self.add_setting_entry(advanced, 2, "游戏结束后执行命令", "post_exit_command", "可留空")
        self.add_setting_entry(advanced, 3, "Java 虚拟机参数", "jvm_args", "例如：-XX:+UseG1GC")
        self.add_setting_entry(advanced, 4, "环境变量", "environment", "格式：名称=值，每行一个")

        ctk.CTkLabel(
            advanced, text="高级参数会直接影响游戏启动。请确认内容正确后再启动游戏。",
            anchor="w", text_color="#966b12", font=("Microsoft YaHei UI", 12),
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))

        ctk.CTkButton(
            content, text="重置设置", width=120, height=38,
            fg_color="#a94442", hover_color="#873735", command=self.reset_settings,
        ).grid(row=11, column=0, columnspan=2, sticky="e", padx=22, pady=(0, 28))

        self.create_launcher_settings_page()
        self.show_settings_page("game")

    def create_launcher_settings_page(self):
        page = ctk.CTkScrollableFrame(self.settings_pages, fg_color=("#e8eef5", "#202830"))
        page.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        page.grid_columnconfigure(0, weight=0, minsize=260)
        page.grid_columnconfigure(1, weight=1)
        self.launcher_settings_page = page

        ctk.CTkLabel(
            page, text="启动器设置", anchor="w",
            font=("Microsoft YaHei UI", 18, "bold"), text_color="#2f6da8",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=22, pady=(20, 8))
        ctk.CTkLabel(
            page, text="下载设置", anchor="w",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=22, pady=(18, 8))

        ctk.CTkLabel(page, text="版本下载源", anchor="w").grid(
            row=2, column=0, sticky="w", padx=18, pady=12,
        )
        source = ctk.CTkComboBox(
            page, height=38, values=["原版", "BMCLAPI", "自定义"],
            command=self.update_download_source,
        )
        source.set(self.settings["download_source"])
        source.grid(row=2, column=1, sticky="ew", padx=(12, 18), pady=8)
        self.download_source_combo = source

        ctk.CTkLabel(page, text="版本清单地址", anchor="w").grid(
            row=3, column=0, sticky="w", padx=18, pady=12,
        )
        self.download_manifest_entry = ctk.CTkEntry(
            page, height=38, placeholder_text="自定义 version_manifest_v2.json 路径或 URL",
        )
        self.download_manifest_entry.insert(0, self.get_download_manifest_url())
        self.download_manifest_entry.grid(row=3, column=1, sticky="ew", padx=(12, 18), pady=8)
        self.download_manifest_entry.bind("<FocusOut>", lambda _event: self.update_custom_manifest_url())
        self.update_manifest_entry_state()

        ctk.CTkLabel(
            page, text="原版：官方 Mojang 版本清单\nBMCLAPI：国内镜像版本清单",
            anchor="w", justify="left", text_color="gray60",
        ).grid(row=4, column=1, sticky="w", padx=(12, 18), pady=(0, 20))

        ctk.CTkLabel(
            page, text="下载并发数", anchor="w",
            font=("Microsoft YaHei UI", 13),
        ).grid(row=5, column=0, sticky="w", padx=18, pady=12)
        concurrency_frame = ctk.CTkFrame(page, fg_color="transparent")
        concurrency_frame.grid(row=5, column=1, sticky="ew", padx=(12, 18), pady=8)
        concurrency_frame.grid_columnconfigure(0, weight=1)
        self.download_concurrency_slider = ctk.CTkSlider(
            concurrency_frame, from_=1, to=256, number_of_steps=255,
            command=self.update_download_concurrency,
        )
        self.download_concurrency_slider.set(self.settings["download_concurrency"])
        self.download_concurrency_slider.grid(row=0, column=0, sticky="ew", padx=(0, 18))
        self.download_concurrency_entry = ctk.CTkEntry(
            concurrency_frame, width=100, height=38, justify="right",
        )
        self.download_concurrency_entry.insert(0, str(self.settings["download_concurrency"]))
        self.download_concurrency_entry.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(concurrency_frame, text="个", width=28, anchor="w").grid(
            row=0, column=2, sticky="w", padx=(8, 0),
        )
        self.download_concurrency_entry.bind(
            "<Return>", lambda _event: self.update_download_concurrency_from_entry(),
        )
        self.download_concurrency_entry.bind(
            "<FocusOut>", lambda _event: self.update_download_concurrency_from_entry(),
        )

        ctk.CTkLabel(
            page, text="并发数范围：1–256，数值越大下载速度越快，但占用的网络和系统资源也越多。",
            anchor="w", text_color="#966b12",
        ).grid(row=6, column=0, columnspan=2, sticky="ew", padx=22, pady=(8, 28))

    def show_settings_page(self, page_name):
        if page_name == "game":
            self.launcher_settings_page.grid_remove()
            self.game_settings_page.grid()
            self.settings_game_button.configure(fg_color=("#3f73aa", "#3f73aa"), text_color="white")
            self.settings_launcher_button.configure(fg_color="transparent", text_color=("#333333", "#dddddd"))
        else:
            self.game_settings_page.grid_remove()
            self.launcher_settings_page.grid()
            self.settings_launcher_button.configure(fg_color=("#3f73aa", "#3f73aa"), text_color="white")
            self.settings_game_button.configure(fg_color="transparent", text_color=("#333333", "#dddddd"))

    def get_download_manifest_url(self):
        source = self.settings["download_source"]
        if source == "BMCLAPI":
            return "https://bmclapi2.bangbang93.com/mc/game/version_manifest_v2.json"
        if source == "自定义":
            return self.settings["download_manifest_url"]
        return "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

    def update_download_source(self, source):
        self.update_setting("download_source", source)
        if source != "自定义":
            self.set_manifest_entry_value(self.get_download_manifest_url(), editable=False)
        else:
            self.set_manifest_entry_value(self.settings["download_manifest_url"], editable=True)

    def update_custom_manifest_url(self):
        if self.settings["download_source"] == "自定义":
            self.update_setting("download_manifest_url", self.download_manifest_entry.get().strip())

    def set_manifest_entry_value(self, value, editable):
        self.download_manifest_entry.configure(state="normal")
        self.download_manifest_entry.delete(0, "end")
        self.download_manifest_entry.insert(0, value)
        self.download_manifest_entry.configure(state="normal" if editable else "readonly")

    def update_manifest_entry_state(self):
        self.set_manifest_entry_value(
            self.get_download_manifest_url(), self.settings["download_source"] == "自定义",
        )

    def update_download_concurrency(self, value):
        concurrency = max(1, min(256, int(round(value))))
        self.update_setting("download_concurrency", concurrency)
        self.download_concurrency_entry.delete(0, "end")
        self.download_concurrency_entry.insert(0, str(concurrency))

    def update_download_concurrency_from_entry(self):
        try:
            concurrency = int(self.download_concurrency_entry.get().strip())
        except ValueError:
            concurrency = self.settings["download_concurrency"]
        if concurrency < 1 or concurrency > 256:
            concurrency = self.settings["download_concurrency"]
        self.update_setting("download_concurrency", concurrency)
        self.download_concurrency_slider.set(concurrency)
        self.download_concurrency_entry.delete(0, "end")
        self.download_concurrency_entry.insert(0, str(concurrency))

    def poll_config_errors(self):
        error_event = self.core.get_config_error()
        if error_event is not None and not self._closing:
            retry = messagebox.askretrycancel(
                "保存失败",
                f"配置保存失败，已尝试 3 次。\n{error_event['error']}",
            )
            if retry:
                self.core.retry_config_save(self.settings)
            else:
                self.core.cancel_config_save()
                self.restore_settings_from_config()
        if not self._closing:
            self._config_error_poll_id = self.after(100, self.poll_config_errors)

    def restore_settings_from_config(self):
        self.settings = self.core.load_config(self.default_settings)
        if self.settings_frame is not None:
            was_visible = bool(self.settings_frame.grid_info())
            self.settings_frame.destroy()
            self.settings_frame = None
            if was_visible:
                self.create_settings_view()
                self.settings_frame.grid()

    def add_setting_entry(self, parent, row, label, key, placeholder):
        ctk.CTkLabel(parent, text=label, anchor="w", font=("Microsoft YaHei UI", 13)).grid(
            row=row, column=0, sticky="w", padx=18, pady=10,
        )
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, height=38)
        if self.settings[key]:
            entry.insert(0, str(self.settings[key]))
        entry.grid(row=row, column=1, sticky="ew", padx=(12, 18), pady=8)
        entry.bind("<FocusOut>", lambda _event, field=key, widget=entry: self.update_setting(field, widget.get()))
        if key == "java_path":
            self.java_path_entry = entry
            self.register_java_drop_target(entry)

    def add_java_setting(self, parent, row):
        ctk.CTkLabel(parent, text="Java 路径", anchor="w", font=("Microsoft YaHei UI", 13)).grid(
            row=row, column=0, sticky="nw", padx=18, pady=12,
        )
        panel = ctk.CTkFrame(parent, fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        panel.grid(row=row, column=1, sticky="ew", padx=(12, 18), pady=8)
        panel.grid_columnconfigure(0, weight=1)

        current = self.settings["java_path"] or "自动选择合适的 Java"
        self.java_header = ctk.CTkButton(
            panel, text=f"{current}  {'▲' if self.java_expanded else '▼'}", anchor="w",
            height=38, fg_color=("#f2f2f2", "#34383b"), text_color=("#333333", "#dddddd"),
            hover_color=("#e5e5e5", "#41464a"), command=self.toggle_java_options,
        )
        self.java_header.grid(row=0, column=0, sticky="ew")
        self.java_options = ctk.CTkFrame(panel, fg_color="transparent")
        self.java_options.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.java_options.grid_columnconfigure(1, weight=1)
        self.java_choice = ctk.StringVar(value=self.settings["java_path"] or "auto")

        self.add_java_radio("auto", "自动选择合适的 Java", "", 0)
        for index, installation in enumerate(self.java_installations, start=1):
            self.add_java_radio(
                installation["path"], installation["version"] + "（64 位）", installation["path"], index,
            )
        custom_row = len(self.java_installations) + 1
        self.add_java_radio("custom", "自定义", "", custom_row)
        self.java_custom_entry = ctk.CTkEntry(self.java_options, placeholder_text="拖入或输入 java.exe 路径", height=34)
        self.java_custom_entry.grid(row=custom_row, column=1, sticky="ew", padx=(12, 0), pady=5)
        self.java_custom_entry.bind("<FocusOut>", lambda _event: self.apply_custom_java())
        self.register_java_drop_target(self.java_custom_entry)
        if self.settings["java_path"] and not any(item["path"] == self.settings["java_path"] for item in self.java_installations):
            self.java_choice.set("custom")
            self.java_custom_entry.insert(0, self.settings["java_path"])
        if not self.java_expanded:
            self.java_options.grid_remove()

    def add_java_radio(self, value, label, path, row):
        ctk.CTkRadioButton(
            self.java_options, text=label, variable=self.java_choice, value=value,
            command=lambda selected=value, selected_path=path: self.select_java(selected, selected_path),
        ).grid(row=row, column=0, sticky="w", padx=10, pady=5)
        if path:
            path_frame = ctk.CTkFrame(self.java_options, fg_color="transparent")
            path_frame.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
            path_frame.grid_columnconfigure(0, weight=1)
            path_entry = ctk.CTkEntry(path_frame, height=28, border_width=0, text_color="gray60")
            path_entry.insert(0, path)
            path_entry.configure(state="readonly")
            path_entry.grid(row=0, column=0, sticky="ew")
            path_scroll = ctk.CTkScrollbar(
                path_frame, orientation="horizontal", command=path_entry._entry.xview, height=10,
            )
            path_scroll.grid(row=1, column=0, sticky="ew", pady=(2, 0))
            path_entry.configure(xscrollcommand=path_scroll.set)

    def toggle_java_options(self):
        self.java_expanded = not self.java_expanded
        if self.java_expanded:
            self.java_options.grid()
        else:
            self.java_options.grid_remove()
        current = self.settings["java_path"] or "自动选择合适的 Java"
        self.java_header.configure(text=f"{current}  {'▲' if self.java_expanded else '▼'}")

    def select_java(self, selected, path):
        if selected == "auto":
            path = self.java_installations[0]["path"] if self.java_installations else ""
        elif selected == "custom" and not path:
            return
        self.update_setting("java_path", path)
        current = path or "自动选择合适的 Java"
        self.java_header.configure(text=f"{current}  {'▲' if self.java_expanded else '▼'}")

    def apply_custom_java(self):
        path = self.java_custom_entry.get().strip()
        if path:
            self.java_choice.set("custom")
            self.select_java("custom", path)

    def register_java_drop_target(self, entry):
        if DND_FILES is not None:
            entry.drop_target_register(DND_FILES)
            entry.dnd_bind("<<Drop>>", self.on_java_drop)

    def on_java_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if not paths:
            return
        path = os.path.normpath(paths[0])
        if os.path.isdir(path):
            candidate = os.path.join(path, "bin", "java.exe")
            if os.path.isfile(candidate):
                path = candidate
        if os.path.isfile(path) and os.path.basename(path).lower() in {"java.exe", "java"}:
            self.java_custom_entry.delete(0, "end")
            self.java_custom_entry.insert(0, path)
            self.select_java("custom", path)
            self.java_choice.set("custom")

    @staticmethod
    def detect_java_path():
        java_path = shutil.which("java")
        if java_path:
            return os.path.normpath(java_path)
        program_files = os.environ.get("ProgramFiles", "")
        java_root = os.path.join(program_files, "Java")
        if os.path.isdir(java_root):
            for name in sorted(os.listdir(java_root), reverse=True):
                candidate = os.path.join(java_root, name, "bin", "java.exe")
                if os.path.isfile(candidate):
                    return candidate
        return ""

    def add_setting_switch(self, parent, row, label, key, description):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=6)
        frame.grid_columnconfigure(0, weight=1)
        text = ctk.CTkLabel(frame, text=f"{label}\n{description}", anchor="w", justify="left")
        text.grid(row=0, column=0, sticky="w")
        switch = ctk.CTkSwitch(frame, text="", command=lambda field=key, widget=None: self.update_setting(field, bool(switch.get())))
        switch.grid(row=0, column=1, padx=12)
        if self.settings[key]:
            switch.select()

    def add_setting_combo(self, parent, row, label, key, values):
        ctk.CTkLabel(parent, text=label, anchor="w", font=("Microsoft YaHei UI", 13)).grid(
            row=row, column=0, sticky="w", padx=18, pady=10,
        )
        combo = ctk.CTkComboBox(parent, values=values, height=38, command=lambda value: self.update_setting(key, value))
        combo.set(self.settings[key])
        combo.grid(row=row, column=1, sticky="ew", padx=(12, 18), pady=8)

    def add_memory_setting(self, parent, row):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=8)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="游戏内存", anchor="w").grid(row=0, column=0, sticky="w")
        slider = ctk.CTkSlider(frame, from_=1024, to=16384, command=self.update_memory)
        slider.set(self.settings["memory"])
        self.memory_slider = slider
        slider.grid(row=0, column=1, sticky="ew", padx=18)
        self.memory_entry = ctk.CTkEntry(frame, width=110, height=38, justify="right")
        self.memory_entry.insert(0, str(self.settings["memory"]))
        self.memory_entry.grid(row=0, column=2, sticky="e")
        ctk.CTkLabel(frame, text="MB", width=36, anchor="w").grid(row=0, column=3, sticky="w", padx=(8, 0))
        self.memory_entry.bind("<Return>", lambda _event: self.update_memory_from_entry())
        self.memory_entry.bind("<FocusOut>", lambda _event: self.update_memory_from_entry())

    def add_resolution_setting(self, parent, row):
        ctk.CTkLabel(parent, text="游戏窗口分辨率", anchor="w").grid(row=row, column=0, sticky="w", padx=18, pady=10)
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="e", padx=18, pady=8)
        width = ctk.CTkEntry(frame, width=90, height=38)
        width.insert(0, str(self.settings["resolution_width"]))
        width.pack(side="left")
        ctk.CTkLabel(frame, text=" × ").pack(side="left", padx=6)
        height = ctk.CTkEntry(frame, width=90, height=38)
        height.insert(0, str(self.settings["resolution_height"]))
        height.pack(side="left")
        fullscreen = ctk.CTkCheckBox(frame, text="全屏", command=lambda: self.update_setting("fullscreen", bool(fullscreen.get())))
        fullscreen.pack(side="left", padx=(14, 0))
        width.bind("<FocusOut>", lambda _event: self.update_setting("resolution_width", width.get()))
        height.bind("<FocusOut>", lambda _event: self.update_setting("resolution_height", height.get()))

    def update_setting(self, key, value):
        self.settings[key] = value
        self.core.enqueue_config_save(self.settings)

    def update_memory(self, value):
        memory = int(round(value))
        self.update_setting("memory", memory)
        self.memory_entry.delete(0, "end")
        self.memory_entry.insert(0, str(memory))

    def update_memory_from_entry(self):
        try:
            memory = int(self.memory_entry.get().strip())
        except ValueError:
            memory = self.settings["memory"]
        if memory < 1024 or memory > 16384:
            memory = self.settings["memory"]
        self.settings["memory"] = memory
        self.core.enqueue_config_save(self.settings)
        self.memory_slider.set(memory)
        self.memory_entry.delete(0, "end")
        self.memory_entry.insert(0, str(memory))

    def reset_settings(self):
        confirmed = messagebox.askyesno("重置设置", "确定要删除 config.json 并恢复默认设置吗？")
        if not confirmed:
            return
        self.core.reset_config()
        self.settings_frame.destroy()
        self.settings_frame = None
        defaults = {
            "java_path": self.detect_java_path(),
            "version_isolation": True,
            "auto_memory": False,
            "memory": 4096,
            "launcher_visibility": "游戏结束后重新打开",
            "resolution_width": 1280,
            "resolution_height": 720,
            "fullscreen": False,
            "show_log": True,
            "process_priority": "高",
            "server_address": "",
            "jvm_args": "",
            "game_args": "",
            "pre_launch_command": "",
            "post_exit_command": "",
            "environment": "",
            "download_source": "原版",
            "download_manifest_url": "",
            "download_concurrency": 8,
        }
        self.default_settings = dict(defaults)
        self.settings = self.core.load_config(self.default_settings)
        self.java_installations = self.core.discover_java_installations()
        self.create_settings_view()
        self.settings_frame.grid()

    def show_home(self):
        self.settings_frame.grid_remove()
        self.sidebar_frame.grid()
        self.main_frame.grid()

    def on_close(self):
        self._closing = True
        if hasattr(self, "_config_error_poll_id"):
            self.after_cancel(self._config_error_poll_id)
        self.core.close()
        self.destroy()