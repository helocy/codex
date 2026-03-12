import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';

interface Props {
  content: string;
  /** 深色背景（用户气泡）时传 true，代码块配色反转 */
  dark?: boolean;
}

const CheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
    <polyline points="20 6 9 17 4 12" />
  </svg>
);
const CopyIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

/** 代码块：带语言标签 + 一键复制 */
const CodeBlock = ({ language, code }: { language: string; code: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-gray-200 bg-[#f6f8fa]">
      {/* 顶栏 */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-100 border-b border-gray-200">
        <span className="text-xs text-gray-500 font-mono">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-800 transition-colors"
        >
          {copied ? <CheckIcon /> : <CopyIcon />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
      {/* 代码区：交给 rehype-highlight 渲染，注入 github 主题样式 */}
      <pre className="overflow-x-auto text-sm leading-relaxed p-4 m-0 bg-[#f6f8fa]">
        <code className={language ? `language-${language}` : ''}>{code}</code>
      </pre>
    </div>
  );
};

export default function MarkdownRenderer({ content, dark = false }: Props) {
  const prose = dark
    ? 'prose-invert prose-p:text-gray-100 prose-headings:text-white prose-strong:text-white prose-code:text-pink-300 prose-a:text-blue-300'
    : 'prose-gray';

  return (
    <div
      className={[
        'prose prose-sm max-w-none',
        prose,
        // 段落、标题间距
        'prose-p:my-1.5 prose-p:leading-relaxed',
        'prose-headings:mt-4 prose-headings:mb-2 prose-headings:font-semibold',
        'prose-h1:text-xl prose-h2:text-lg prose-h3:text-base',
        // 列表
        'prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5',
        // 行内代码
        dark
          ? 'prose-code:bg-white/20 prose-code:text-pink-200'
          : 'prose-code:bg-gray-100 prose-code:text-pink-600',
        'prose-code:rounded prose-code:px-1 prose-code:py-0.5 prose-code:text-[0.8em] prose-code:font-mono',
        'prose-code:before:content-none prose-code:after:content-none',
        // 引用块
        dark
          ? 'prose-blockquote:border-gray-400 prose-blockquote:text-gray-300'
          : 'prose-blockquote:border-gray-300 prose-blockquote:text-gray-600',
        'prose-blockquote:my-2 prose-blockquote:pl-3',
        // 表格
        'prose-table:text-sm prose-th:bg-gray-50 prose-th:font-semibold',
        // 水平线
        'prose-hr:border-gray-200 prose-hr:my-4',
      ].join(' ')}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // 代码块：pre > code → 替换为自定义 CodeBlock
          code({ className, children, ...props }) {
            const isBlock = !!(props as any).node?.properties?.className ||
              String(children).includes('\n') ||
              className?.startsWith('language-');

            const language = (className || '').replace('language-', '');
            const code = String(children).replace(/\n$/, '');

            if (isBlock) {
              return <CodeBlock language={language} code={code} />;
            }
            // 行内代码
            return <code className={className} {...props}>{children}</code>;
          },
          // pre 包裹：交给 code 自行渲染，pre 不输出额外容器
          pre({ children }) {
            return <>{children}</>;
          },
          // 链接在新标签打开
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer"
                className={dark ? 'text-blue-300 hover:underline' : 'text-blue-600 hover:underline'}>
                {children}
              </a>
            );
          },
          // 表格加横向滚动
          table({ children }) {
            return (
              <div className="overflow-x-auto my-3">
                <table className="min-w-full border-collapse border border-gray-200 text-sm">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }) {
            return <th className="border border-gray-200 px-3 py-2 text-left bg-gray-50">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-gray-200 px-3 py-2">{children}</td>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
