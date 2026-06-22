"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
}

/**
 * 基于 react-markdown + remark-gfm 的 Markdown 渲染器
 * 支持 GFM（表格、删除线、任务列表、自动链接）
 */
export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className="text-sm leading-relaxed text-dark-text"
      components={{
        h1: ({ children }) => (
          <h1 className="text-xl font-bold mt-6 mb-3 text-white border-b border-white/[0.06] pb-2">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-lg font-bold mt-5 mb-2 text-dark-text">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-base font-semibold mt-4 mb-2 text-dark-text">
            {children}
          </h3>
        ),
        p: ({ children }) => (
          <p className="text-sm my-2 leading-relaxed text-dark-text">{children}</p>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-white">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-gray-300">{children}</em>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return (
              <code className="text-emerald-400 text-xs font-mono">
                {children}
              </code>
            );
          }
          return (
            <code className="bg-white/5 text-primary-400 px-1 py-0.5 rounded text-xs font-mono">
              {children}
            </code>
          );
        },
        pre: ({ children }) => (
          <pre className="bg-black/30 text-emerald-400 text-xs p-4 rounded-lg overflow-x-auto my-3 font-mono border border-white/[0.06]">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-primary-500/40 pl-4 py-2 my-3 bg-primary-500/5 text-sm text-dark-text rounded-r-lg">
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-white/[0.03]">{children}</thead>
        ),
        th: ({ children }) => (
          <th className="px-3 py-2 text-left font-semibold text-dark-text border-b border-white/[0.06]">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 border-b border-white/[0.03] text-dark-text">
            {children}
          </td>
        ),
        tr: ({ children, ...props }) => {
          // react-markdown doesn't pass index, use CSS nth-child instead
          return <tr className="even:bg-white/[0.02]">{children}</tr>;
        },
        hr: () => <hr className="my-4 border-white/[0.06]" />,
        ol: ({ children }) => (
          <ol className="list-decimal list-inside ml-4 my-2 space-y-1 text-sm text-dark-text">
            {children}
          </ol>
        ),
        ul: ({ children }) => (
          <ul className="list-disc list-inside ml-4 my-2 space-y-1 text-sm text-dark-text">
            {children}
          </ul>
        ),
        li: ({ children }) => <li className="my-0.5">{children}</li>,
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-400 hover:text-primary-300 underline"
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
