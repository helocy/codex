import os
import re
from PyPDF2 import PdfReader
from docx import Document as DocxDocument


class FileProcessor:
    @staticmethod
    def _open_pdf(file_path: str) -> "PdfReader":
        """打开 PDF，自动尝试空密码解密加密文件"""
        reader = PdfReader(file_path)
        if reader.is_encrypted:
            try:
                result = reader.decrypt("")  # 返回 1/2 表示成功，0 表示密码错误
            except Exception:
                raise Exception("该 PDF 已加密，请先移除密码后再上传")
            if result == 0:
                raise Exception("该 PDF 已加密，请先移除密码后再上传")
        return reader

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """从 PDF 提取全文（用于存储 document.content）"""
        try:
            reader = FileProcessor._open_pdf(file_path)
            pages = []
            for i, page in enumerate(reader.pages):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(f"[第 {i+1} 页]\n{text}")
            return "\n\n".join(pages)
        except Exception as e:
            raise Exception(f"PDF 解析失败: {str(e)}")

    @staticmethod
    def _extract_pdf_pages(file_path: str) -> list[tuple[int, str]]:
        """逐页提取 PDF 文本，返回 [(page_num, text), ...]"""
        reader = FileProcessor._open_pdf(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((i + 1, text))
        return pages

    @staticmethod
    def chunk_pdf(file_path: str, max_chunk_size: int = 1000, overlap: int = 100) -> list[str]:
        """
        PDF 感知分块策略：
        1. 逐页提取文本，每页用 [第 N 页] 作为上下文前缀
        2. 每页 <= max_chunk_size 直接作为一个 chunk
        3. 超大页按段落合并，保留页码前缀
        4. 超大段落再字符切
        相邻页文本量极少时合并，避免产生大量碎片 chunk
        """
        pages = FileProcessor._extract_pdf_pages(file_path)
        if not pages:
            return []

        chunks = []
        pending_heading = ""
        pending_text = ""

        for page_num, text in pages:
            heading = f"[第 {page_num} 页]"
            full = f"{heading}\n\n{text}"

            if len(full) <= max_chunk_size:
                # 小页：尝试与 pending 合并
                candidate = (pending_text + "\n\n" + full).strip() if pending_text else full
                if len(candidate) <= max_chunk_size:
                    pending_text = candidate
                    if not pending_heading:
                        pending_heading = heading
                else:
                    if pending_text:
                        chunks.append(pending_text)
                    pending_heading = heading
                    pending_text = full
            else:
                # 大页：先 flush pending，再按段落切
                if pending_text:
                    chunks.append(pending_text)
                    pending_text = ""
                    pending_heading = ""
                sub = FileProcessor._chunk_by_paragraphs(text, max_chunk_size, overlap, heading=heading)
                chunks.extend(sub if sub else [full[:max_chunk_size]])

        if pending_text:
            chunks.append(pending_text)

        return [c for c in chunks if c.strip()]

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """从 Word 文档提取文本"""
        try:
            doc = DocxDocument(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            raise Exception(f"Word 文档解析失败: {str(e)}")

    @staticmethod
    def extract_text_from_markdown(file_path: str) -> str:
        """从 Markdown 提取文本"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content.strip()
        except Exception as e:
            raise Exception(f"Markdown 解析失败: {str(e)}")

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
        """字符级分块（非 Markdown 文件的兜底策略）"""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return [c for c in chunks if c.strip()]

    @staticmethod
    def _chunk_by_chars(text: str, max_size: int = 1000, overlap: int = 100) -> list[str]:
        """字符级分块（内部用）"""
        if len(text) <= max_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start:start + max_size])
            start += max_size - overlap
        return chunks

    @staticmethod
    def _chunk_by_paragraphs(text: str, max_size: int = 1000, overlap: int = 100,
                              heading: str = "") -> list[str]:
        """段落级分块：合并小段落，超大段落再字符切"""
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        chunks = []
        current = heading  # 每个 chunk 带上所属标题作为上下文前缀

        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip() if current else para
            if len(candidate) <= max_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(para) > max_size:
                    # 单段落超限，字符切，每块保留标题前缀
                    for sub in FileProcessor._chunk_by_chars(para, max_size, overlap):
                        chunks.append((heading + "\n\n" + sub).strip() if heading else sub)
                    current = heading
                else:
                    current = (heading + "\n\n" + para).strip() if heading else para

        if current and current.strip() != heading.strip():
            chunks.append(current)

        return [c for c in chunks if c.strip()]

    @staticmethod
    def chunk_markdown(text: str, max_chunk_size: int = 1000, overlap: int = 100) -> list[str]:
        """
        Markdown 感知分块策略：
        1. 按标题（# ~ ###）将文档切成若干 section
        2. 每个 section <= max_chunk_size 直接作为一块
        3. 超大 section 按段落合并，保留标题前缀
        4. 超大段落再按字符切
        """
        heading_re = re.compile(r'^(#{1,3}\s+.+)$', re.MULTILINE)
        positions = [m.start() for m in heading_re.finditer(text)]

        if not positions:
            # 没有标题，按段落分块
            return FileProcessor._chunk_by_paragraphs(text, max_chunk_size, overlap)

        # 收集各 section：[heading_line, body_text]
        sections = []
        # 标题前的前言
        if positions[0] > 0:
            preamble = text[:positions[0]].strip()
            if preamble:
                sections.append(("", preamble))

        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(text)
            section_text = text[pos:end]
            lines = section_text.split('\n', 1)
            heading_line = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            sections.append((heading_line, body))

        chunks = []
        for heading_line, body in sections:
            full_section = (heading_line + "\n\n" + body).strip() if body else heading_line
            if not full_section:
                continue
            if len(full_section) <= max_chunk_size:
                chunks.append(full_section)
            else:
                # section 过大，按段落细分，保留标题前缀
                sub = FileProcessor._chunk_by_paragraphs(
                    body, max_chunk_size, overlap, heading=heading_line
                )
                chunks.extend(sub if sub else [full_section[:max_chunk_size]])

        return [c for c in chunks if c.strip()]
