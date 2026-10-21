import os
import json
import re
import shutil
import subprocess
import sys
import time
from queue import Empty, Queue
from threading import Event, Thread

class MinecraftLauncherCore:
    def __init__(self, minecraft_dir=None):
        # 自动获取默认的 .minecraft 路径
        if minecraft_dir is None:
            self.minecraft_dir = os.path.join(os.environ.get('APPDATA', ''), '.minecraft')
        else:
            self.minecraft_dir = minecraft_dir
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self._config_queue = Queue()
        self._config_errors = Queue()
        self._config_resume = Event()
        self._config_resume.set()
        self._config_writer_running = True
        self._config_thread = Thread(target=self._config_worker, name="config-writer", daemon=True)
        self._config_thread.start()

    def load_config(self, defaults):
        settings = dict(defaults)
        try:
            with open(self.config_path, "r", encoding="utf-8") as config_file:
                saved_settings = json.load(config_file)
            if isinstance(saved_settings, dict):
                settings.update({key: value for key, value in saved_settings.items() if key in settings})
        except (OSError, json.JSONDecodeError):
            pass
        return settings

    def save_config(self, settings):
        self._write_config(settings)

    def enqueue_config_save(self, settings):
        """把配置快照交给后台线程，避免阻塞 UI 线程。"""
        if self._config_writer_running:
            self._config_queue.put(dict(settings))

    def get_config_error(self):
        try:
            return self._config_errors.get_nowait()
        except Empty:
            return None

    def retry_config_save(self, settings):
        self._discard_pending_config()
        self.enqueue_config_save(settings)
        self._config_resume.set()

    def cancel_config_save(self):
        self._discard_pending_config()
        self._config_resume.set()

    def _discard_pending_config(self):
        while True:
            try:
                self._config_queue.get_nowait()
            except Empty:
                return
            else:
                self._config_queue.task_done()

    def _config_worker(self):
        while True:
            settings = self._config_queue.get()
            failed = None
            try:
                if settings is None:
                    return
                for attempt in range(3):
                    try:
                        self._write_config(settings)
                        failed = None
                        break
                    except OSError as error:
                        failed = error
                        if attempt < 2:
                            time.sleep(0.05)
                if failed is not None:
                    self._config_errors.put({"settings": settings, "error": failed})
                    self._config_resume.clear()
            finally:
                self._config_queue.task_done()
            if failed is not None:
                self._config_resume.wait()

    def _write_config(self, settings):
        temporary_path = f"{self.config_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as config_file:
            json.dump(settings, config_file, ensure_ascii=False, indent=4)
        os.replace(temporary_path, self.config_path)

    def close(self):
        if not self._config_writer_running:
            return
        self._config_writer_running = False
        self._discard_pending_config()
        self._config_resume.set()
        self._config_queue.put(None)
        self._config_queue.join()
        self._config_thread.join(timeout=2)

    def reset_config(self):
        self.cancel_config_save()
        self._config_queue.join()
        try:
            os.remove(self.config_path)
        except FileNotFoundError:
            pass

    @staticmethod
    def discover_java_installations():
        """扫描 PATH、常见安装目录和 Windows 注册表中的 Java。"""
        candidates = []

        java_on_path = shutil.which("java")
        if java_on_path:
            candidates.append(java_on_path)

        roots = []
        for variable in ("ProgramFiles", "ProgramW6982", "ProgramFiles(x86)"):
            value = os.environ.get(variable)
            if value:
                roots.extend([
                    os.path.join(value, "Java"),
                    os.path.join(value, "Eclipse Adoptium"),
                    os.path.join(value, "Microsoft"),
                    os.path.join(value, "Amazon Corretto"),
                    os.path.join(value, "BellSoft"),
                    os.path.join(value, "Zulu"),
                ])

        for drive in "CDEFGHIJ":
            roots.extend([
                f"{drive}:\\Program Files\\Java",
                f"{drive}:\\Program Files\\Eclipse Adoptium",
                f"{drive}:\\Program Files\\Microsoft",
                f"{drive}:\\Program Files\\Amazon Corretto",
                f"{drive}:\\Program Files\\BellSoft",
                f"{drive}:\\Program Files\\Zulu",
            ])

        for root in roots:
            if not os.path.isdir(root):
                continue
            for current_root, directories, _files in os.walk(root):
                directories[:] = [directory for directory in directories if directory.lower() not in {"lib", "include", "legal"}]
                java_path = os.path.join(current_root, "bin", "java.exe")
                if os.path.isfile(java_path):
                    candidates.append(java_path)

        if sys.platform == "win32":
            try:
                import winreg

                for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    for key_path in (
                        r"SOFTWARE\JavaSoft\Java Runtime Environment",
                        r"SOFTWARE\JavaSoft\JDK",
                    ):
                        try:
                            with winreg.OpenKey(hive, key_path) as key:
                                current, _ = winreg.QueryValueEx(key, "CurrentVersion")
                                with winreg.OpenKey(key, str(current)) as version_key:
                                    java_home, _ = winreg.QueryValueEx(version_key, "JavaHome")
                                    candidates.append(os.path.join(java_home, "bin", "java.exe"))
                        except (FileNotFoundError, OSError):
                            continue
            except ImportError:
                pass

        installations = []
        seen = set()
        for path in candidates:
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized in seen or not os.path.isfile(path):
                continue
            seen.add(normalized)
            installations.append({
                "path": os.path.normpath(path),
                "version": MinecraftLauncherCore.java_version(path),
            })
        return installations

    @staticmethod
    def java_version(java_path):
        try:
            result = subprocess.run(
                [java_path, "-version"], capture_output=True, text=True, timeout=2,
            )
            output = f"{result.stdout}\n{result.stderr}"
            match = re.search(r'version "([^"]+)"', output)
            if match:
                return match.group(1)
        except (OSError, subprocess.SubprocessError):
            pass
        return "未知版本"

    def launch_game(self, player_name="TrashPlayer", version_id="1.20.4", max_memory="4096"):
        """
        核心逻辑：处理启动游戏按钮点击后的动作
        后续这里会编写组装 JVM 参数并调用 subprocess 的真实逻辑
        """
        print(f"[Core] 准备启动游戏...")
        print(f"  - 游戏目录: {self.minecraft_dir}")
        print(f"  - 玩家名称: {player_name}")
        print(f"  - 游戏版本: {version_id}")
        print(f"  - 分配内存: {max_memory} MB")
        
        # 预留位：后续写 subprocess 启动代码
        return True

    def change_version(self):
        """
        核心逻辑：处理更换版本按钮点击后的动作
        """
        print(f"[Core] 触发了更换版本逻辑...")
        # 预留位：后续写打开版本选择弹窗或扫描 versions 目录的逻辑
        return "1.20.4"