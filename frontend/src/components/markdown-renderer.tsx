'use client';

import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql';
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';
import jsx from 'react-syntax-highlighter/dist/esm/languages/prism/jsx';
import tsx from 'react-syntax-highlighter/dist/esm/languages/prism/tsx';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import yaml from 'react-syntax-highlighter/dist/esm/languages/prism/yaml';
import css from 'react-syntax-highlighter/dist/esm/languages/prism/css';
import markup from 'react-syntax-highlighter/dist/esm/languages/prism/markup';
import java from 'react-syntax-highlighter/dist/esm/languages/prism/java';
import go from 'react-syntax-highlighter/dist/esm/languages/prism/go';
import { Check, Copy } from 'lucide-react';
import { useState, useCallback } from 'react';

// 按需注册语言（仅保留业务高频语言，从根上压缩 syntax-highlighter 体积）
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('typescript', typescript);
SyntaxHighlighter.registerLanguage('jsx', jsx);
SyntaxHighlighter.registerLanguage('tsx', tsx);
SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('sql', sql);
SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('html', markup);
SyntaxHighlighter.registerLanguage('markup', markup);
SyntaxHighlighter.registerLanguage('java', java);
SyntaxHighlighter.registerLanguage('go', go);

/** 语言别名 → 已注册主名 */
const LANG_ALIASES: Record<string, string> = {
  py: 'python',
  js: 'javascript',
  ts: 'typescript',
  sh: 'bash',
  shell: 'bash',
  yml: 'yaml',
  html: 'markup',
};

/** 已注册语言集合（用于 fallback 到 text） */
const REGISTERED_LANGS = new Set([
  'javascript',
  'typescript',
  'jsx',
  'tsx',
  'python',
  'sql',
  'bash',
  'json',
  'yaml',
  'css',
  'markup',
  'java',
  'go',
]);

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
  const normalized = LANG_ALIASES[language] ?? language;
  const highlightLang = REGISTERED_LANGS.has(normalized) ? normalized : '';
  const codeText = String(children).replace(/\n$/, '');

  // Inline code (no language specified and single line)
  if (!language && !codeText.includes('\n')) {
    return (
      <code
        className="px-1.5 py-0.5 rounded bg-muted text-primary text-[13px] font-mono"
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
        language={highlightLang || 'text'}
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
    <blockquote className="my-2 pl-3 border-l-4 border-primary/40 bg-muted/40 rounded-r-md py-1.5 pr-2 text-foreground/80 italic">
      {children}
    </blockquote>
  ),

  // Tables
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-2 overflow-x-auto rounded-lg border border-border">
      <table className="min-w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-muted/60">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="px-3 py-1.5 text-left font-semibold text-foreground border-b border-border whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="px-3 py-1.5 text-muted-foreground border-b border-border/60 whitespace-nowrap">
      {children}
    </td>
  ),
  tr: ({ children }: { children?: React.ReactNode }) => (
    <tr className="hover:bg-muted/40 transition-colors">{children}</tr>
  ),

  // Horizontal rule
  hr: () => <hr className="my-3 border-border" />,

  // Links
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:text-primary/80 underline underline-offset-2 transition-colors"
    >
      {children}
    </a>
  ),

  // Strong & Emphasis
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-foreground/80">{children}</em>
  ),

  // Images (render as link for chat context)
  img: ({ src, alt }: { src?: string; alt?: string }) => (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:text-primary/80 underline underline-offset-2"
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
