import React, { useState, useEffect, useRef } from 'react';
import { uploadFile, saveText, chatWithRAG, configureLLM, getLLMConfig, getDocuments, getDbStats, deleteDocument, resetDatabase, getEmbeddingConfig, configureEmbedding, exportDatabase, importDatabase, getOriginalDocPaths, addOriginalDocPath, removeOriginalDocPath, batchBuildTreeIndex, findDuplicates, configureCodeAnalysisLLM, getCodeAnalysisLLMConfig, listUsers, createUser, deleteUser, embedTexts, extractFileText, changePassword, changeUsername } from './services/api';
import { saveLocalDoc, listLocalDocs, deleteLocalDoc, searchLocalDocs, chunkText } from './db/localDb';
import MarkdownRenderer, { SimpleCodeRenderer } from './components/MarkdownRenderer';
import { useTranslation } from './i18n/useTranslation';
import { useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import './index.css';

type Mode = 'memory' | 'chat' | 'config' | 'users';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  webSources?: any[];
  originalDocStatus?: string;
  codeAnalysisStatus?: string;
  codeAnalysisDetail?: string;
  treeNodes?: any[];
  elapsed?: number;
  timings?: Record<string, number>;
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
  const { user, isAdmin, logout } = useAuth();
  const [showLogin, setShowLogin] = useState(false);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
  const [usersMessage, setUsersMessage] = useState('');
  const [accountNewUsername, setAccountNewUsername] = useState('');
  const [accountNewPassword, setAccountNewPassword] = useState('');
  const [accountConfirmPassword, setAccountConfirmPassword] = useState('');
  const [accountCurrentPassword, setAccountCurrentPassword] = useState('');
  const [accountMessage, setAccountMessage] = useState('');
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
  const [useCodeAnalysis, setUseCodeAnalysis] = useState(true);  // 是否启用源码分析
  const [historyTurns, setHistoryTurns] = useState(0);  // 携带历史轮数，0=不携带
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const toggleSection = (key: string) => setExpandedSections(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s; });
  const [chattingElapsed, setChattingElapsed] = useState(0);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const chattingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);

  const getSavedConfig = (): LLMConfig => {
    const saved = localStorage.getItem('llm_config');
    if (saved) { try { return JSON.parse(saved); } catch {} }
    return { provider: 'custom', model: '', base_url: '', api_key: '' };
  };

  const [llmConfig, setLlmConfig] = useState<LLMConfig>(getSavedConfig());
  const [codeAnalysisConfig, setCodeAnalysisConfig] = useState<LLMConfig>({ provider: '', model: 'claude-sonnet-4-6', base_url: '', api_key: '' });
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
  const [docsMessage, setDocsMessage] = useState('');
  const [configTab, setConfigTab] = useState<'model' | 'database' | 'docs'>('model');

  // 本地文档（存储在浏览器 IndexedDB，不上传服务端）
  const [localDocs, setLocalDocs] = useState<any[]>([]);
  const [localUploading, setLocalUploading] = useState(false);
  const [localMessage, setLocalMessage] = useState('');

  // 用户设置弹窗（非管理员的个人 LLM 配置）
  const [showUserSettings, setShowUserSettings] = useState(false);
  const [userSettingsMessage, setUserSettingsMessage] = useState('');

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
  }, []);

  // 管理员登录时：关闭用户设置弹窗 + 同步 LLM 配置到服务端
  useEffect(() => {
    if (!isAdmin) return;
    setShowUserSettings(false);
    const savedConfig = localStorage.getItem('llm_config');
    if (savedConfig) {
      try {
        const config = JSON.parse(savedConfig);
        if (config.api_key && config.api_key.trim()) {
          configureLLM(config).catch(console.error);
        }
      } catch {}
    }
  }, [isAdmin]);

  useEffect(() => {
    if (mode === 'config') { loadDbStats(); loadDocuments(); loadOriginalDocPaths(); }
    if (mode === 'users' && isAdmin) { loadUsers(); }
    if (mode === 'memory') { loadLocalDocs(); }
  }, [mode, isAdmin]);

  useEffect(() => {
    if (chatting) {
      setChattingElapsed(0);
      chattingTimerRef.current = setInterval(() => setChattingElapsed(s => s + 1), 1000);
    } else {
      if (chattingTimerRef.current) { clearInterval(chattingTimerRef.current); chattingTimerRef.current = null; }
    }
    return () => { if (chattingTimerRef.current) clearInterval(chattingTimerRef.current); };
  }, [chatting]);

  const loadLLMConfig = async () => {
    try { await getLLMConfig(); } catch {}
    try {
      const c = await getCodeAnalysisLLMConfig();
      setCodeAnalysisConfig({ provider: c.provider || '', model: c.model || 'claude-sonnet-4-6', base_url: c.base_url || '', api_key: '' });
    } catch {}
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

  const loadUsers = async () => {
    try { setUsersList(await listUsers()); } catch {}
  };

  const loadDbStats = async () => {
    setStatsLoading(true);
    try { setDbStats(await getDbStats()); } catch {} finally { setStatsLoading(false); }
  };

  const loadLocalDocs = async () => {
    try { setLocalDocs(await listLocalDocs()); } catch {}
  };

  const handleLocalFileUpload = async (file: File) => {
    setLocalUploading(true);
    setLocalMessage('');
    try {
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      let text = '';
      if (ext === 'txt' || ext === 'md') {
        text = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve((e.target?.result as string) || '');
          reader.onerror = reject;
          reader.readAsText(file, 'utf-8');
        });
      } else {
        text = await extractFileText(file);
      }
      if (!text.trim()) {
        setLocalMessage(language === 'zh' ? '✗ 无法提取文本内容' : '✗ Failed to extract text');
        return;
      }
      const chunks = chunkText(text);
      const embeddings = await embedTexts(chunks);
      await saveLocalDoc({
        id: crypto.randomUUID(),
        title: file.name,
        fileType: ext || 'text',
        fileSize: file.size,
        createdAt: new Date().toISOString(),
        chunkCount: chunks.length,
        chunks: chunks.map((t, i) => ({ text: t, embedding: embeddings[i], index: i })),
      });
      setLocalMessage(language === 'zh'
        ? `✓ 已保存 "${file.name}"（${chunks.length} 个文本块）`
        : `✓ Saved "${file.name}" (${chunks.length} chunks)`);
      loadLocalDocs();
    } catch (e: any) {
      setLocalMessage(`✗ ${e.response?.data?.detail || e.message}`);
    } finally {
      setLocalUploading(false);
    }
  };

  const handleDeleteLocalDoc = async (id: string, title: string) => {
    showConfirm(
      language === 'zh' ? '删除本地文档' : 'Delete local document',
      language === 'zh' ? `确认删除 "${title}"？此操作无法撤销。` : `Delete "${title}"? This cannot be undone.`,
      async () => {
        setConfirm(p => ({ ...p, visible: false }));
        await deleteLocalDoc(id);
        loadLocalDocs();
      }
    );
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
    setTimeout(() => {
      const form = document.querySelector<HTMLFormElement>('form[data-chat-form]');
      if (form) form.requestSubmit();
    }, 0);
  };

  const handleDeleteDocument = (doc: any) => {
    showConfirm(t.dialogDeleteTitle, t.dialogDeleteMessage.replace('{title}', doc.title), async () => {
      setConfirm(p => ({ ...p, visible: false }));
      try {
        await deleteDocument(doc.id);
        setDocsMessage(`${t.msgSuccess} ${t.msgDeleteSuccess}：${doc.title}`);
        // 从冗余组中移除已删除的文档，组内只剩1个时整组消除
        setDuplicateGroups(prev =>
          prev
            .map(group => group.filter((d: any) => d.id !== doc.id))
            .filter(group => group.length >= 2)
        );
        await loadDocuments(); await loadDbStats();
      } catch (e: any) { setDocsMessage(`${t.msgError} ${language === 'zh' ? '删除失败' : 'Delete failed'}：${e.response?.data?.detail || e.message}`); }
    });
  };

  const handleBatchBuildTreeIndex = async () => {
    setBatchBuilding(true);
    setDocsMessage('');
    try {
      const result = await batchBuildTreeIndex();
      if (result.triggered_count === 0) {
        setDocsMessage(`✓ ${language === 'zh' ? '所有文档均已有树形索引，无需重建' : 'All documents already have tree index'}`);
      } else {
        setDocsMessage(`✓ ${language === 'zh' ? `已触发 ${result.triggered_count} 篇文档的树形索引构建，后台处理中...` : `Triggered tree index build for ${result.triggered_count} documents, processing in background...`}`);
      }
      // 延迟刷新列表，让后台有时间处理部分文档
      setTimeout(() => loadDocuments(), 3000);
    } catch (e: any) {
      setDocsMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    } finally {
      setBatchBuilding(false);
    }
  };

  const handleFindDuplicates = async () => {
    setDuplicateSearching(true);
    setDuplicateSearched(false);
    setDuplicateGroups([]);
    try {
      const result = await findDuplicates(0.97);
      setDuplicateGroups(result.groups || []);
    } catch (e: any) {
      setAdminMessage(`${t.msgError} ${e.response?.data?.detail || e.message}`);
    } finally {
      setDuplicateSearching(false);
      setDuplicateSearched(true);
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
    setChatMessages(prev => [...prev, userMessage]);
    setQuery('');
    setChatting(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const t0 = Date.now();
    const history = historyTurns > 0
      ? chatMessages.slice(-(historyTurns * 2)).map(m => ({ role: m.role, content: m.content }))
      : [];
    try {
      // 搜索用户本地文档
      let localContext: string[] | undefined;
      if (useRag) {
        try {
          const [queryEmb] = await embedTexts([userMessage.content]);
          const localResults = await searchLocalDocs(queryEmb, 5);
          if (localResults.length > 0) localContext = localResults;
        } catch {}
      }

      // 非管理员使用个人 LLM 配置
      const savedCfg = localStorage.getItem('llm_config');
      let userLlmConfig: typeof llmConfig | undefined;
      if (!isAdmin && savedCfg) {
        try {
          const cfg = JSON.parse(savedCfg);
          if (cfg.api_key?.trim()) userLlmConfig = cfg;
        } catch {}
      }

      const r = await chatWithRAG(
        userMessage.content, 20, useRag, useWebSearch, useOriginalDoc,
        history, true, controller.signal, useCodeAnalysis,
        localContext,
        userLlmConfig,
      );
      const elapsed = (Date.now() - t0) / 1000;
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: r.answer,
        sources: r.sources,
        webSources: r.web_sources,
        originalDocStatus: r.original_doc_status,
        codeAnalysisStatus: r.code_analysis_status,
        codeAnalysisDetail: r.code_analysis_detail,
        treeNodes: r.tree_nodes,
        elapsed,
        timings: r.timings,
      }]);
    } catch (e: any) {
      if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') {
        const elapsed = (Date.now() - t0) / 1000;
        setChatMessages(prev => [...prev, { role: 'assistant', content: language === 'zh' ? '已停止。' : 'Stopped.', elapsed }]);
      } else {
        const elapsed = (Date.now() - t0) / 1000;
        setChatMessages(prev => [...prev, { role: 'assistant', content: `抱歉，对话失败: ${e.response?.data?.detail || e.message}`, elapsed }]);
      }
    } finally {
      setChatting(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopChat = () => {
    abortControllerRef.current?.abort();
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
        setUploadLogs(prev => [...prev, `⚠️ 发现相似文档：${similarTitles} (${elapsed}s)`]);
        setUploading(false); setUploadDone(true);
        // 弹出确认框让用户决定是否强制上传
        showConfirm(
          language === 'zh' ? '发现相似文档' : 'Similar documents found',
          (language === 'zh'
            ? `已存在相似文档：${similarTitles}\n\n是否仍要继续上传？`
            : `Similar documents already exist: ${similarTitles}\n\nContinue uploading anyway?`),
          async () => {
            setConfirm(p => ({ ...p, visible: false }));
            setUploading(true); setUploadDone(false);
            try {
              const r2 = await uploadFile(file, true, overwriteUpload);
              const e2 = ((Date.now() - t0) / 1000).toFixed(1);
              setUploadLogs(prev => [...prev, `✓ ${r2.title}（${r2.chunks_count} 个文本块，耗时 ${e2}s）`]);
              setMessage(`✓ 上传成功: ${r2.title}`);
              setUploadProgress(1);
              loadDocuments();
            } catch (err: any) {
              setMessage(`✗ 上传失败: ${err.response?.data?.detail || err.message}`);
            } finally {
              setUploading(false); setUploadDone(true);
            }
          }
        );
        return;
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
    if (isAdmin) {
      try {
        await configureLLM(llmConfig);
        localStorage.setItem('llm_config', JSON.stringify(llmConfig));
        setMessage(`${t.msgSuccess} ${t.msgConfigSuccess}`);
        setTimeout(() => setMessage(''), 3000);
      } catch (e: any) { setMessage(`${t.msgError} ${language === 'zh' ? '配置失败' : 'Configuration failed'}: ${e.response?.data?.detail || e.message}`); }
    } else {
      // 普通用户：仅保存到 localStorage，作为个人 LLM 配置
      localStorage.setItem('llm_config', JSON.stringify(llmConfig));
      setUserSettingsMessage(language === 'zh' ? '✓ 配置已保存' : '✓ Config saved');
      setTimeout(() => setUserSettingsMessage(''), 3000);
    }
  };

  const handleSaveCodeAnalysisConfig = async () => {
    try {
      await configureCodeAnalysisLLM(codeAnalysisConfig);
      setMessage(`✓ ${language === 'zh' ? '代码分析 LLM 配置成功' : 'Code analysis LLM configured'}`);
      setTimeout(() => setMessage(''), 3000);
    } catch (e: any) { setMessage(`✗ ${language === 'zh' ? '配置失败' : 'Configuration failed'}: ${(e as any).response?.data?.detail || (e as any).message}`); }
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

  const modeLabels: Record<string, string> = {
    chat: t.modeChat,
    memory: t.modeMemory,
    ...(isAdmin ? { config: t.modeConfig } : {}),
    ...(isAdmin ? { users: language === 'zh' ? '👥 用户管理' : '👥 Users' } : {}),
  };

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

      {/* User Settings Modal (non-admin personal LLM config) */}
      {showUserSettings && !isAdmin && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-gray-900">{language === 'zh' ? '个人对话模型配置' : 'Personal LLM Config'}</h3>
              <button onClick={() => setShowUserSettings(false)} className="text-gray-400 hover:text-gray-600">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-5">
              {language === 'zh'
                ? '配置你自己的大模型，仅存储在本地浏览器，不上传服务器。对话时优先使用此配置。'
                : 'Configure your own LLM. Stored locally in your browser only. Used for all your conversations.'}
            </p>
            <div className="space-y-4">
              {[
                { label: language === 'zh' ? '接口地址 (Base URL)' : 'Base URL', key: 'base_url', type: 'text', placeholder: 'e.g. https://ark.cn-beijing.volces.com/api/v3' },
                { label: 'API Key', key: 'api_key', type: 'password', placeholder: 'sk-...' },
                { label: language === 'zh' ? '模型名称' : 'Model', key: 'model', type: 'text', placeholder: 'e.g. doubao-pro-4k, gpt-4o, qwen-plus' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">{f.label}</label>
                  <input type={f.type} value={(llmConfig as any)[f.key] || ''}
                    onChange={(e) => setLlmConfig({ ...llmConfig, [f.key]: e.target.value })}
                    placeholder={f.placeholder}
                    className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none text-sm" />
                </div>
              ))}
              <button
                onClick={handleSaveLLMConfig}
                className="w-full px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors font-medium"
              >
                {language === 'zh' ? '保存配置' : 'Save Config'}
              </button>
              {userSettingsMessage && (
                <div className={`text-sm text-center ${userSettingsMessage.includes('✓') ? 'text-green-600' : 'text-red-600'}`}>
                  {userSettingsMessage}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Login Modal */}
      {showLogin && <LoginPage onClose={() => setShowLogin(false)} />}

      {/* Confirm Dialog */}
      {confirm.visible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-xl font-bold text-gray-900 mb-3">{confirm.title}</h3>
            <p className="text-gray-600 mb-6 leading-relaxed whitespace-pre-wrap break-all">{confirm.message}</p>
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
        <div className="w-full max-w-4xl flex justify-end mb-2">
          {user ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">
                {user.username}{user.role === 'admin' && <span className="ml-1 text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">admin</span>}
              </span>
              {!isAdmin && (
                <button
                  onClick={() => setShowUserSettings(true)}
                  title={language === 'zh' ? '个人设置' : 'Settings'}
                  className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-2 py-1 rounded-lg"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline' }}>
                    <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                  </svg>
                </button>
              )}
              <button
                onClick={() => switchLanguage(language === 'zh' ? 'en' : 'zh')}
                className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-2 py-1 rounded-lg hover:bg-gray-50"
              >
                {language === 'zh' ? 'EN' : '中文'}
              </button>
              <button onClick={logout} className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-2 py-1 rounded-lg">
                {language === 'zh' ? '退出' : 'Logout'}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => switchLanguage(language === 'zh' ? 'en' : 'zh')}
                className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-2 py-1 rounded-lg hover:bg-gray-50"
              >
                {language === 'zh' ? 'EN' : '中文'}
              </button>
              <button
                onClick={() => setShowUserSettings(true)}
                title={language === 'zh' ? '对话模型配置' : 'LLM Settings'}
                className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 px-2 py-1 rounded-lg"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline' }}>
                  <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                </svg>
              </button>
              <button onClick={() => setShowLogin(true)} className="text-sm text-gray-500 hover:text-gray-800 border border-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-50">
                {language === 'zh' ? '管理员登录' : 'Admin Login'}
              </button>
            </div>
          )}
        </div>
        <h1 className="text-5xl font-bold text-gray-900 mb-8">{t.appName}</h1>
        <div className="flex gap-3 flex-wrap justify-center">
          {(Object.keys(modeLabels) as Mode[]).map((m) => (
            <button key={m} onClick={() => setMode(m as Mode)}
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
                            <button onClick={() => toggleSection(`think-${index}`)} className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 font-medium mb-1 w-full text-left">
                              {t.thinkingProcess}
                              <svg className={`ml-1 transition-transform ${expandedSections.has(`think-${index}`) ? 'rotate-180' : ''}`} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                            </button>
                            {expandedSections.has(`think-${index}`) && (
                              <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">{thinking}</p>
                            )}
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
                    <div className="mt-3 text-xs text-gray-400 flex flex-wrap gap-x-3 gap-y-0.5">
                      <span>{language === 'zh' ? '总耗时' : 'Total'}: {msg.elapsed.toFixed(1)}s</span>
                      {msg.timings?.['search/tree_index'] !== undefined && (
                        <span className="text-gray-500">检索: {msg.timings['search/tree_index']}s</span>
                      )}
                      {msg.timings?.['original_doc_lookup'] !== undefined && (
                        <span className="text-gray-500">原文: {msg.timings['original_doc_lookup']}s</span>
                      )}
                      {msg.timings?.['code_analysis'] !== undefined && (
                        <span className="text-blue-400/70">源码分析: {msg.timings['code_analysis']}s</span>
                      )}
                      {msg.timings?.['llm_generate'] !== undefined && (
                        <span className="text-gray-500">生成: {msg.timings['llm_generate']}s</span>
                      )}
                    </div>
                  )}
                  {((msg.sources?.length ?? 0) > 0 || msg.codeAnalysisDetail || (msg.webSources?.length ?? 0) > 0) && (
                    <div className="mt-4 pt-4 border-t border-gray-200 divide-y divide-gray-100 text-xs text-gray-500">
                      {/* 命中章节 */}
                      {msg.treeNodes && msg.treeNodes.length > 0 && (
                        <div className="py-2">
                          <button onClick={() => toggleSection(`tree-${index}`)} className="flex items-center gap-1 font-medium text-gray-500 hover:text-gray-700 w-full text-left">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                            {language === 'zh' ? '命中章节' : 'Matched sections'}
                            <svg className={`ml-auto transition-transform ${expandedSections.has(`tree-${index}`) ? 'rotate-180' : ''}`} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                          </button>
                          {expandedSections.has(`tree-${index}`) && Array.from(new Map(msg.treeNodes.map((n: any) => [`${n.doc_id}-${n.node_id}`, n])).values()).map((n: any, i: number) => (
                            <div key={i} className="pl-4 text-gray-400 mb-0.5 mt-1"><em>{n.doc_title} › {n.node_title}</em></div>
                          ))}
                        </div>
                      )}
                      {/* 知识库来源 */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="py-2">
                          <button onClick={() => toggleSection(`sources-${index}`)} className="flex items-center gap-1 font-medium text-gray-500 hover:text-gray-700 w-full text-left">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                            {t.sourceKnowledgeBase}
                            <svg className={`ml-auto transition-transform ${expandedSections.has(`sources-${index}`) ? 'rotate-180' : ''}`} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                          </button>
                          {expandedSections.has(`sources-${index}`) && Array.from(new Map(msg.sources.map((s: any) => [s.document_id, s])).values()).map((s: any, i: number) => (
                            <div key={i} className="pl-4 text-gray-400 mb-0.5 mt-1">文档 #{s.document_id} <em>({(s.similarity * 100).toFixed(0)}% 匹配)</em></div>
                          ))}
                        </div>
                      )}
                      {/* 原始文档查找 */}
                      {msg.originalDocStatus && (
                        <div className="py-2">
                          <button onClick={() => toggleSection(`origdoc-${index}`)} className="flex items-center gap-1 font-medium text-gray-500 hover:text-gray-700 w-full text-left">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                            {language === 'zh' ? '原始文档' : 'Source docs'}
                            <svg className={`ml-auto transition-transform ${expandedSections.has(`origdoc-${index}`) ? 'rotate-180' : ''}`} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                          </button>
                          {expandedSections.has(`origdoc-${index}`) && (
                            <div className="pl-4 text-gray-400 whitespace-pre-wrap font-mono text-[11px] mt-1">{msg.originalDocStatus}</div>
                          )}
                        </div>
                      )}
                      {/* 源码分析结论 */}
                      {msg.codeAnalysisDetail && (
                        <div className="py-2">
                          <button onClick={() => toggleSection(`code-${index}`)} className="flex items-center gap-1 font-medium text-gray-500 hover:text-gray-700 w-full text-left">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                            {language === 'zh' ? '源码分析结论' : 'Source Analysis'}
                            <svg className={`ml-auto transition-transform ${expandedSections.has(`code-${index}`) ? 'rotate-180' : ''}`} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                          </button>
                          {expandedSections.has(`code-${index}`) && (
                            <div className="pl-4 mt-1">
                              <SimpleCodeRenderer content={msg.codeAnalysisDetail} />
                            </div>
                          )}
                        </div>
                      )}
                      {/* 网络搜索 */}
                      {msg.webSources && msg.webSources.length > 0 && (
                        <div className="py-2">
                          <p className="flex items-center gap-1 font-medium text-gray-500 mb-1">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                            {t.sourceWebSearch}
                          </p>
                          {msg.webSources.map((s: any, i: number) => (
                            <div key={i} className="pl-4 text-gray-400 mb-0.5">
                              <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:underline">{s.title}</a>
                            </div>
                          ))}
                        </div>
                      )}
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

            {/* 等待动画 */}
            {chatting && (() => {
              if (!useCodeAnalysis) {
                return (
                  <div className="flex items-start gap-3">
                    <div className="bg-white rounded-2xl px-6 py-4 shadow-md">
                      <div className="flex gap-1 items-center">
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                );
              }
              const STAGES = [
                { until: 8,   zh: '查询知识库', en: 'Searching' },
                { until: 25,  zh: '阅读文档',   en: 'Reading docs' },
                { until: 75,  zh: '分析代码',   en: 'Analyzing code' },
                { until: 90,  zh: '交叉验证',   en: 'Cross-checking' },
                { until: Infinity, zh: '总结',  en: 'Summarizing' },
              ];
              const TOTAL_EST = 130;
              const currentIdx = STAGES.findIndex(s => chattingElapsed < s.until);
              const safeIdx = currentIdx === -1 ? STAGES.length - 1 : currentIdx;
              const remaining = Math.max(0, TOTAL_EST - chattingElapsed);
              const stageLabel = language === 'zh' ? STAGES[safeIdx].zh : STAGES[safeIdx].en;
              // Icon paths for each stage
              const iconPaths = [
                <circle key="s" cx="10" cy="10" r="6" />,  // search
                <><path key="b1" d="M2 3h5a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path key="b2" d="M22 3h-5a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h6z"/></>,  // book
                <><polyline key="c1" points="15 17 21 12 15 7"/><polyline key="c2" points="9 7 3 12 9 17"/></>,  // code
                <><polyline key="v1" points="22 4 22 9 17 9"/><polyline key="v2" points="2 20 2 15 7 15"/><path key="v3" d="M3.5 9a9 9 0 0 1 14.8-3.4L22 9M2 15l3.7 3.7A9 9 0 0 0 20.5 15"/></>,  // refresh
                <><path key="w1" d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path key="w2" d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/></>,  // pen
              ];
              const spinDur = ['1.8s','1.5s','2.5s','1.2s','2s'][safeIdx];
              return (
                <div className="flex items-start gap-3">
                  <div className="bg-white rounded-2xl px-5 py-3 shadow-md flex items-center gap-3">
                    {/* Spinning ring + static icon */}
                    <div className="relative w-7 h-7 flex items-center justify-center flex-shrink-0">
                      <svg className="absolute inset-0 animate-spin" style={{ animationDuration: spinDur }} width="28" height="28" viewBox="0 0 28 28" fill="none">
                        <circle cx="14" cy="14" r="12" stroke="#bfdbfe" strokeWidth="2.5" strokeDasharray="18 56" strokeLinecap="round"/>
                      </svg>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        {iconPaths[safeIdx]}
                        {safeIdx === 0 && <line x1="18" y1="18" x2="14.5" y2="14.5" />}
                      </svg>
                    </div>
                    <span className="text-sm text-gray-700 font-medium">{stageLabel}...</span>
                    <span className="text-xs text-gray-400">
                      {remaining > 0
                        ? (language === 'zh' ? `还剩约 ${remaining} 秒` : `~${remaining}s left`)
                        : (language === 'zh' ? '即将完成' : 'Almost done')}
                    </span>
                  </div>
                </div>
              );
            })()}

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

              {/* Tab Bar */}
              <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
                {(['model', 'database', 'docs'] as const).map((tab) => {
                  const labels = { model: language === 'zh' ? '模型配置' : 'Model', database: language === 'zh' ? '数据库配置' : 'Database', docs: language === 'zh' ? '文档列表' : 'Documents' };
                  return (
                    <button
                      key={tab}
                      onClick={() => setConfigTab(tab)}
                      className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                        configTab === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      {labels[tab]}
                    </button>
                  );
                })}
              </div>

              {/* ===== 模型配置 Tab ===== */}
              {configTab === 'model' && (
                <div className="space-y-6">

              {/* LLM + Embedding Config (localhost only) */}
              {isAdmin && (
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
                    <h2 className="text-xl font-bold text-gray-900 mb-1">{language === 'zh' ? '代码分析 LLM' : 'Code Analysis LLM'}</h2>
                    <p className="text-sm text-gray-500 mb-5">{language === 'zh' ? '用于源码分析的专用模型，留空则使用主 LLM。推荐使用 Claude（Anthropic）。' : 'Dedicated model for code analysis. Leave empty to use main LLM. Claude (Anthropic) recommended.'}</p>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">{language === 'zh' ? '提供商' : 'Provider'}</label>
                        <select value={codeAnalysisConfig.provider} onChange={(e) => setCodeAnalysisConfig({ ...codeAnalysisConfig, provider: e.target.value })}
                          className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none bg-white">
                          <option value="">{language === 'zh' ? '不启用（使用主 LLM）' : 'Disabled (use main LLM)'}</option>
                          <option value="anthropic">Anthropic (Claude)</option>
                          <option value="openai">OpenAI</option>
                          <option value="doubao">{language === 'zh' ? '豆包 (Doubao)' : 'Doubao'}</option>
                          <option value="custom">{language === 'zh' ? '其他兼容接口' : 'Custom OpenAI-compatible'}</option>
                        </select>
                      </div>
                      {codeAnalysisConfig.provider && [
                        { label: language === 'zh' ? '模型名称' : 'Model', key: 'model', type: 'text', placeholder: 'claude-sonnet-4-6' },
                        { label: 'Base URL', key: 'base_url', type: 'text', placeholder: 'https://api.anthropic.com' },
                        { label: 'API Key', key: 'api_key', type: 'password', placeholder: 'sk-ant-...' },
                      ].map(f => (
                        <div key={f.key}>
                          <label className="block text-sm font-medium text-gray-700 mb-2">{f.label}</label>
                          <input type={f.type} value={(codeAnalysisConfig as any)[f.key] || ''}
                            onChange={(e) => setCodeAnalysisConfig({ ...codeAnalysisConfig, [f.key]: e.target.value })}
                            placeholder={f.placeholder}
                            className="w-full px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-gray-400 outline-none" />
                        </div>
                      ))}
                      <button onClick={handleSaveCodeAnalysisConfig}
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
                </div>
              )}

              {/* ===== 数据库配置 Tab ===== */}
              {configTab === 'database' && (
                <div className="space-y-6">

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

              {/* 原始文档搜索路径 (localhost only) */}
              {isAdmin && (
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
                {isAdmin && (
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

              {isAdmin && (
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
                        {language === 'zh' ? `发现 ${duplicateGroups.length} 组冗余文档：` : `Found ${duplicateGroups.length} duplicate group(s):`}
                      </p>
                      {duplicateGroups.map((group, gi) => (
                        <div key={gi} className="border border-orange-100 rounded-xl p-4 bg-orange-50">
                          <p className="text-xs font-medium text-orange-700 mb-3">{language === 'zh' ? `第 ${gi + 1} 组` : `Group ${gi + 1}`}</p>
                          <div className="space-y-2">
                            {group.map((doc: any) => (
                              <div key={doc.id} className="flex items-center gap-3">
                                <div className="flex-1 min-w-0">
                                  <span className="text-sm font-medium text-gray-800 truncate block">{doc.title}</span>
                                  <span className="text-xs text-gray-400">
                                    {doc.file_type} · {doc.chunk_count} {language === 'zh' ? '个文本块' : 'chunks'}
                                    {' · '}{language === 'zh' ? '相似度' : 'score'} {(doc.max_similarity * 100).toFixed(1)}%
                                    {doc.created_at && ` · ${new Date(doc.created_at).toLocaleDateString()}`}
                                  </span>
                                </div>
                                <button
                                  className="text-xs text-red-500 hover:text-red-700 hover:underline shrink-0 font-medium"
                                  onClick={async () => {
                                    try {
                                      await deleteDocument(doc.id);
                                      setDuplicateGroups(prev =>
                                        prev
                                          .map(g => g.filter((d: any) => d.id !== doc.id))
                                          .filter(g => g.length >= 2)
                                      );
                                      await loadDocuments();
                                      await loadDbStats();
                                    } catch (err: any) {
                                      setAdminMessage(`${t.msgError} ${err.response?.data?.detail || err.message}`);
                                    }
                                  }}
                                >
                                  {language === 'zh' ? '删除' : 'Delete'}
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
                </div>
              )}

              {/* ===== 文档列表 Tab ===== */}
              {configTab === 'docs' && (
                <div className="space-y-6">

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
                  {isAdmin && documents.length > 0 && (
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
                                <p className="text-gray-800 text-sm truncate" title={doc.title}>
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
                            {isAdmin && (
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

              {docsMessage && (
                <div className={`text-sm px-4 py-3 rounded-xl whitespace-pre-wrap ${docsMessage.includes('✓') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {docsMessage}
                </div>
              )}
                </div>
              )}

            </div>
          )}

          {/* Users Mode (admin only) */}
          {mode === 'users' && isAdmin && (
            <div className="w-full max-w-2xl space-y-6">

              {/* 账号设置 */}
              <div className="bg-white rounded-2xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-4">{language === 'zh' ? '我的账号' : 'My Account'}</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">{language === 'zh' ? '当前密码（修改任何信息都需要验证）' : 'Current password (required for any change)'}</label>
                    <input type="password" value={accountCurrentPassword} onChange={e => setAccountCurrentPassword(e.target.value)}
                      placeholder={language === 'zh' ? '当前密码' : 'Current password'}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">{language === 'zh' ? '新登录名（留空不修改）' : 'New username (optional)'}</label>
                    <input type="text" value={accountNewUsername} onChange={e => setAccountNewUsername(e.target.value)}
                      placeholder={language === 'zh' ? '新用户名' : 'New username'}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{language === 'zh' ? '新密码（留空不修改）' : 'New password (optional)'}</label>
                      <input type="password" value={accountNewPassword} onChange={e => setAccountNewPassword(e.target.value)}
                        placeholder={language === 'zh' ? '新密码' : 'New password'}
                        className={`w-full border rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400 ${accountNewPassword && accountConfirmPassword && accountNewPassword !== accountConfirmPassword ? 'border-red-300' : 'border-gray-200'}`} />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{language === 'zh' ? '确认新密码' : 'Confirm new password'}</label>
                      <input type="password" value={accountConfirmPassword} onChange={e => setAccountConfirmPassword(e.target.value)}
                        placeholder={language === 'zh' ? '再次输入新密码' : 'Repeat new password'}
                        className={`w-full border rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400 ${accountNewPassword && accountConfirmPassword && accountNewPassword !== accountConfirmPassword ? 'border-red-300' : 'border-gray-200'}`} />
                    </div>
                  </div>
                  {accountNewPassword && accountConfirmPassword && accountNewPassword !== accountConfirmPassword && (
                    <p className="text-xs text-red-500">{language === 'zh' ? '两次密码不一致' : 'Passwords do not match'}</p>
                  )}
                  <button
                    disabled={!accountCurrentPassword.trim() || (!accountNewUsername.trim() && !accountNewPassword.trim()) || (!!accountNewPassword && accountNewPassword !== accountConfirmPassword)}
                    onClick={async () => {
                      if (!user) return;
                      setAccountMessage('');
                      const msgs: string[] = [];
                      try {
                        if (accountNewUsername.trim()) {
                          await changeUsername(accountNewUsername.trim(), accountCurrentPassword);
                          msgs.push(language === 'zh' ? `登录名已改为 "${accountNewUsername.trim()}"` : `Username changed to "${accountNewUsername.trim()}"`);
                        }
                        if (accountNewPassword.trim()) {
                          await changePassword(accountCurrentPassword, accountNewPassword.trim());
                          msgs.push(language === 'zh' ? '密码已更新' : 'Password updated');
                        }
                        setAccountMessage('✓ ' + msgs.join('，'));
                        setAccountCurrentPassword(''); setAccountNewUsername(''); setAccountNewPassword(''); setAccountConfirmPassword('');
                        if (accountNewUsername.trim()) {
                          // 用户名变了，需要重新登录
                          setTimeout(() => { logout(); }, 1500);
                        }
                      } catch (e: any) {
                        setAccountMessage('✗ ' + (e.response?.data?.detail || e.message));
                      }
                    }}
                    className="px-5 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {language === 'zh' ? '保存修改' : 'Save Changes'}
                  </button>
                  {accountMessage && (
                    <p className={`text-sm ${accountMessage.startsWith('✓') ? 'text-green-600' : 'text-red-600'}`}>{accountMessage}</p>
                  )}
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-4">{language === 'zh' ? '创建用户' : 'Create User'}</h3>
                <div className="space-y-3">
                  <input type="text" value={newUsername} onChange={e => setNewUsername(e.target.value)}
                    placeholder={language === 'zh' ? '用户名' : 'Username'}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400" />
                  <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                    placeholder={language === 'zh' ? '密码' : 'Password'}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400" />
                  <select value={newRole} onChange={e => setNewRole(e.target.value as 'user' | 'admin')}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-gray-400">
                    <option value="user">{language === 'zh' ? '普通用户' : 'User'}</option>
                    <option value="admin">{language === 'zh' ? '管理员' : 'Admin'}</option>
                  </select>
                  <button
                    onClick={async () => {
                      if (!newUsername.trim() || !newPassword.trim()) return;
                      try {
                        await createUser(newUsername.trim(), newPassword, newRole);
                        setUsersMessage(language === 'zh' ? '用户创建成功' : 'User created');
                        setNewUsername(''); setNewPassword(''); setNewRole('user');
                        loadUsers();
                      } catch (e: any) { setUsersMessage(e.response?.data?.detail || e.message); }
                    }}
                    disabled={!newUsername.trim() || !newPassword.trim()}
                    className="px-5 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40"
                  >
                    {language === 'zh' ? '创建' : 'Create'}
                  </button>
                  {usersMessage && <p className="text-sm text-gray-600">{usersMessage}</p>}
                </div>
              </div>
              <div className="bg-white rounded-2xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-4">{language === 'zh' ? '用户列表' : 'User List'}</h3>
                <div className="space-y-2">
                  {usersList.map((u: any) => (
                    <div key={u.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <span className="text-sm font-medium text-gray-800">{u.username}</span>
                        <span className="ml-2 text-xs text-gray-400">{u.role}</span>
                      </div>
                      <button
                        onClick={() => showConfirm(
                          language === 'zh' ? '删除用户' : 'Delete User',
                          language === 'zh' ? `确认删除用户 "${u.username}"？` : `Delete user "${u.username}"?`,
                          async () => {
                            setConfirm(p => ({ ...p, visible: false }));
                            try { await deleteUser(u.id); loadUsers(); } catch (e: any) { setUsersMessage(e.response?.data?.detail || e.message); }
                          }
                        )}
                        className="text-xs text-red-500 border border-red-200 px-2 py-1 rounded hover:bg-red-50"
                      >
                        {language === 'zh' ? '删除' : 'Delete'}
                      </button>
                    </div>
                  ))}
                  {usersList.length === 0 && <p className="text-sm text-gray-400">{language === 'zh' ? '暂无用户' : 'No users'}</p>}
                </div>
              </div>
            </div>
          )}

          {/* Memory Mode */}
          {mode === 'memory' && (
            <div className="w-full max-w-4xl space-y-6">

              {/* 普通用户：本地文档上传 */}
              {!isAdmin && (
              <>
              <div className="bg-white rounded-2xl p-6 shadow-md">
                <h3 className="text-lg font-bold text-gray-900 mb-1">
                  {language === 'zh' ? '上传本地文档' : 'Upload Local Document'}
                </h3>
                <p className="text-xs text-gray-400 mb-4">
                  {language === 'zh'
                    ? '文档只存储在你的浏览器中，不会上传到服务器。对话时自动检索这些文档。支持 .txt、.md、.pdf、.docx。'
                    : 'Documents are stored only in your browser, never sent to the server. Auto-searched during chat. Supports .txt, .md, .pdf, .docx.'}
                </p>
                <label className={`flex items-center justify-center gap-2 px-6 py-3 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:border-gray-400 hover:bg-gray-50 transition-colors ${localUploading ? 'opacity-50 pointer-events-none' : ''}`}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                  <span className="text-sm text-gray-600">
                    {localUploading
                      ? (language === 'zh' ? '处理中...' : 'Processing...')
                      : (language === 'zh' ? '点击选择文件' : 'Click to select file')}
                  </span>
                  <input
                    type="file"
                    accept=".txt,.md,.pdf,.docx,.doc"
                    className="hidden"
                    disabled={localUploading}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleLocalFileUpload(file);
                      e.target.value = '';
                    }}
                  />
                </label>
                {localMessage && (
                  <div className={`mt-3 text-sm px-4 py-2 rounded-lg ${localMessage.includes('✓') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                    {localMessage}
                  </div>
                )}
              </div>

              <div className="bg-white rounded-2xl shadow-md overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h3 className="text-lg font-bold text-gray-900">
                    {language === 'zh' ? `我的文档（${localDocs.length}）` : `My Documents (${localDocs.length})`}
                  </h3>
                  <button onClick={loadLocalDocs} className="text-xs text-gray-400 hover:text-gray-600">
                    {language === 'zh' ? '刷新' : 'Refresh'}
                  </button>
                </div>
                {localDocs.length === 0 ? (
                  <div className="text-center text-gray-400 py-12 text-sm">
                    {language === 'zh' ? '暂无本地文档' : 'No local documents yet'}
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
                    {localDocs.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between px-6 py-4 hover:bg-gray-50">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <span className={`text-xs font-bold px-1.5 py-0.5 rounded shrink-0 ${
                            doc.fileType === 'md' ? 'bg-blue-100 text-blue-700' :
                            doc.fileType === 'pdf' ? 'bg-red-100 text-red-700' :
                            doc.fileType === 'docx' || doc.fileType === 'doc' ? 'bg-indigo-100 text-indigo-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {doc.fileType.toUpperCase()}
                          </span>
                          <div className="min-w-0">
                            <p className="text-gray-800 text-sm truncate" title={doc.title}>{doc.title}</p>
                            <p className="text-xs text-gray-400">
                              {doc.chunkCount} {language === 'zh' ? '个文本块' : 'chunks'} · {new Date(doc.createdAt).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteLocalDoc(doc.id, doc.title)}
                          className="ml-4 px-3 py-1.5 text-xs text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors shrink-0"
                        >
                          {language === 'zh' ? '删除' : 'Delete'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              </>
              )}

              {/* 文本输入区域 */}
              {isAdmin && (
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
              )}

              {isAdmin && (
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
              )}

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

              {isAdmin && documents.length > 0 && (
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
            <form onSubmit={getSubmitHandler()} data-chat-form>
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
                          <input type="checkbox" checked={useCodeAnalysis} onChange={(e) => setUseCodeAnalysis(e.target.checked)} className="w-4 h-4 rounded border-gray-300" />
                          {language === 'zh' ? '源码分析' : 'Code Analysis'}
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                          <input type="checkbox" checked={useWebSearch} onChange={(e) => setUseWebSearch(e.target.checked)} className="w-4 h-4 rounded border-gray-300" />
                          {t.optionWebSearch}
                        </label>
                        <label className="flex items-center gap-1.5 text-sm text-gray-600 select-none">
                          {language === 'zh' ? '历史' : 'History'}
                          <select value={historyTurns} onChange={(e) => setHistoryTurns(Number(e.target.value))}
                            className="text-xs border border-gray-200 rounded px-1 py-0.5 bg-white outline-none">
                            <option value={0}>{language === 'zh' ? '不携带' : 'Off'}</option>
                            <option value={1}>{language === 'zh' ? '1轮' : '1 turn'}</option>
                            <option value={2}>{language === 'zh' ? '2轮' : '2 turns'}</option>
                            <option value={3}>{language === 'zh' ? '3轮' : '3 turns'}</option>
                          </select>
                        </label>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {mode === 'chat' && chatting && (
                      <button type="button" onClick={handleStopChat}
                        className="px-5 py-2 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 transition-colors">
                        {language === 'zh' ? '停止' : 'Stop'}
                      </button>
                    )}
                    <button type="submit"
                      disabled={(mode === 'chat' ? chatting : uploading) || !query.trim()}
                      className="px-5 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                      {mode === 'chat' ? (chatting ? t.chatThinking : t.chatSend) : (uploading ? t.actionSaving : t.actionSave)}
                    </button>
                  </div>
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
