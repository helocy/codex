import React, { useState } from 'react';
import { searchDocuments } from '../services/api';

interface SearchResult {
  chunk_id: number;
  document_id: number;
  content: string;
  similarity: number;
  chunk_index: number;
}

export const SearchBox: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);
    try {
      const data = await searchDocuments(query);
      setResults(data.results);
    } catch (error) {
      console.error('搜索失败:', error);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="🔍 输入问题或关键词..."
            className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={searching}
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="absolute right-2 top-1/2 transform -translate-y-1/2 px-4 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
          >
            {searching ? '搜索中...' : '搜索'}
          </button>
        </div>
      </form>

      {results.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-700">
            搜索结果 ({results.length})
          </h3>
          {results.map((result) => (
            <div
              key={result.chunk_id}
              className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs text-gray-500">
                  文档 ID: {result.document_id} | 片段 {result.chunk_index + 1}
                </span>
                <span className="text-xs font-semibold text-blue-600">
                  相似度: {(result.similarity * 100).toFixed(1)}%
                </span>
              </div>
              <p className="text-gray-800 whitespace-pre-wrap">{result.content}</p>
            </div>
          ))}
        </div>
      )}

      {results.length === 0 && query && !searching && (
        <div className="text-center text-gray-500 py-8">
          没有找到相关结果
        </div>
      )}
    </div>
  );
};
