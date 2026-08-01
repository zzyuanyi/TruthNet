'use client';

import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Check, Copy } from 'lucide-react';
import { useState, useCallback } from 'react';

/** Copy button for code blocks */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1 rounded-md bg-white/10 hover:bg-white/20 transition-colors"
      title="复制代码"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5 text-gray-400" />}
    </button>
  );
}

/** Language display label */
const LANG_LABELS: Record<string, string> = {
  python: 'Python',
  py: 'Python',
  sql: 'SQL',
  javascript: 'JavaScript',
  js: 'JavaScript',
  typescript: 'TypeScript',
  ts: 'TypeScript',
  bash: 'Bash',
  sh: 'Shell',
  shell: 'Shell',
  json: 'JSON',
  yaml: 'YAML',
  yml: 'YAML',
  css: 'CSS',
  html: 'HTML',
  java: 'Java',
  go: 'Go',
  rust: 'Rust',
  r: 'R',
};

/** Code block component with syntax highlighting + copy button */
function CodeBlock({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }) {
  const match = /language-(\w+)/.exec(className || '');
  const language = match?.[1] ?? '';
  const codeText = String(children).replace(/\n$/, '');

  // Inline code (no language specified and single line)
  if (!language && !codeText.includes('\n')) {
    return (
      <code
        className="px-1.5 py-0.5 rounded bg-gray-100 text-blue-700 text-[13px] font-mono"
        {...rest}
      >
        {children}
      </code>
    );
  }

  // Fenced code block with syntax highlighting
  return (
    <div className="relative my-2.5 rounded-lg overflow-hidden border border-gray-700/50">
      {language && (
        <div className="flex items-center justify-between px-4 py-1 bg-[#1e1e2e] border-b border-gray-700/50">
          <span className="text-[11px] text-gray-400 font-mono">
            {LANG_LABELS[language] ?? language.toUpperCase()}
          </span>
        </div>
      )}
      <CopyButton text={codeText} />
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: '13px',
          lineHeight: '1.6',
          padding: '12px 16px',
          background: '#1e1e2e',
        }}
        showLineNumbers={codeText.split('\n').length > 3}
        lineNumberStyle={{ color: '#4a4a6a', fontSize: '11px', minWidth: '2.5em' }}
      >
        {codeText}
      </SyntaxHighlighter>
    </div>
  );
}

/** Markdown renderer props */
interface MarkdownRendererProps {
  content: string;
  className?: string;
  variant?: string;
}

/** Shared component overrides for react-markdown */
const sharedComponents = {
  // Code blocks & inline code
  code: CodeBlock,

  // Headings
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="text-lg font-bold mt-4 mb-2 first:mt-0">{children}</h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="text-base font-bold mt-3 mb-1.5 first:mt-0">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="text-[15px] font-semibold mt-2.5 mb-1 first:mt-0">{children}</h3>
  ),

  // Paragraphs
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="my-1.5 first:my-0 last:my-0">{children}</p>
  ),

  // Lists
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-1.5 ml-4 list-disc space-y-0.5">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-1.5 ml-4 list-decimal space-y-0.5">{children}</ol>
  ),
  li: ({ children, ...rest }: Record<string, unknown>) => (
    <li className="pl-0.5" {...rest}>{children as React.ReactNode}</li>
  ),

  // Blockquotes
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-2 pl-3 border-l-3 border-blue-400 bg-blue-50/50 rounded-r-md py-1.5 pr-2 text-gray-700 italic">
      {children}
    </blockquote>
  ),

  // Tables
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-2 overflow-x-auto rounded-md border border-gray-200">
      <table className="min-w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-gray-50">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-3 py-1.5 text-left font-semibold text-gray-700 border-b border-gray-200 whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-3 py-1.5 text-gray-600 border-b border-gray-100 whitespace-nowrap">
      {children}
    </td>
  ),
  tr: ({ children }: { children?: React.ReactNode }) => (
    <tr className="hover:bg-gray-50/50 transition-colors">{children}</tr>
  ),

  // Horizontal rule
  hr: () => <hr className="my-3 border-gray-200" />,

  // Links
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 hover:text-blue-800 underline underline-offset-2 transition-colors"
    >
      {children}
    </a>
  ),

  // Strong & Emphasis
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-gray-700">{children}</em>
  ),

  // Images (render as link for chat context)
  img: ({ src, alt }: { src?: string; alt?: string }) => (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 hover:text-blue-800 underline underline-offset-2"
    >
      {alt ?? '图片链接'}
    </a>
  ),
};

/** Rich Markdown renderer for AI chat messages */
export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`markdown-body ${className ?? ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={sharedComponents as unknown as Components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/** Compact version for streaming display — same rendering, lighter description */
export function StreamingMarkdown({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`markdown-body ${className ?? ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={sharedComponents as unknown as Components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
