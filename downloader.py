import json
import os
import re
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from queue import Empty, Queue


LOADER_CATALOG_URLS = {
    "原版": None,
    "Fabric": "https://meta.fabricmc.net/v2/versions/game",
    "Forge": "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml",
    "NeoForge": "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml",
    "Quilt": "https://meta.quiltmc.org/v3/versions/game",
}


class MinecraftDownloadService:
    def __init__(self, download_root=None):
        self.download_root = download_root or os.path.join(os.getcwd(), ".minecraft", "versions")
        self.events = Queue()

    def load_versions_async(self, loader, manifest_url):
        self.events.put(("catalog_loading", loader))
        thread = threading.Thread(
            target=self._load_versions,
            args=(loader, manifest_url),
            name=f"catalog-{loader}",
            daemon=True,
        )
        thread.start()

    def _load_versions(self, loader, manifest_url):
        try:
            payload = self._read_url(manifest_url)
            if loader == "原版":
                manifest = json.loads(payload)
                versions = [
                    {"id": item["id"], "type": item.get("type", "unknown"), "url": item["url"]}
                    for item in manifest.get("versions", [])
                    if item.get("id") and item.get("url")
                ]
            elif loader in {"Fabric", "Quilt"}:
                versions = self._parse_game_versions(loader, json.loads(payload))
            else:
                versions = self._parse_maven_versions(loader, payload)
            self.events.put(("catalog_loaded", loader, versions))
        except (OSError, ValueError, KeyError, ElementTree.ParseError) as error:
            self.events.put(("catalog_error", loader, str(error)))

    def download_version_async(self, loader, version, installation_name):
        thread = threading.Thread(
            target=self._download_version,
            args=(loader, version, installation_name),
            name=f"download-{loader}-{version['id']}",
            daemon=True,
        )
        thread.start()

    @staticmethod
    def make_loader_version(loader, game_version):
        version_id = game_version["id"]
        if loader == "Fabric":
            url = f"https://meta.fabricmc.net/v2/versions/loader/{version_id}"
        elif loader == "Quilt":
            url = f"https://meta.quiltmc.org/v3/versions/loader/{version_id}"
        elif loader == "Forge":
            url = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
        elif loader == "NeoForge":
            url = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
        else:
            return dict(game_version)
        return {"id": f"{loader}-{version_id}", "type": "loader", "url": url}

    def _download_version(self, loader, version, installation_name):
        target_dir = os.path.join(self.download_root, self._safe_name(installation_name))
        os.makedirs(target_dir, exist_ok=True)
        extension = ".jar" if version["url"].lower().endswith(".jar") else ".json"
        target_path = os.path.join(target_dir, f"{self._safe_name(version['id'])}{extension}")
        temporary_path = f"{target_path}.part"
        try:
            request = urllib.request.Request(version["url"], headers={"User-Agent": "TrashLauncher/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response, open(temporary_path, "wb") as output:
                total = int(response.headers.get("Content-Length") or 0)
                downloaded = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    self.events.put(("download_progress", loader, version["id"], downloaded, total))
            os.replace(temporary_path, target_path)
            self.events.put(("download_done", loader, version["id"], target_path))
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            try:
                os.remove(temporary_path)
            except FileNotFoundError:
                pass
            self.events.put(("download_error", loader, version["id"], str(error)))

    @staticmethod
    def _read_url(url):
        if os.path.isfile(url):
            with open(url, "r", encoding="utf-8") as manifest_file:
                return manifest_file.read()
        request = urllib.request.Request(url, headers={"User-Agent": "TrashLauncher/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")

    @staticmethod
    def _parse_game_versions(loader, payload):
        versions = []
        for item in payload:
            if isinstance(item, str):
                version_id = item
            else:
                version_id = item.get("version") or item.get("id")
            if not version_id:
                continue
            if loader == "Fabric":
                url = f"https://meta.fabricmc.net/v2/versions/loader/{version_id}"
            else:
                url = f"https://meta.quiltmc.org/v3/versions/loader/{version_id}"
            versions.append({"id": version_id, "type": "game", "url": url})
        return versions

    @staticmethod
    def _parse_maven_versions(loader, payload):
        root = ElementTree.fromstring(payload)
        versions = [item.text for item in root.findall(".//version") if item.text]
        versions = list(dict.fromkeys(versions))[-200:]
        if loader == "Forge":
            base_url = "https://maven.minecraftforge.net/net/minecraftforge/forge"
            versions.reverse()
            return [
                {"id": version, "type": "loader", "url": f"{base_url}/{version}/forge-{version}-installer.jar"}
                for version in versions
            ]
        base_url = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
        versions.reverse()
        return [
            {"id": version, "type": "loader", "url": f"{base_url}/{version}/neoforge-{version}-installer.jar"}
            for version in versions
        ]

    @staticmethod
    def _safe_name(value):
        return re.sub(r"[^A-Za-z0-9._-]+", "_", value)

    def get_event(self):
        try:
            return self.events.get_nowait()
        except Empty:
            return None
