export type Language = 'zh' | 'en';

export interface Translations {
  // Header
  appName: string;

  // Modes
  modeChat: string;
  modeMemory: string;
  modeConfig: string;

  // Language
  languageSwitch: string;
  languageChinese: string;
  languageEnglish: string;

  // Chat
  chatPlaceholder: string;
  chatPlaceholderNoRag: string;
  chatSend: string;
  chatThinking: string;
  chatEmpty: string;
  chatEmptyRag: string;
  chatEmptyNoRag: string;

  // Options
  optionKnowledgeBase: string;
  optionOriginalDoc: string;
  optionWebSearch: string;

  // Actions
  actionCopy: string;
  actionCopied: string;
  actionResend: string;
  actionSave: string;
  actionSaving: string;
  actionDelete: string;
  actionCancel: string;
  actionConfirm: string;
  actionAdd: string;
  actionRefresh: string;
  actionExport: string;
  actionImport: string;
  actionReset: string;
  actionSearch: string;
  actionClear: string;

  // Memory
  memoryTextInput: string;
  memoryTextInputDesc: string;
  memoryTitlePlaceholder: string;
  memoryContentPlaceholder: string;
  memorySaveToKb: string;
  memoryUploadTitle: string;
  memoryUploadDesc: string;
  memoryUploadSingle: string;
  memoryUploadBatch: string;
  memoryUploadBatchDesc: string;
  memoryForceUpload: string;
  memoryForceUploadDesc: string;
  memoryOverwriteUpload: string;
  memoryOverwriteUploadDesc: string;
  memoryUploadProgress: string;
  memoryUploadResult: string;
  memoryDocumentList: string;

  // Config
  configStats: string;
  configDocCount: string;
  configChunkCount: string;
  configDbSize: string;
  configLlm: string;
  configLlmBaseUrl: string;
  configLlmApiKey: string;
  configLlmModel: string;
  configEmbedding: string;
  configEmbeddingProvider: string;
  configEmbeddingModel: string;
  configEmbeddingCurrent: string;
  configEmbeddingWarning: string;
  configOriginalDocPath: string;
  configOriginalDocPathDesc: string;
  configOriginalDocPathPlaceholder: string;
  configOriginalDocPathEmpty: string;
  configDocTypes: string;
  configDocSearch: string;
  configDocSearchPlaceholder: string;

  // Messages
  msgSuccess: string;
  msgError: string;
  msgSaveSuccess: string;
  msgUploadSuccess: string;
  msgDeleteSuccess: string;
  msgResetSuccess: string;
  msgExportSuccess: string;
  msgImportSuccess: string;
  msgConfigSuccess: string;
  msgPathAdded: string;
  msgPathRemoved: string;

  // Dialogs
  dialogDeleteTitle: string;
  dialogDeleteMessage: string;
  dialogResetTitle: string;
  dialogResetMessage: string;
  dialogExportTitle: string;
  dialogExportMessage: string;
  dialogImportTitle: string;
  dialogImportMessage: string;

  // Sources
  sourceKnowledgeBase: string;
  sourceWebSearch: string;
  sourceOriginalDoc: string;
  sourceOriginalDocStatus: string;
  sourceOriginalDocFound: string;
  sourceOriginalDocNotFound: string;
  sourceOriginalDocPages: string;

  // Thinking
  thinkingProcess: string;

  // Footer
  footerText: string;

  // File types
  fileTypeMarkdown: string;
  fileTypePdf: string;
  fileTypeWord: string;
  fileTypeText: string;
  fileTypeAudio: string;
  fileTypeImage: string;
  fileTypeVideo: string;

  // Embedding providers
  embeddingLocal: string;
  embeddingDoubao: string;
  embeddingOpenAI: string;

  // Export/Import
  exportingTitle: string;
  exportingMessage: string;
  exportingWait: string;

  // Stats
  statsLoading: string;
  statsNoData: string;
}

export const translations: Record<Language, Translations> = {
  zh: {
    appName: 'Codex',

    modeChat: '💬 对话',
    modeMemory: '💾 记忆',
    modeConfig: '⚙️ 配置',

    languageSwitch: '语言',
    languageChinese: '中文',
    languageEnglish: 'English',

    chatPlaceholder: '向你的知识库提问...',
    chatPlaceholderNoRag: '和大模型聊天...',
    chatSend: '发送',
    chatThinking: '思考中...',
    chatEmpty: '开始和大模型对话吧',
    chatEmptyRag: '（知识库模式）',
    chatEmptyNoRag: '（直接对话）',

    optionKnowledgeBase: '知识库',
    optionOriginalDoc: '原始文档',
    optionWebSearch: '联网搜索',

    actionCopy: '复制',
    actionCopied: '已复制',
    actionResend: '重发',
    actionSave: '保存',
    actionSaving: '保存中...',
    actionDelete: '删除',
    actionCancel: '取消',
    actionConfirm: '确认',
    actionAdd: '添加',
    actionRefresh: '🔄 刷新统计',
    actionExport: '📥 导出备份',
    actionImport: '📤 导入备份',
    actionReset: '🗑 重置知识库',
    actionSearch: '搜索',
    actionClear: '清除',

    memoryTextInput: '直接输入文本',
    memoryTextInputDesc: '直接输入或粘贴文本内容，保存到知识库',
    memoryTitlePlaceholder: '输入标题（可选）',
    memoryContentPlaceholder: '在此输入或粘贴要保存的文本内容...',
    memorySaveToKb: '保存到知识库',
    memoryUploadTitle: '上传文档到知识库',
    memoryUploadDesc: '支持 Markdown（感知分块）和 PDF（按页分块），上传后自动向量化',
    memoryUploadSingle: '单个文件',
    memoryUploadBatch: '批量上传目录',
    memoryUploadBatchDesc: '自动扫描目录下所有 .md 和 .pdf 文件',
    memoryForceUpload: '强制上传（跳过相似文档检测）',
    memoryForceUploadDesc: '',
    memoryOverwriteUpload: '覆盖上传（覆盖同名文档）',
    memoryOverwriteUploadDesc: '',
    memoryUploadProgress: '上传进度',
    memoryUploadResult: '上传结果',
    memoryDocumentList: '已上传文档',

    configStats: '统计信息',
    configDocCount: '文档总数',
    configChunkCount: '向量块总数',
    configDbSize: '数据库大小',
    configLlm: '大模型配置',
    configLlmBaseUrl: 'API Base URL',
    configLlmApiKey: 'API Key',
    configLlmModel: '模型名称',
    configEmbedding: '嵌入模型配置',
    configEmbeddingProvider: '模型提供商',
    configEmbeddingModel: '模型名称',
    configEmbeddingCurrent: '当前使用：',
    configEmbeddingWarning: '⚠️ 更换嵌入模型后，需要重置知识库并重新上传文档，否则新旧向量不兼容',
    configOriginalDocPath: '原始文档搜索路径',
    configOriginalDocPathDesc: '配置本地路径，匹配知识库后会优先查找原始文档内容',
    configOriginalDocPathPlaceholder: '输入本地路径，如 /Users/yzc/docs',
    configOriginalDocPathEmpty: '尚未配置搜索路径',
    configDocTypes: '文档类型分布',
    configDocSearch: '文档列表',
    configDocSearchPlaceholder: '搜索文档名...',

    msgSuccess: '✓',
    msgError: '✗',
    msgSaveSuccess: '保存成功',
    msgUploadSuccess: '上传成功',
    msgDeleteSuccess: '已删除文档',
    msgResetSuccess: '知识库已重置，所有数据已清空',
    msgExportSuccess: '数据库导出成功',
    msgImportSuccess: '导入成功',
    msgConfigSuccess: 'LLM 配置保存成功',
    msgPathAdded: '路径添加成功',
    msgPathRemoved: '路径已移除',

    dialogDeleteTitle: '删除文档',
    dialogDeleteMessage: '确定要删除「{title}」吗？此操作不可撤销，相关的向量数据也将一并删除。',
    dialogResetTitle: '重置知识库',
    dialogResetMessage: '确定要清空所有数据吗？包括全部文档和向量索引，此操作不可撤销！',
    dialogExportTitle: '导出数据库',
    dialogExportMessage: '即将导出 {docCount} 个文档和 {chunkCount} 个向量块。\n\n预估文件大小：约 {sizeMB} MB\n预估耗时：约 {minutes} 分钟\n\n导出过程中请勿关闭页面。',
    dialogImportTitle: '导入数据库',
    dialogImportMessage: '导入会添加备份文件中的所有文档到当前数据库。如果需要完全恢复备份，请先重置知识库。确定要继续吗？',

    sourceKnowledgeBase: '知识库来源：',
    sourceWebSearch: '网络来源：',
    sourceOriginalDoc: '原始文档：',
    sourceOriginalDocStatus: '原始文档查找情况',
    sourceOriginalDocFound: '✓ 已找到原始文档：',
    sourceOriginalDocNotFound: '✗ 未找到原始文档：',
    sourceOriginalDocPages: '（参考页码：{pages}）',

    thinkingProcess: '思考过程',

    footerText: 'Codex v0.4.2 · 基于本地 AI 的智能笔记系统 · by Zhichao',

    fileTypeMarkdown: '📝 Markdown',
    fileTypePdf: '📄 PDF',
    fileTypeWord: '📃 Word',
    fileTypeText: '📋 文本',
    fileTypeAudio: '🎵 音频',
    fileTypeImage: '🖼 图片',
    fileTypeVideo: '🎬 视频',

    embeddingLocal: '本地模型 (sentence-transformers)',
    embeddingDoubao: '豆包 Embedding',
    embeddingOpenAI: '云端 API (OpenAI 兼容)',

    exportingTitle: '正在导出数据库',
    exportingMessage: '正在生成备份文件，请稍候...',
    exportingWait: '请勿关闭页面',

    statsLoading: '...',
    statsNoData: '-',
  },

  en: {
    appName: 'Codex',

    modeChat: '💬 Chat',
    modeMemory: '💾 Memory',
    modeConfig: '⚙️ Config',

    languageSwitch: 'Language',
    languageChinese: '中文',
    languageEnglish: 'English',

    chatPlaceholder: 'Ask your knowledge base...',
    chatPlaceholderNoRag: 'Chat with AI...',
    chatSend: 'Send',
    chatThinking: 'Thinking...',
    chatEmpty: 'Start chatting with AI',
    chatEmptyRag: '(Knowledge Base Mode)',
    chatEmptyNoRag: '(Direct Chat)',

    optionKnowledgeBase: 'Knowledge Base',
    optionOriginalDoc: 'Original Doc',
    optionWebSearch: 'Web Search',

    actionCopy: 'Copy',
    actionCopied: 'Copied',
    actionResend: 'Resend',
    actionSave: 'Save',
    actionSaving: 'Saving...',
    actionDelete: 'Delete',
    actionCancel: 'Cancel',
    actionConfirm: 'Confirm',
    actionAdd: 'Add',
    actionRefresh: '🔄 Refresh Stats',
    actionExport: '📥 Export Backup',
    actionImport: '📤 Import Backup',
    actionReset: '🗑 Reset Database',
    actionSearch: 'Search',
    actionClear: 'Clear',

    memoryTextInput: 'Direct Text Input',
    memoryTextInputDesc: 'Enter or paste text content to save to knowledge base',
    memoryTitlePlaceholder: 'Enter title (optional)',
    memoryContentPlaceholder: 'Enter or paste text content here...',
    memorySaveToKb: 'Save to Knowledge Base',
    memoryUploadTitle: 'Upload Documents',
    memoryUploadDesc: 'Supports Markdown (semantic chunking) and PDF (page-based chunking), auto-vectorized after upload',
    memoryUploadSingle: 'Single File',
    memoryUploadBatch: 'Batch Upload Directory',
    memoryUploadBatchDesc: 'Auto-scan all .md and .pdf files in directory',
    memoryForceUpload: 'Force Upload (skip similarity check)',
    memoryForceUploadDesc: '',
    memoryOverwriteUpload: 'Overwrite Upload (replace existing)',
    memoryOverwriteUploadDesc: '',
    memoryUploadProgress: 'Upload Progress',
    memoryUploadResult: 'Upload Result',
    memoryDocumentList: 'Uploaded Documents',

    configStats: 'Statistics',
    configDocCount: 'Documents',
    configChunkCount: 'Chunks',
    configDbSize: 'Database Size',
    configLlm: 'LLM Configuration',
    configLlmBaseUrl: 'API Base URL',
    configLlmApiKey: 'API Key',
    configLlmModel: 'Model Name',
    configEmbedding: 'Embedding Configuration',
    configEmbeddingProvider: 'Provider',
    configEmbeddingModel: 'Model Name',
    configEmbeddingCurrent: 'Current:',
    configEmbeddingWarning: '⚠️ After changing embedding model, you need to reset the database and re-upload documents, as vectors are incompatible',
    configOriginalDocPath: 'Original Document Search Paths',
    configOriginalDocPathDesc: 'Configure local paths to search for original documents',
    configOriginalDocPathPlaceholder: 'Enter local path, e.g. /Users/yzc/docs',
    configOriginalDocPathEmpty: 'No search paths configured',
    configDocTypes: 'Document Types',
    configDocSearch: 'Document List',
    configDocSearchPlaceholder: 'Search documents...',

    msgSuccess: '✓',
    msgError: '✗',
    msgSaveSuccess: 'Saved successfully',
    msgUploadSuccess: 'Uploaded successfully',
    msgDeleteSuccess: 'Document deleted',
    msgResetSuccess: 'Database reset, all data cleared',
    msgExportSuccess: 'Database exported successfully',
    msgImportSuccess: 'Imported successfully',
    msgConfigSuccess: 'LLM configuration saved',
    msgPathAdded: 'Path added successfully',
    msgPathRemoved: 'Path removed',

    dialogDeleteTitle: 'Delete Document',
    dialogDeleteMessage: 'Are you sure to delete "{title}"? This action cannot be undone, and related vector data will also be deleted.',
    dialogResetTitle: 'Reset Database',
    dialogResetMessage: 'Are you sure to clear all data? Including all documents and vector indexes. This action cannot be undone!',
    dialogExportTitle: 'Export Database',
    dialogExportMessage: 'About to export {docCount} documents and {chunkCount} chunks.\n\nEstimated size: ~{sizeMB} MB\nEstimated time: ~{minutes} minutes\n\nDo not close the page during export.',
    dialogImportTitle: 'Import Database',
    dialogImportMessage: 'Import will add all documents from the backup file to the current database. If you need to fully restore the backup, please reset the database first. Continue?',

    sourceKnowledgeBase: 'Knowledge Base Sources:',
    sourceWebSearch: 'Web Sources:',
    sourceOriginalDoc: 'Original Document:',
    sourceOriginalDocStatus: 'Original Document Search Status',
    sourceOriginalDocFound: '✓ Found original document:',
    sourceOriginalDocNotFound: '✗ Original document not found:',
    sourceOriginalDocPages: '(Reference pages: {pages})',

    thinkingProcess: 'Thinking Process',

    footerText: 'Codex v0.4.2 · Local AI-powered Knowledge Base · by Zhichao',

    fileTypeMarkdown: '📝 Markdown',
    fileTypePdf: '📄 PDF',
    fileTypeWord: '📃 Word',
    fileTypeText: '📋 Text',
    fileTypeAudio: '🎵 Audio',
    fileTypeImage: '🖼 Image',
    fileTypeVideo: '🎬 Video',

    embeddingLocal: 'Local Model (sentence-transformers)',
    embeddingDoubao: 'Doubao Embedding',
    embeddingOpenAI: 'Cloud API (OpenAI Compatible)',

    exportingTitle: 'Exporting Database',
    exportingMessage: 'Generating backup file, please wait...',
    exportingWait: 'Do not close the page',

    statsLoading: '...',
    statsNoData: '-',
  },
};
