"""
远程代码服务 - 通过 SSH 访问远端 SDK 源码
"""
import os
import re
from typing import Optional
import paramiko
from app.core.config import settings


class RemoteCodeService:
    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None

    def _get_client(self) -> paramiko.SSHClient:
        if self._client and self._client.get_transport() and self._client.get_transport().is_active():
            return self._client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_path = os.path.expanduser(settings.CODE_SSH_KEY_PATH)
        client.connect(
            hostname=settings.CODE_SSH_HOST,
            username=settings.CODE_SSH_USER,
            key_filename=key_path if os.path.exists(key_path) else None,
            timeout=10,
        )
        self._client = client
        return client

    def exec(self, cmd: str, timeout: int = 30) -> str:
        client = self._get_client()
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return (out + err).strip()

    def list_sdks(self) -> dict:
        """返回 {chip_model: sdk_path}"""
        sdk_root = settings.CODE_SDK_ROOT
        out = self.exec(f"ls {sdk_root}")
        result = {}
        for name in out.splitlines():
            name = name.strip()
            if name:
                # 优先取 dev 子目录，否则取根目录
                dev_path = f"{sdk_root}/{name}/dev"
                check = self.exec(f"test -d {dev_path} && echo yes || echo no")
                result[name] = dev_path if check.strip() == "yes" else f"{sdk_root}/{name}"
        return result

    def find_sdk_path(self, chip_model: str) -> Optional[str]:
        """根据芯片型号查找 SDK 路径，模糊匹配"""
        sdks = self.list_sdks()
        chip_upper = chip_model.upper()
        # 精确匹配
        for name, path in sdks.items():
            if name.upper() == chip_upper:
                return path
        # 前缀匹配（如 RV1103 匹配 RV1103B）
        for name, path in sdks.items():
            if chip_upper in name.upper() or name.upper() in chip_upper:
                return path
        return None

    def grep(self, pattern: str, path: str, include: str = "", case_insensitive: bool = True, max_lines: int = 60) -> str:
        """在远端目录中搜索代码"""
        flags = "-r -n"
        if case_insensitive:
            flags += " -i"
        include_flag = f'--include="{include}"' if include else ""
        cmd = f'grep {flags} {include_flag} "{pattern}" {path} 2>/dev/null | head -{max_lines}'
        return self.exec(cmd, timeout=30)

    def read_file(self, path: str, start_line: int = 1, end_line: int = 0, max_bytes: int = 12000) -> str:
        """读取远端文件内容"""
        if end_line > 0:
            cmd = f"sed -n '{start_line},{end_line}p' {path} 2>/dev/null"
        else:
            cmd = f"head -c {max_bytes} {path} 2>/dev/null"
        return self.exec(cmd, timeout=15)

    def list_files(self, path: str, pattern: str = "", max_depth: int = 2) -> str:
        """列出远端目录文件"""
        if pattern:
            cmd = f"find {path} -maxdepth {max_depth} -name '{pattern}' 2>/dev/null | head -50"
        else:
            cmd = f"ls -la {path} 2>/dev/null | head -50"
        return self.exec(cmd, timeout=15)

    def list_docs(self, sdk_path: str, lang: str = "zh") -> str:
        """列出 SDK 的文档目录，区分可读 MD 和不可读 PDF"""
        docs_path = f"{sdk_path}/docs/{lang}"
        check = self.exec(f"test -d {docs_path} && echo yes || echo no")
        if check.strip() != "yes":
            docs_path = f"{sdk_path}/docs"
        md_files = self.exec(f"find {docs_path} -maxdepth 4 -name '*.md' 2>/dev/null | head -30")
        pdf_files = self.exec(f"find {docs_path} -maxdepth 4 -name '*.pdf' 2>/dev/null | head -30")
        parts = []
        if md_files:
            parts.append("📄 Markdown 文档（可用 read_file 直接读取）：\n" + md_files)
        if pdf_files:
            parts.append("📕 PDF 文档（⚠️ 无法通过 read_file 读取，内容已在知识库中，请勿调用 read_file 读取 PDF）：\n" + pdf_files)
        return "\n\n".join(parts) if parts else ""


remote_code_service = RemoteCodeService()
