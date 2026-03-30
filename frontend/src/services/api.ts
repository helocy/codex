import axios from 'axios';

const API_BASE_URL = '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadFile = async (file: File, skipDuplicate: boolean = false, overwrite: boolean = false) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    params: {
      skip_duplicate: skipDuplicate,
      overwrite: overwrite
    }
  });

  return response.data;
};

export const saveText = async (content: string, title?: string) => {
  const response = await api.post('/documents/text', {
    content,
    title,
  });

  return response.data;
};

export const searchDocuments = async (query: string, topK: number = 5) => {
  const response = await api.post('/search/search', {
    query,
    top_k: topK,
  });

  return response.data;
};

export const getDocuments = async () => {
  const response = await api.get('/documents/documents');
  return response.data;
};

export const getDocument = async (id: number) => {
  const response = await api.get(`/documents/documents/${id}`);
  return response.data;
};

export const chatWithRAG = async (
  query: string,
  topK: number = 10,
  useRag: boolean = true,
  useWebSearch: boolean = false,
  useOriginalDoc: boolean = true,
  history?: Array<{ role: string; content: string }>,
  useTreeIndex: boolean = true,
  signal?: AbortSignal,
  useCodeAnalysis: boolean = false,
) => {
  const response = await api.post('/chat/chat', {
    query,
    top_k: topK,
    use_rag: useRag,
    use_web_search: useWebSearch,
    use_original_doc: useOriginalDoc,
    use_tree_index: useTreeIndex,
    use_code_analysis: useCodeAnalysis,
    history: history || [],
  }, { signal });
  return response.data;
};

export const configureLLM = async (config: {
  provider: string;
  api_key?: string;
  base_url?: string;
  model?: string;
}) => {
  const response = await api.post('/chat/config', config);
  return response.data;
};

export const uploadDirectory = async (directoryPath: string) => {
  const response = await api.post('/documents/upload-directory', null, {
    params: { directory_path: directoryPath }
  });
  return response.data;
};

export const getLLMConfig = async () => {
  const response = await api.get('/chat/config');
  return response.data;
};

export const configureCodeAnalysisLLM = async (config: {
  provider: string;
  api_key?: string;
  base_url?: string;
  model?: string;
}) => {
  const response = await api.post('/chat/code-analysis-config', config);
  return response.data;
};

export const getCodeAnalysisLLMConfig = async () => {
  const response = await api.get('/chat/code-analysis-config');
  return response.data;
};

export const getDbStats = async () => {
  const response = await api.get('/admin/stats');
  return response.data;
};

export const deleteDocument = async (id: number) => {
  const response = await api.delete(`/admin/documents/${id}`);
  return response.data;
};

export const resetDatabase = async () => {
  const response = await api.delete('/admin/reset');
  return response.data;
};

export const exportDatabase = async () => {
  const response = await api.get('/admin/export', {
    responseType: 'blob'
  });
  return response.data;
};

export const importDatabase = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/admin/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getEmbeddingConfig = async () => {
  const response = await api.get('/embedding/config');
  return response.data;
};

export const configureEmbedding = async (config: {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
}) => {
  const response = await api.post('/embedding/config', config);
  return response.data;
};

export const buildDocumentTreeIndex = async (id: number) => {
  const response = await api.post(`/documents/documents/${id}/build-tree-index`);
  return response.data;
};

export const batchBuildTreeIndex = async () => {
  const response = await api.post('/documents/batch-build-tree-index');
  return response.data;
};

export const findDuplicates = async (threshold: number = 0.92) => {
  const response = await api.get('/admin/duplicates', { params: { threshold } });
  return response.data;
};

export const getOriginalDocPaths = async () => {
  const response = await api.get('/admin/original-doc-paths');
  return response.data;
};

export const addOriginalDocPath = async (path: string) => {
  const response = await api.post('/admin/original-doc-paths', null, { params: { path } });
  return response.data;
};

export const removeOriginalDocPath = async (path: string) => {
  const response = await api.delete('/admin/original-doc-paths', { params: { path } });
  return response.data;
};