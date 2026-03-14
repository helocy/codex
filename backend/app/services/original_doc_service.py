import json
import os
from typing import List, Optional

CONFIG_FILE = "./config/original_doc_paths.json"

# 尝试导入 PDF 和 Word 解析库
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class OriginalDocService:
    """原始文档路径管理服务"""

    def __init__(self):
        self.paths: List[str] = []
        self._load_config()

    def _load_config(self):
        """从配置文件加载路径列表"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.paths = config.get('paths', [])
            except Exception:
                self.paths = []
        else:
            self.paths = []

    def _save_config(self):
        """保存路径列表到配置文件"""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        config = {'paths': self.paths}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_paths(self) -> List[str]:
        """获取所有配置的路径"""
        return self.paths

    def add_path(self, path: str) -> dict:
        """添加一个新的路径"""
        path = os.path.abspath(path)
        if path in self.paths:
            return {'success': False, 'message': '路径已存在'}
        if not os.path.exists(path):
            return {'success': False, 'message': '路径不存在'}
        self.paths.append(path)
        self._save_config()
        return {'success': True, 'message': '路径添加成功'}

    def remove_path(self, path: str) -> dict:
        """移除一个路径"""
        if path not in self.paths:
            return {'success': False, 'message': '路径不存在'}
        self.paths.remove(path)
        self._save_config()
        return {'success': True, 'message': '路径移除成功'}

    def find_original_doc(self, title: str, target_pages: Optional[set] = None) -> Optional[str]:
        """
        根据文档标题在配置的路径中查找原始文档内容

        Args:
            title: 文档标题
            target_pages: 目标页码集合（1-indexed），仅对 PDF 生效。
                          为 None 时读取全部内容。

        Returns:
            原始文档内容，如果找不到返回 None
        """
        if not self.paths:
            return None

        # 尝试多种文件扩展名
        base_names = [
            title,
            title.replace('/', os.sep),
            os.path.basename(title),
        ]

        extensions = ['.md', '.txt', '.markdown', '.pdf', '.docx']

        for search_path in self.paths:
            if not os.path.exists(search_path):
                continue

            for root, dirs, files in os.walk(search_path):
                for base_name in base_names:
                    # 如果 base_name 已经有扩展名，直接尝试查找
                    if any(base_name.endswith(ext) for ext in extensions):
                        file_path = os.path.join(root, base_name)
                        if os.path.exists(file_path):
                            try:
                                ext = os.path.splitext(base_name)[1]
                                content = self._read_file(file_path, ext, target_pages)
                                if content:
                                    return content
                            except Exception:
                                continue
                    else:
                        # 如果没有扩展名，尝试添加各种扩展名
                        for ext in extensions:
                            filename = base_name + ext
                            file_path = os.path.join(root, filename)
                            if os.path.exists(file_path):
                                try:
                                    content = self._read_file(file_path, ext, target_pages)
                                    if content:
                                        return content
                                except Exception:
                                    continue

        return None

    def _read_file(self, file_path: str, ext: str, target_pages: Optional[set] = None) -> Optional[str]:
        """根据文件扩展名读取文件内容"""
        if ext in ['.md', '.txt', '.markdown']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        elif ext == '.pdf' and PDF_AVAILABLE:
            try:
                reader = PdfReader(file_path)
                total_pages = len(reader.pages)

                if target_pages:
                    # 只解析目标页码（1-indexed → 0-indexed）
                    indices = sorted(p - 1 for p in target_pages if 1 <= p <= total_pages)
                    text_parts = []
                    for i in indices:
                        text = reader.pages[i].extract_text() or ""
                        if text.strip():
                            text_parts.append(f"[第 {i + 1} 页]\n{text}")
                    content = '\n\n'.join(text_parts)

                    # 内容过少（< 200字符）时，自动扩展 ±3 页重试
                    if len(content.strip()) < 200:
                        expanded = set()
                        for p in target_pages:
                            for offset in range(-3, 4):
                                np_ = p + offset
                                if 1 <= np_ <= total_pages:
                                    expanded.add(np_)
                        indices = sorted(p - 1 for p in expanded)
                        text_parts = []
                        for i in indices:
                            text = reader.pages[i].extract_text() or ""
                            if text.strip():
                                text_parts.append(f"[第 {i + 1} 页]\n{text}")
                        content = '\n\n'.join(text_parts)

                    return content if content.strip() else None
                else:
                    # 无页码信息时读取全部
                    text_parts = []
                    for page in reader.pages:
                        text_parts.append(page.extract_text())
                    return '\n\n'.join(text_parts)
            except Exception:
                return None

        elif ext == '.docx' and DOCX_AVAILABLE:
            try:
                doc = Document(file_path)
                text_parts = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text)
                return '\n\n'.join(text_parts)
            except Exception:
                return None

        return None


# 全局实例
original_doc_service = OriginalDocService()
