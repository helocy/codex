import React, { useState, useEffect, useRef } from 'react';
import { uploadFile, saveText, chatWithRAG, configureLLM, getLLMConfig, getDocuments, getDbStats, deleteDocument, resetDatabase, getEmbeddingConfig, configureEmbedding, exportDatabase, importDatabase, getOriginalDocPaths, addOriginalDocPath, removeOriginalDocPath, batchBuildTreeIndex, findDuplicates } from './services/api';
import MarkdownRenderer from './components/MarkdownRenderer';
import { useTranslation } from './i18n/useTranslation';
import './index.css';

type Mode = 'memory' | 'chat' | 'config';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  webSources?: any[];
  originalDocStatus?: string;
  treeNodes?: any[];
  elapsed?: number;  // 耗时（秒）
}

interface LLMConfig {
  provider: string;
  model?: string;
  api_key?: string;
  base_url?: string;
}

interface EmbeddingConfig {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
}

interface DbStats {
  document_count: number;
  chunk_count: number;
  db_size: string;
  type_counts: Record<string, number>;
  embedding_provider: string;
  embedding_model: string;
}

interface ConfirmDialog {
  visible: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
}

// 图标组件
const CopyIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

const ResendIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <polyline points="1 4 1 10 7 10" />
    <path d="M3.51 15a9 9 0 1 0 .49-4" />
  </svg>
);

const CheckIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
    <polyline points="20 6 9 17 4 12" />
  </svg>
);


function parseThinking(content: string): { thinking: string | null; answer: string } {
  const fullMatch = content.match(/^<think>([\s\S]*?)<\/think>\s*([\s\S]*)$/);
  if (fullMatch) {
    return { thinking: fullMatch[1].trim(), answer: fullMatch[2].trim() };
  }
  const openMatch = content.match(/^<think>([\s\S]*)$/);
  if (openMatch) {
    return { thinking: openMatch[1].trim(), answer: '' };
  }
  return { thinking: null, answer: content };
}

function App() {
  const { t, language, switchLanguage } = useTranslation();
  const [mode, setMode] = useState<Mode>('chat');  // 默认显示对话界面
  const [query, setQuery] = useState('');
  const [textContent, setTextContent] = useState('');  // 记忆页面的文本输入
  const [textTitle, setTextTitle] = useState('');  // 记忆页面的标题输入
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatting, setChatting] = useState(false);
  const [useRag, setUseRag] = useState(true);  // 默认勾选知识库
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [useOriginalDoc, setUseOriginalDoc] = useState(true);  // 默认勾选搜索原始文档
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);

  const getSavedConfig = (): LLMConfig => {
    const saved = localStorage.getItem('llm_config');
    if (saved) { try { return JSON.parse(saved); } catch {} }
    return { provider: 'custom', model: '', base_url: '', api_key: '' };
  };

  const [llmConfig, setLlmConfig] = useState<LLMConfig>(getSavedConfig());
  const [embeddingConfig, setEmbeddingConfig] = useState<EmbeddingConfig>({ provider: 'local', model: 'paraphrase-multilingual-MiniLM-L12-v2' });
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploadLogs, setUploadLogs] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadTotal, setUploadTotal] = useState(0);
  const [uploadDone, setUploadDone] = useState(false);
  const [forceUpload, setForceUpload] = useState(false);  // 强制上传选项
  const [overwriteUpload, setOverwriteUpload] = useState(false);  // 覆盖上传选项

  const [dbStats, setDbStats] = useState<DbStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [originalDocPaths, setOriginalDocPaths] = useState<string[]>([]);
  const [newDocPath, setNewDocPath] = useState('');
  const [adminMessage, setAdminMessage] = useState('');
  const [docSearch, setDocSearch] = useState('');
  const [confirm, setConfirm] = useState<ConfirmDialog>({ visible: false, title: '', message: '', onConfirm: () => {} });
  const [exporting, setExporting] = useState(false);
  const [batchBuilding, setBatchBuilding] = useState(false);
  const [duplicateGroups, setDuplicateGroups] = useState<any[][]>([]);
  const [duplicateSearching, setDuplicateSearching] = useState(false);
  const [duplicateSearched, setDuplicateSearched] = useState(false);
  const [duplicateKeep, setDuplicateKeep] = useState<Record<number, number>>({});  // groupIndex -> doc.id to keep

  // 自动滚到底部
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, chatting]);

  useEffect(() => {
    loadLLMConfig();
    loadEmbeddingConfig();
    loadDocuments();
    const savedConfig = localStorage.getItem('llm_config');
    if (savedConfig) {
      try {
        const config = JSON.parse(savedConfig);
        // 只有当配置了 API Key 时才自动配置
        if (config.api_key && config.api_key.trim()) {
          configureLLM(config).catch(console.error);
        }
      } catch {}
    }
  }, []);

  useEffect(() => {
    if (mode === 'config') { loadDbStats(); loadDocuments(); loadOriginalDocPaths(); }
  }, [mode]);

  const loadLLMConfig = async () => {
    try { await getLLMConfig(); } catch {}
  };

  const loadEmbeddingConfig = async () => {
    try {
      const c = await getEmbeddingConfig();
      setEmbeddingConfig({ provider: c.provider, model: c.model, base_url: c.base_url });
    } catch {}
  };

  const loadDocuments = async () => {
    try { const d = await getDocuments(); setDocuments(d.documents || []); } catch {}
  };

  const loadDbStats = async () => {
    setStatsLoading(true);
    try { setDbStats(await getDbStats()); } catch {} finally { setStatsLoading(false); }
  };

  const loadOriginalDocPaths = async () => {
    try {
      const data = await getOriginalDocPaths();
      setOriginalDocPaths(data.paths || []);
    } catch {}
  };

  const handleAddDocPath = async () => {
    if (!newDocPath.trim()) return;
    try {
      await addOriginalDocPath(newDocPath.trim());
      setNewDocPath('');
      loadOriginalDocPaths();
      setAdminMessage(`${t.msgSuccess} ${t.msgPathAdded}`);
    } catch (e: any) {
      setAdminMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleRemoveDocPath = async (path: string) => {
    try {
      await removeOriginalDocPath(path);
      loadOriginalDocPaths();
      setAdminMessage(`${t.msgSuccess} ${t.msgPathRemoved}`);
    } catch (e: any) {
      setAdminMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    }
  };

  const showConfirm = (title: string, message: string, onConfirm: () => void) => {
    setConfirm({ visible: true, title, message, onConfirm });
  };

  const handleCopy = (content: string, idx: number) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  };

  const handleResend = (content: string) => {
    setQuery(content);
  };

  const handleDeleteDocument = (doc: any) => {
    showConfirm(t.dialogDeleteTitle, t.dialogDeleteMessage.replace('{title}', doc.title), async () => {
      setConfirm(p => ({ ...p, visible: false }));
      try {
        await deleteDocument(doc.id);
        setAdminMessage(`${t.msgSuccess} ${t.msgDeleteSuccess}：${doc.title}`);
        // 从冗余组中移除已删除的文档，组内只剩1个时整组消除
        setDuplicateGroups(prev => {
          const updated = prev
            .map(group => group.filter((d: any) => d.id !== doc.id))
            .filter(group => group.length >= 2);
          return updated;
        });
        setDuplicateKeep(prev => {
          const updated = { ...prev };
          Object.keys(updated).forEach(gi => {
            if (updated[Number(gi)] === doc.id) delete updated[Number(gi)];
          });
          return updated;
        });
        await loadDocuments(); await loadDbStats();
      } catch (e: any) { setAdminMessage(`${t.msgError} ${language === 'zh' ? '删除失败' : 'Delete failed'}：${e.response?.data?.detail || e.message}`); }
    });
  };

  const handleBatchBuildTreeIndex = async () => {
    setBatchBuilding(true);
    setAdminMessage('');
    try {
      const result = await batchBuildTreeIndex();
      if (result.triggered_count === 0) {
        setAdminMessage(`✓ ${language === 'zh' ? '所有文档均已有树形索引，无需重建' : 'All documents already have tree index'}`);
      } else {
        setAdminMessage(`✓ ${language === 'zh' ? `已触发 ${result.triggered_count} 篇文档的树形索引构建，后台处理中...` : `Triggered tree index build for ${result.triggered_count} documents, processing in background...`}`);
      }
      // 延迟刷新列表，让后台有时间处理部分文档
      setTimeout(() => loadDocuments(), 3000);
    } catch (e: any) {
      setAdminMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    } finally {
      setBatchBuilding(false);
    }
  };

  const handleFindDuplicates = async () => {
    setDuplicateSearching(true);
    setDuplicateSearched(false);
    setDuplicateGroups([]);
    setDuplicateKeep({});
    try {
      const result = await findDuplicates(0.97);
      setDuplicateGroups(result.groups || []);
      // 默认保留每组中 chunk 数最多的文档
      const defaultKeep: Record<number, number> = {};
      (result.groups || []).forEach((group: any[], gi: number) => {
        const best = group.reduce((a: any, b: any) => (b.chunk_count > a.chunk_count ? b : a));
        defaultKeep[gi] = best.id;
      });
      setDuplicateKeep(defaultKeep);
    } catch (e: any) {
      setAdminMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    } finally {
      setDuplicateSearching(false);
      setDuplicateSearched(true);
    }
  };

  const handleDeleteDuplicates = async () => {
    const toDelete: number[] = [];
    duplicateGroups.forEach((group, gi) => {
      const keepId = duplicateKeep[gi];
      group.forEach((doc: any) => {
        if (doc.id !== keepId) toDelete.push(doc.id);
      });
    });
    if (toDelete.length === 0) return;
    try {
      for (const id of toDelete) await deleteDocument(id);
      setAdminMessage(`✓ 已删除 ${toDelete.length} 个冗余文档`);
      // 删除后重新检测，刷新冗余组
      setDuplicateGroups([]);
      setDuplicateKeep({});
      setDuplicateSearched(false);
      await loadDocuments();
      await loadDbStats();
    } catch (e: any) {
      setAdminMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleReset = () => {
    showConfirm(t.dialogResetTitle, t.dialogResetMessage, async () => {
      setConfirm(p => ({ ...p, visible: false }));
      try {
        await resetDatabase();
        setAdminMessage(`${t.msgSuccess} ${t.msgResetSuccess}`);
        await loadDocuments(); await loadDbStats();
      } catch (e: any) { setAdminMessage(`${t.msgError} ${language === 'zh' ? '重置失败' : 'Reset failed'}：${e.response?.data?.detail || e.message}`); }
    });
  };

  const handleExport = async () => {
    if (!dbStats) {
      setAdminMessage(language === 'zh' ? '请先加载统计信息' : 'Please load statistics first');
      return;
    }

    const estimatedSizeMB = Math.ceil(dbStats.chunk_count * 0.05); // 每个 chunk 约 50KB
    const estimatedMinutes = Math.ceil(dbStats.chunk_count / 100); // 约 100 chunks/分钟

    const message = t.dialogExportMessage
      .replace('{docCount}', dbStats.document_count.toString())
      .replace('{chunkCount}', dbStats.chunk_count.toString())
      .replace('{sizeMB}', estimatedSizeMB.toString())
      .replace('{minutes}', estimatedMinutes.toString());

    showConfirm(
      t.dialogExportTitle,
      message,
      async () => {
        setConfirm(p => ({ ...p, visible: false }));
        setExporting(true);
        setAdminMessage('');
        try {
          const blob = await exportDatabase();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `codex_backup_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
          setAdminMessage(`${t.msgSuccess} ${t.msgExportSuccess}`);
        } catch (e: any) {
          setAdminMessage(`${t.msgError} ${language === 'zh' ? '导出失败' : 'Export failed'}：${e.response?.data?.detail || e.message}`);
        } finally {
          setExporting(false);
        }
      }
    );
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    showConfirm(t.dialogImportTitle, t.dialogImportMessage, async () => {
      setConfirm(p => ({ ...p, visible: false }));
      try {
        setAdminMessage(language === 'zh' ? '正在导入数据库...' : 'Importing database...');
        const result = await importDatabase(file);
        setAdminMessage(`${t.msgSuccess} ${t.msgImportSuccess}：${result.imported_documents} ${language === 'zh' ? '个文档' : 'documents'}，${result.imported_chunks} ${language === 'zh' ? '个文本块' : 'chunks'}`);
        await loadDocuments(); await loadDbStats();
      } catch (e: any) {
        const errorDetail = e.response?.data?.detail || e.message;
        // 如果是 embedding 模型不匹配错误，显示完整的错误信息
        if (errorDetail.includes('Embedding') || errorDetail.includes('模型不匹配')) {
          setAdminMessage(`${t.msgError} ${errorDetail}`);
        } else {
          setAdminMessage(`${t.msgError} ${language === 'zh' ? '导入失败' : 'Import failed'}：${errorDetail}`);
        }
      }
    });

    e.target.value = '';
  };
  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const userMessage: ChatMessage = { role: 'user', content: query };
    const currentHistory = chatMessages.map(m => ({ role: m.role, content: m.content }));
    setChatMessages(prev => [...prev, userMessage]);
    setQuery('');
    setChatting(true);
    const t0 = Date.now();
    try {
      const r = await chatWithRAG(userMessage.content, 20, useRag, useWebSearch, useOriginalDoc, currentHistory);
      const elapsed = (Date.now() - t0) / 1000;
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: r.answer,
        sources: r.sources,
        webSources: r.web_sources,
        originalDocStatus: r.original_doc_status,
        treeNodes: r.tree_nodes,
        elapsed,
      }]);
    } catch (e: any) {
      const elapsed = (Date.now() - t0) / 1000;
      setChatMessages(prev => [...prev, { role: 'assistant', content: `抱歉，对话失败: ${e.response?.data?.detail || e.message}`, elapsed }]);
    } finally { setChatting(false); }
  };

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textContent.trim()) return;
    setUploading(true); setMessage('');
    try {
      const r = await saveText(textContent, textTitle || undefined);
      setMessage(`✓ 保存成功: ${r.title}`);
      setTextContent('');
      setTextTitle('');
      loadDocuments();
    } catch (e: any) {
      // 如果是相似文档提示
      const errorDetail = e.response?.data?.detail || e.message;
      if (errorDetail.includes('相似文档')) {
        setMessage(`⚠️ ${errorDetail}`);
      } else {
        setMessage(`✗ 保存失败: ${errorDetail}`);
      }
    }
    finally { setUploading(false); }
  };

  const handleUpload = async (file: File) => {
    const t0 = Date.now();
    setUploading(true); setMessage(''); setUploadDone(false);
    setUploadLogs([`正在处理: ${file.name}`]);
    setUploadProgress(0); setUploadTotal(1);
    try {
      const r = await uploadFile(file, forceUpload, overwriteUpload);

      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      if (r.similar_documents && r.similar_documents.length > 0) {
        const similarTitles = r.similar_documents.map((d: any) => d.title).join('、');
        setUploadLogs(prev => [...prev, `⚠️ 发现相似文档：${similarTitles}。${r.suggestion || ''} (${elapsed}s)`]);
        setMessage(`⚠️ 发现相似文档：${similarTitles}`);
      } else {
        setUploadLogs(prev => [...prev, `✓ ${r.title}（${r.chunks_count} 个文本块，耗时 ${elapsed}s）`]);
        setMessage(`✓ 上传成功: ${r.title}`);
      }

      setUploadProgress(1);
      loadDocuments();
    } catch (e: any) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      setUploadLogs(prev => [...prev, `❌ ${file.name}: ${e.response?.data?.detail || e.message} (${elapsed}s)`]);
      setUploadProgress(1);
      setMessage(`✗ 上传失败: ${e.response?.data?.detail || e.message}`);
    } finally {
      setUploading(false); setUploadDone(true);
    }
  };

  const SUPPORTED_EXTS = ['.md', '.pdf'];

  const handleDirectoryUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const supported = Array.from(files).filter(f =>
      SUPPORTED_EXTS.some(ext => f.name.toLowerCase().endsWith(ext))
    );
    if (supported.length === 0) {
      setMessage(`✗ 目录中没有找到支持的文件（${SUPPORTED_EXTS.join('、')}）`);
      return;
    }
    // 按类型统计
    const mdCount = supported.filter(f => f.name.toLowerCase().endsWith('.md')).length;
    const pdfCount = supported.filter(f => f.name.toLowerCase().endsWith('.pdf')).length;
    const typeDesc = [mdCount && `${mdCount} 个 MD`, pdfCount && `${pdfCount} 个 PDF`].filter(Boolean).join('、');

    setUploading(true); setMessage(''); setUploadDone(false);
    setUploadLogs([`发现 ${supported.length} 个文件（${typeDesc}），开始上传...`]);
    setUploadProgress(0); setUploadTotal(supported.length);
    const batchT0 = Date.now();
    let successCount = 0, totalChunks = 0;
    for (let i = 0; i < supported.length; i++) {
      const file = supported[i];
      const relativePath = (file as any).webkitRelativePath || file.name;
      setUploadLogs(prev => [...prev, `正在处理 (${i + 1}/${supported.length}): ${relativePath}`]);
      const fileT0 = Date.now();
      try {
        const r = await uploadFile(file, forceUpload, overwriteUpload);
        const fileElapsed = ((Date.now() - fileT0) / 1000).toFixed(1);

        // 检查是否是相似文档提示
        if (r.similar_documents && r.similar_documents.length > 0) {
          const similarTitles = r.similar_documents.map((d: any) => d.title).join('、');
          setUploadLogs(prev => [...prev, `⚠️ ${relativePath}: 发现相似文档 ${similarTitles} (${fileElapsed}s)`]);
        } else {
          successCount++;
          totalChunks += r.chunks_count || 0;
          setUploadLogs(prev => [...prev, `✓ ${relativePath} (${r.chunks_count} 个文本块，${fileElapsed}s)`]);
        }

        setUploadProgress(i + 1);
      } catch (e: any) {
        const fileElapsed = ((Date.now() - fileT0) / 1000).toFixed(1);
        setUploadLogs(prev => [...prev, `❌ ${relativePath}: ${e.response?.data?.detail || e.message} (${fileElapsed}s)`]);
        setUploadProgress(i + 1);
      }
    }
    const batchElapsed = ((Date.now() - batchT0) / 1000).toFixed(1);
    setUploadLogs(prev => [...prev, `完成：${successCount} 个文件，${totalChunks} 个文本块，总耗时 ${batchElapsed}s`]);
    setMessage(`✓ 上传完成: ${successCount} 个文件，${totalChunks} 个文本块`);
    loadDocuments(); setUploading(false); setUploadDone(true);
    e.target.value = '';
  };

  const handleSaveLLMConfig = async () => {
    try {
      await configureLLM(llmConfig);
      localStorage.setItem('llm_config', JSON.stringify(llmConfig));
      setMessage(`${t.msgSuccess} ${t.msgConfigSuccess}`);
      setTimeout(() => setMessage(''), 3000);
    } catch (e: any) { setMessage(`${t.msgError} ${language === 'zh' ? '配置失败' : 'Configuration failed'}: ${e.response?.data?.detail || e.message}`); }
  };

  const handleSaveEmbeddingConfig = async () => {
    try {
      const result = await configureEmbedding(embeddingConfig);
      setMessage(`${t.msgSuccess} ${language === 'zh' ? '嵌入模型配置成功，向量维度' : 'Embedding configured, dimension'}: ${result.dimension}`);
      setTimeout(() => setMessage(''), 3000);
    } catch (e: any) { setMessage(`${t.msgError} ${language === 'zh' ? '配置失败' : 'Configuration failed'}: ${e.response?.data?.detail || e.message}`); }
  };

  const getSubmitHandler = () => {
    if (mode === 'chat') return handleChat;
    return handleTextSubmit;
  };

  const fileTypeLabel: Record<string, string> = {
    markdown: t.fileTypeMarkdown, pdf: t.fileTypePdf, word: t.fileTypeWord,
    text: t.fileTypeText, audio: t.fileTypeAudio, image: t.fileTypeImage, video: t.fileTypeVideo,
  };

  const modeLabels: Record<Mode, string> = {
    chat: t.modeChat, memory: t.modeMemory, config: t.modeConfig,
  };

  const isLocalhost = ['localhost', '127.0.0.1'].includes(window.location.hostname);

  const actionBtn = (onClick: () => void, children: React.ReactNode, label: string) => (
    <button
      onClick={onClick}
      title={label}
      className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-all"
    >
      {children}
      <span>{label}</span>
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* Export Progress Overlay */}
      {exporting && (
        <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <div className="text-center">
              <div className="mb-4">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">{t.exportingTitle}</h3>
              <p className="text-gray-600 mb-4">{t.exportingMessage}</p>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '100%' }}></div>
              </div>
              <p className="text-sm text-gray-500 mt-4">{t.exportingWait}</p>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Dialog */}
      {confirm.visible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-xl font-bold text-gray-900 mb-3">{confirm.title}</h3>
            <p className="text-gray-600 mb-6 leading-relaxed whitespace-pre-wrap">{confirm.message}</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setConfirm(p => ({ ...p, visible: false }))}
                className="px-5 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors">{t.actionCancel}</button>
              <button onClick={confirm.onConfirm}
                className="px-5 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors">{t.actionConfirm}</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== Header (only title + tabs) ===== */}
      <header className="flex flex-col items-center pt-10 pb-0 px-8 shrink-0">
        <h1 className="text-5xl font-bold text-gray-900 mb-8">{t.appName}</h1>
        <div className="flex gap-3 flex-wrap justify-center">
          {(Object.keys(modeLabels) as Mode[]).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`px-6 py-2.5 rounded-full text-sm font-medium transition-all ${mode === m ? 'bg-gray-900 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'}`}>
              {modeLabels[m]}
            </button>
          ))}
        </div>
      </header>

      {/* ===== Chat Mode (full-height scrollable) ===== */}
      {mode === 'chat' && (
        <div
          ref={chatContainerRef}
          className="flex-1 overflow-y-auto px-8 py-6"
          style={{ paddingBottom: '180px' }}
        >
          <div className="max-w-4xl mx-auto space-y-6">
            {chatMessages.length === 0 && (
              <div className="text-center text-gray-400 mt-24 text-sm">{t.chatEmpty} {useRag ? t.chatEmptyRag : t.chatEmptyNoRag}</div>
            )}

            {chatMessages.map((msg, index) => (
              <div key={index} className={`flex flex-col gap-1 group ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                {/* 消息气泡 */}
                <div className={`max-w-3xl rounded-2xl px-6 py-4 ${msg.role === 'user' ? 'bg-gray-900 text-white' : 'bg-white text-gray-800 shadow-md'}`}>
                  {msg.role === 'assistant' ? (() => {
                    const { thinking, answer } = parseThinking(msg.content);
                    return (
                      <>
                        {thinking && (
                          <div className="mb-3 pb-3 border-b border-gray-100">
                            <p className="text-xs text-gray-400 mb-1 font-medium">{t.thinkingProcess}</p>
                            <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">{thinking}</p>
                          </div>
                        )}
                        {(answer || !thinking) && (
                          <MarkdownRenderer content={answer || msg.content} />
                        )}
                      </>
                    );
                  })() : (
                    <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  )}
                  {msg.role === 'assistant' && msg.elapsed !== undefined && (
                    <div className="mt-3 text-xs text-gray-400">
                      {language === 'zh' ? '耗时' : 'Time'}: {msg.elapsed.toFixed(1)}s
                    </div>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-700">
                      {msg.treeNodes && msg.treeNodes.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-400 mb-1">📑 {language === 'zh' ? '命中章节' : 'Matched sections'}</p>
                          {Array.from(new Map(msg.treeNodes.map((n: any) => [`${n.doc_id}-${n.node_id}`, n])).values()).map((n: any, i: number) => (
                            <div key={i} className="text-xs text-gray-400 mb-0.5 pl-2">
                              · {n.doc_title} › {n.node_title}
                            </div>
                          ))}
                        </div>
                      )}
                      <p className="text-xs text-gray-400 mb-2">{t.sourceKnowledgeBase}</p>
                      {Array.from(new Map(msg.sources.map((s: any) => [s.document_id, s])).values()).map((s: any, i: number) => (
                        <div key={i} className="text-xs text-gray-300 mb-1">
                          • 文档 #{s.document_id} ({(s.similarity * 100).toFixed(0)}% 匹配)
                        </div>
                      ))}
                      {msg.originalDocStatus && (
                        <div className="mt-3 pt-3 border-t border-gray-600">
                          <pre className="text-xs text-gray-400 whitespace-pre-wrap">{msg.originalDocStatus}</pre>
                        </div>
                      )}
                    </div>
                  )}
                  {msg.webSources && msg.webSources.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-700">
                      <p className="text-xs text-gray-400 mb-2">{t.sourceWebSearch}</p>
                      {msg.webSources.map((s: any, i: number) => (
                        <div key={i} className="text-xs text-gray-300 mb-1">
                          • <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:underline">{s.title}</a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 操作按钮（悬停显示） */}
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                  {actionBtn(() => handleCopy(msg.content, index),
                    copiedIdx === index ? <CheckIcon /> : <CopyIcon />,
                    copiedIdx === index ? t.actionCopied : t.actionCopy
                  )}
                  {msg.role === 'user' && actionBtn(() => handleResend(msg.content), <ResendIcon />, t.actionResend)}
                </div>
              </div>
            ))}

            {/* 思考中动画 */}
            {chatting && (
              <div className="flex items-start gap-3">
                <div className="bg-white rounded-2xl px-6 py-4 shadow-md">
                  <div className="flex gap-1 items-center">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>
      )}

      {/* ===== Non-chat content ===== */}
      {mode !== 'chat' && (
        <main className="flex-1 flex flex-col items-center px-8 py-8">

          {/* Config (merged Settings + Admin) */}
          {mode === 'config' && (
            <div className="w-full max-w-4xl space-y-6">

              {/* Stats Cards */}
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: t.configDocCount, value: statsLoading ? t.statsLoading : dbStats?.document_count ?? t.statsNoData, icon: '📄' },
                  { label: t.configChunkCount, value: statsLoading ? t.statsLoading : dbStats?.chunk_count ?? t.statsNoData, icon: '🧩' },
                  { label: t.configDbSize, value: statsLoading ? t.statsLoading : dbStats?.db_size ?? t.statsNoData, icon: '💾' },
                ].map((card) => (
                  <div key={card.label} className="bg-white rounded-2xl p-6 shadow-md text-center">
                    <div className="text-3xl mb-2">{card.icon}</div>
                    <div className="text-2xl font-bold text-gray-900">{card.value}</div>
                    <div className="text-sm text-gray-500 mt-1">{card.label}</div>
                  </div>
                ))}
              </div>

              {/* LLM + Embedding Config (localhost only) */}
              {isLocalhost && (
                <>
                  <div className="bg-white rounded-2xl p-8 shadow-md">
                    <h2 className="text-xl font-bold text-gray-900 mb-5">{t.configLlm}</h2>
                    <div className="space-y-4">
                      {[
                        { label: t.configLlmBaseUrl, key: 'base_url', type: 'text', placeholder: 'e.g. https://ark.cn-beijing.volces.com/api/v3' },
                        { label: t.configLlmApiKey, key: 'api_key', type: 'password', placeholder: 'Enter API Key' },
                        { label: t.configLlmModel, key: 'model', type: 'text', placeholder: 'e.g. doubao-pro-4k, gpt-4o, qwen-plus' },
                      ].map(f => (
                        <div key={f.key}>
                          <label className="block text-sm font-medium text-gray-700 mb-2">{f.label}</label>
                          <input type={f.type} value={(llmConfig as any)[f.key] || ''}
                            onChange={(e) => setLlmConfig({ ...llmConfig, [f.key]: e.target.value })}
                            placeholder={f.placeholder}
                            className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none" />
                        </div>
                      ))}
                      <button onClick={handleSaveLLMConfig}
                        className="w-full px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors font-medium">{t.actionSave}</button>
                      {message && <div className={`text-sm text-center ${message.includes('✓') ? 'text-green-600' : 'text-red-600'}`}>{message}</div>}
                    </div>
                  </div>

                  <div className="bg-white rounded-2xl p-8 shadow-md">
                    <div className="flex items-center justify-between mb-5">
                      <h2 className="text-xl font-bold text-gray-900">{t.languageSwitch}</h2>
                      <button
                        onClick={() => switchLanguage(language === 'zh' ? 'en' : 'zh')}
                        className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        {language === 'zh' ? t.languageEnglish : t.languageChinese}
                      </button>
                    </div>
                  </div>

                  <div className="bg-white rounded-2xl p-8 shadow-md">
                    <h2 className="text-xl font-bold text-gray-900 mb-5">{t.configEmbedding}</h2>
                    {dbStats && (
                      <div className="flex items-center gap-3 mb-5 pb-5 border-b border-gray-100">
                        <span className="text-sm text-gray-500">{t.configEmbeddingCurrent}</span>
                        <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
                          {dbStats.embedding_provider === 'local' ? t.embeddingLocal.split(' ')[0] :
                           dbStats.embedding_provider === 'doubao' ? t.embeddingDoubao : t.embeddingOpenAI.split(' ')[0]}
                        </span>
                        <span className="text-gray-700 font-mono text-sm">{dbStats.embedding_model}</span>
                      </div>
                    )}
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">{t.configEmbeddingProvider}</label>
                        <select value={embeddingConfig.provider}
                          onChange={(e) => {
                            const newProvider = e.target.value;
                            const defaultModels: Record<string, string> = {
                              'local': 'paraphrase-multilingual-MiniLM-L12-v2',
                              'doubao': 'doubao-embedding-vision-251215',
                              'openai': 'text-embedding-3-small'
                            };
                            setEmbeddingConfig({
                              ...embeddingConfig,
                              provider: newProvider,
                              model: defaultModels[newProvider] || embeddingConfig.model
                            });
                          }}
                          className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none">
                          <option value="local">{t.embeddingLocal}</option>
                          <option value="doubao">{t.embeddingDoubao}</option>
                          <option value="openai">{t.embeddingOpenAI}</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">{t.configEmbeddingModel}</label>
                        <input type="text" value={embeddingConfig.model}
                          onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, model: e.target.value })}
                          placeholder={
                            embeddingConfig.provider === 'local' ? 'e.g. paraphrase-multilingual-MiniLM-L12-v2' :
                            embeddingConfig.provider === 'doubao' ? 'e.g. doubao-embedding-vision-251215' :
                            'e.g. text-embedding-3-small'
                          }
                          className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none" />
                        {embeddingConfig.provider === 'local' && (
                          <p className="text-xs text-gray-500 mt-1">Recommended: paraphrase-multilingual-MiniLM-L12-v2, BAAI/bge-small-zh-v1.5</p>
                        )}
                        {embeddingConfig.provider === 'doubao' && (
                          <p className="text-xs text-gray-500 mt-1">Recommended: doubao-embedding-vision-251215</p>
                        )}
                      </div>

                      {(embeddingConfig.provider === 'openai' || embeddingConfig.provider === 'doubao') && (
                        <>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">{t.configLlmApiKey}</label>
                            <input type="password" value={embeddingConfig.api_key || ''}
                              onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, api_key: e.target.value })}
                              placeholder="Enter API Key"
                              className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none" />
                          </div>
                          {embeddingConfig.provider === 'openai' && (
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-2">{t.configLlmBaseUrl} (Optional)</label>
                              <input type="text" value={embeddingConfig.base_url || ''}
                                onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, base_url: e.target.value })}
                                placeholder="e.g. https://api.openai.com/v1"
                                className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none" />
                            </div>
                          )}
                        </>
                      )}

                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                        <p className="text-sm text-amber-800">{t.configEmbeddingWarning}</p>
                      </div>

                      <button onClick={handleSaveEmbeddingConfig}
                        className="w-full px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors font-medium">{t.actionSave}</button>
                    </div>
                  </div>
                </>
              )}

              {/* 原始文档搜索路径 (localhost only) */}
              {isLocalhost && (
                <div className="bg-white rounded-2xl p-6 shadow-md">
                  <h3 className="text-lg font-bold text-gray-900 mb-1">{t.configOriginalDocPath}</h3>
                  <p className="text-xs text-gray-400 mb-4">{t.configOriginalDocPathDesc}</p>
                  <div className="flex gap-2 mb-4">
                    <input
                      type="text"
                      value={newDocPath}
                      onChange={(e) => setNewDocPath(e.target.value)}
                      placeholder={t.configOriginalDocPathPlaceholder}
                      className="flex-1 px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none text-sm"
                    />
                    <button
                      onClick={handleAddDocPath}
                      disabled={!newDocPath.trim()}
                      className="px-4 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {t.actionAdd}
                    </button>
                  </div>
                  {originalDocPaths.length === 0 ? (
                    <p className="text-sm text-gray-400">{t.configOriginalDocPathEmpty}</p>
                  ) : (
                    <div className="space-y-2">
                      {originalDocPaths.map((path) => (
                        <div key={path} className="flex items-center justify-between px-4 py-2 bg-gray-50 rounded-lg">
                          <span className="text-sm text-gray-700 font-mono truncate flex-1">{path}</span>
                          <button
                            onClick={() => handleRemoveDocPath(path)}
                            className="ml-2 px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded"
                          >
                            {t.actionDelete}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {dbStats && Object.keys(dbStats.type_counts).length > 0 && (
                <div className="bg-white rounded-2xl p-6 shadow-md">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">{t.configDocTypes}</h3>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(dbStats.type_counts).map(([type, count]) => (
                      <span key={type} className="px-4 py-2 bg-gray-100 rounded-full text-sm text-gray-700">
                        {fileTypeLabel[type] || type}：{count} {language === 'zh' ? '篇' : ''}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-3">
                <button onClick={loadDbStats}
                  className="px-5 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors text-sm font-medium">
                  {t.actionRefresh}
                </button>
                <button onClick={handleExport}
                  className="px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors text-sm font-medium">
                  {t.actionExport}
                </button>
                {isLocalhost && (
                  <>
                    <label className="px-5 py-2.5 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors text-sm font-medium cursor-pointer">
                      {t.actionImport}
                      <input type="file" accept=".json" onChange={handleImport} className="hidden" />
                    </label>
                    <button onClick={handleReset}
                      className="px-5 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors text-sm font-medium ml-auto">
                      {t.actionReset}
                    </button>
                  </>
                )}
              </div>

              {adminMessage && (
                <div className={`text-sm px-4 py-3 rounded-xl whitespace-pre-wrap ${adminMessage.includes('✓') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {adminMessage}
                </div>
              )}

              {isLocalhost && (
                <div className="bg-white rounded-2xl shadow-md p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{language === 'zh' ? '冗余文档检测' : 'Duplicate Detection'}</h3>
                      <p className="text-xs text-gray-400 mt-0.5">{language === 'zh' ? '找出内容高度相似的文档，帮助清理知识库' : 'Find highly similar documents to clean up the knowledge base'}</p>
                    </div>
                    <button
                      onClick={handleFindDuplicates}
                      disabled={duplicateSearching}
                      className="px-4 py-2 bg-orange-500 text-white rounded-xl hover:bg-orange-600 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {duplicateSearching ? (language === 'zh' ? '检测中...' : 'Scanning...') : (language === 'zh' ? '搜索冗余文档' : 'Find Duplicates')}
                    </button>
                  </div>

                  {duplicateSearched && duplicateGroups.length === 0 && (
                    <div className="text-sm text-green-600 bg-green-50 rounded-xl px-4 py-3">
                      {language === 'zh' ? '未发现冗余文档' : 'No duplicates found'}
                    </div>
                  )}

                  {duplicateGroups.length > 0 && (
                    <div className="space-y-4">
                      <p className="text-sm text-amber-700 bg-amber-50 rounded-xl px-4 py-2">
                        {language === 'zh' ? `发现 ${duplicateGroups.length} 组冗余文档，请选择每组中要保留的文档：` : `Found ${duplicateGroups.length} duplicate groups. Select which document to keep in each group:`}
                      </p>
                      {duplicateGroups.map((group, gi) => (
                        <div key={gi} className="border border-orange-100 rounded-xl p-4 bg-orange-50">
                          <p className="text-xs font-medium text-orange-700 mb-3">{language === 'zh' ? `第 ${gi + 1} 组` : `Group ${gi + 1}`}</p>
                          <div className="space-y-2">
                            {group.map((doc: any) => (
                              <label key={doc.id} className="flex items-center gap-3 cursor-pointer group">
                                <input
                                  type="radio"
                                  name={`dup-group-${gi}`}
                                  checked={duplicateKeep[gi] === doc.id}
                                  onChange={() => setDuplicateKeep(prev => ({ ...prev, [gi]: doc.id }))}
                                  className="accent-orange-500"
                                />
                                <div className="flex-1 min-w-0">
                                  <span className="text-sm font-medium text-gray-800 truncate block">{doc.title}</span>
                                  <span className="text-xs text-gray-400">
                                    {doc.file_type} · {doc.chunk_count} {language === 'zh' ? '个文本块' : 'chunks'}
                                    {' · '}{language === 'zh' ? '综合相似度' : 'score'} {(doc.max_similarity * 100).toFixed(1)}%
                                    {doc.emb_similarity !== undefined && ` · embedding ${(doc.emb_similarity * 100).toFixed(1)}%`}
                                    {doc.created_at && ` · ${new Date(doc.created_at).toLocaleDateString()}`}
                                  </span>
                                </div>
                                {duplicateKeep[gi] === doc.id
                                  ? <span className="text-xs text-green-600 font-medium shrink-0">{language === 'zh' ? '保留' : 'Keep'}</span>
                                  : <span className="text-xs text-red-400 shrink-0">{language === 'zh' ? '删除' : 'Delete'}</span>
                                }
                              </label>
                            ))}
                          </div>
                        </div>
                      ))}
                      <button
                        onClick={handleDeleteDuplicates}
                        className="px-5 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors text-sm font-medium"
                      >
                        {language === 'zh'
                          ? `删除未选中的 ${duplicateGroups.reduce((n, g, gi) => n + g.filter((d: any) => d.id !== duplicateKeep[gi]).length, 0)} 个冗余文档`
                          : `Delete ${duplicateGroups.reduce((n, g, gi) => n + g.filter((d: any) => d.id !== duplicateKeep[gi]).length, 0)} duplicate documents`
                        }
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="bg-white rounded-2xl shadow-md overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-4">
                  <h3 className="text-lg font-bold text-gray-900 shrink-0">
                    {t.configDocSearch}（{docSearch.trim()
                      ? `${documents.filter(d => d.title.toLowerCase().includes(docSearch.toLowerCase())).length} / ${documents.length}`
                      : documents.length} {language === 'zh' ? '篇' : ''}）
                  </h3>
                  <input
                    type="text"
                    value={docSearch}
                    onChange={(e) => setDocSearch(e.target.value)}
                    placeholder={t.configDocSearchPlaceholder}
                    className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:border-gray-400 outline-none"
                  />
                  {docSearch && (
                    <button onClick={() => setDocSearch('')} className="text-xs text-gray-400 hover:text-gray-600 shrink-0">{t.actionClear}</button>
                  )}
                  {isLocalhost && documents.length > 0 && (
                    <button
                      onClick={handleBatchBuildTreeIndex}
                      disabled={batchBuilding}
                      className="shrink-0 px-3 py-1.5 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {batchBuilding
                        ? (language === 'zh' ? '构建中...' : 'Building...')
                        : (language === 'zh' ? '🌳 批量构建树形索引' : '🌳 Build Tree Index')}
                    </button>
                  )}
                </div>
                {documents.length === 0 ? (
                  <div className="text-center text-gray-400 py-12">{language === 'zh' ? '暂无文档' : 'No documents'}</div>
                ) : (() => {
                  const filtered = docSearch.trim()
                    ? documents.filter(d => d.title.toLowerCase().includes(docSearch.toLowerCase()))
                    : documents;
                  return filtered.length === 0 ? (
                    <div className="text-center text-gray-400 py-12">{language === 'zh' ? '无匹配文档' : 'No matching documents'}</div>
                  ) : (
                    <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
                      {filtered.map((doc) => {
                        const kw = docSearch.trim().toLowerCase();
                        const title = doc.title;
                        const idx = kw ? title.toLowerCase().indexOf(kw) : -1;
                        return (
                          <div key={doc.id} className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors">
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              <span className="text-gray-400 text-xs w-8 shrink-0">#{doc.id}</span>
                              <span className={`text-xs font-bold px-1.5 py-0.5 rounded shrink-0 ${
                                doc.file_type === 'markdown' ? 'bg-blue-100 text-blue-700' :
                                doc.file_type === 'pdf' ? 'bg-red-100 text-red-700' :
                                doc.file_type === 'word' ? 'bg-indigo-100 text-indigo-700' :
                                'bg-gray-100 text-gray-600'
                              }`}>
                                {doc.file_type === 'markdown' ? 'MD' :
                                 doc.file_type === 'pdf' ? 'PDF' :
                                 doc.file_type === 'word' ? 'DOC' : 'TXT'}
                              </span>
                              <span title={doc.has_tree_index ? (language === 'zh' ? '已有树形索引' : 'Has tree index') : (language === 'zh' ? '无树形索引' : 'No tree index')}
                                className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${doc.has_tree_index ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-50 text-gray-300'}`}>
                                🌳
                              </span>
                              <div className="min-w-0">
                                <p className="text-gray-800 text-sm truncate">
                                  {idx >= 0 ? (
                                    <>
                                      {title.slice(0, idx)}
                                      <mark className="bg-yellow-200 text-gray-900 rounded px-0.5">{title.slice(idx, idx + kw.length)}</mark>
                                      {title.slice(idx + kw.length)}
                                    </>
                                  ) : title}
                                </p>
                                <p className="text-xs text-gray-400">{new Date(doc.created_at).toLocaleString()}</p>
                              </div>
                            </div>
                            {isLocalhost && (
                              <button onClick={() => handleDeleteDocument(doc)}
                                className="ml-4 px-3 py-1.5 text-xs text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors shrink-0">
                                {t.actionDelete}
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Codex Mode */}
          {mode === 'memory' && (
            <div className="w-full max-w-4xl space-y-6">
              {/* 文本输入区域 */}
              <div className="bg-white rounded-2xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-1">{t.memoryTextInput}</h3>
                <p className="text-xs text-gray-400 mb-3">{t.memoryTextInputDesc}</p>
                <form onSubmit={handleTextSubmit}>
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={textTitle}
                      onChange={(e) => setTextTitle(e.target.value)}
                      placeholder={t.memoryTitlePlaceholder}
                      className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none text-sm"
                      disabled={uploading}
                    />
                    <textarea
                      value={textContent}
                      onChange={(e) => setTextContent(e.target.value)}
                      placeholder={t.memoryContentPlaceholder}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none text-sm resize-none"
                      rows={5}
                      disabled={uploading}
                    />
                    <button
                      type="submit"
                      disabled={uploading || !textContent.trim()}
                      className="px-6 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {uploading ? t.actionSaving : t.memorySaveToKb}
                    </button>
                  </div>
                </form>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-1">{t.memoryUploadTitle}</h3>
                <p className="text-xs text-gray-400 mb-5">{t.memoryUploadDesc}</p>

                {/* 上传选项 */}
                <div className="mb-4 space-y-2">
                  <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={forceUpload}
                      onChange={(e) => setForceUpload(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300"
                    />
                    {t.memoryForceUpload}
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={overwriteUpload}
                      onChange={(e) => setOverwriteUpload(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300"
                    />
                    {t.memoryOverwriteUpload}
                  </label>
                </div>

                {/* 单文件上传 */}
                <div className="mb-5">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t.memoryUploadSingle}
                    <span className="ml-2 text-xs font-normal text-gray-400">.md · .pdf</span>
                  </label>
                  <input type="file" accept=".md,.pdf" disabled={uploading}
                    onChange={(e) => { if (e.target.files?.[0]) handleUpload(e.target.files[0]); }}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200 disabled:opacity-50" />
                </div>

                {/* 目录批量上传 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t.memoryUploadBatch}
                    <span className="ml-2 text-xs font-normal text-gray-400">{t.memoryUploadBatchDesc}</span>
                  </label>
                  <input ref={dirInputRef} type="file" {...{ webkitdirectory: "true", directory: "true" } as any} onChange={handleDirectoryUpload} disabled={uploading} className="hidden" />
                  <button type="button" onClick={() => dirInputRef.current?.click()} disabled={uploading}
                    className="px-4 py-2 text-sm font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors">
                    {language === 'zh' ? '选择路径' : 'Select Path'}
                  </button>
                </div>
              </div>

              {(uploading || uploadDone) && (
                <div className="bg-white rounded-2xl p-6 shadow-md">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">
                    {uploading ? t.memoryUploadProgress : t.memoryUploadResult}
                  </h3>
                  {uploadTotal > 0 && (
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>{uploading ? (language === 'zh' ? '正在处理...' : 'Processing...') : (language === 'zh' ? '已完成' : 'Completed')}</span>
                        <span>{uploadProgress}/{uploadTotal}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                          style={{ width: `${(uploadProgress / uploadTotal) * 100}%` }}></div>
                      </div>
                    </div>
                  )}
                  <div className="bg-gray-900 rounded-lg p-4 max-h-72 overflow-y-auto">
                    <div className="font-mono text-xs text-green-400 space-y-1">
                      {uploadLogs.map((log, i) => <div key={i} className="whitespace-pre-wrap">{log}</div>)}
                    </div>
                  </div>
                </div>
              )}

              {documents.length > 0 && (
                <div className="bg-white rounded-2xl p-6 shadow-md">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">{t.memoryDocumentList} ({documents.length})</h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {documents.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className={`text-xs font-bold px-1.5 py-0.5 rounded shrink-0 ${
                            doc.file_type === 'markdown' ? 'bg-blue-100 text-blue-700' :
                            doc.file_type === 'pdf' ? 'bg-red-100 text-red-700' :
                            doc.file_type === 'word' ? 'bg-indigo-100 text-indigo-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {doc.file_type === 'markdown' ? 'MD' :
                             doc.file_type === 'pdf' ? 'PDF' :
                             doc.file_type === 'word' ? 'DOC' : 'TXT'}
                          </span>
                          <span className="text-gray-800 truncate text-sm">{doc.title}</span>
                        </div>
                        <span className="text-xs text-gray-400 shrink-0 ml-3">{new Date(doc.created_at).toLocaleDateString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {message && (
                <div className={`text-sm ${message.includes('✓') || message.includes('成功') ? 'text-green-600' : 'text-red-600'}`}>{message}</div>
              )}
            </div>
          )}

        </main>
      )}

      {/* ===== Bottom Input (chat / search) ===== */}
      {mode !== 'config' && mode !== 'memory' && (
        <div className="fixed bottom-0 left-0 right-0 bg-gray-50/95 backdrop-blur border-t border-gray-200 p-4">
          <div className="max-w-4xl mx-auto">
            <form onSubmit={getSubmitHandler()}>
              <div className="bg-white rounded-2xl border-2 border-gray-200 focus-within:border-gray-400 transition-colors">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={
                    mode === 'chat' ? (useRag ? t.chatPlaceholder : t.chatPlaceholderNoRag) :
                    (language === 'zh' ? '记录新的想法...' : 'Record new idea...')
                  }
                  className="w-full px-5 py-3.5 text-base text-gray-900 bg-transparent outline-none rounded-t-2xl"
                  disabled={uploading || chatting}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { getSubmitHandler()(e as any); } }}
                />
                <div className="flex items-center justify-between px-4 py-2.5 border-t border-gray-100">
                  <div className="flex items-center gap-4">
                    {mode === 'chat' && (
                      <>
                        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                          <input type="checkbox" checked={useRag} onChange={(e) => setUseRag(e.target.checked)} className="w-4 h-4 rounded border-gray-300" />
                          {t.optionKnowledgeBase}
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                          <input type="checkbox" checked={useOriginalDoc} onChange={(e) => setUseOriginalDoc(e.target.checked)} className="w-4 h-4 rounded border-gray-300" />
                          {t.optionOriginalDoc}
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                          <input type="checkbox" checked={useWebSearch} onChange={(e) => setUseWebSearch(e.target.checked)} className="w-4 h-4 rounded border-gray-300" />
                          {t.optionWebSearch}
                        </label>
                      </>
                    )}
                  </div>
                  <button type="submit"
                    disabled={(mode === 'chat' ? chatting : uploading) || !query.trim()}
                    className="px-5 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                    {mode === 'chat' ? (chatting ? t.chatThinking : t.chatSend) : (uploading ? t.actionSaving : t.actionSave)}
                  </button>
                </div>
              </div>
            </form>
            <div className="text-center text-xs text-gray-400 mt-2">{t.footerText}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
