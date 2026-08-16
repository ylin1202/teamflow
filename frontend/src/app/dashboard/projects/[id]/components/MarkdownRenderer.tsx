"use client";

import dynamic from "next/dynamic";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

const markdownComponents = {
  h1: ({ ...props }: any) => (
    <h1 className="text-xl font-bold text-gray-900 border-b border-gray-200 pb-2 mt-5 mb-3 tracking-tight" {...props} />
  ),
  h2: ({ ...props }: any) => (
    <h2 className="text-base font-bold text-gray-800 border-b border-gray-100 pb-1 mt-4 mb-2 tracking-tight" {...props} />
  ),
  h3: ({ ...props }: any) => (
    <h3 className="text-sm font-semibold text-gray-800 mt-3 mb-1.5" {...props} />
  ),
  p: ({ ...props }: any) => (
    <p className="text-gray-700 text-sm leading-relaxed mb-2.5" {...props} />
  ),
  ul: ({ ...props }: any) => (
    <ul className="list-disc list-outside pl-5 space-y-1 mb-3 text-sm text-gray-700" {...props} />
  ),
  ol: ({ ...props }: any) => (
    <ol className="list-decimal list-outside pl-5 space-y-1 mb-3 text-sm text-gray-700" {...props} />
  ),
  li: ({ ...props }: any) => <li className="leading-relaxed text-gray-700" {...props} />,
  pre: ({ ...props }: any) => (
    <pre className="bg-gray-900 text-gray-100 p-4 rounded-xl overflow-x-auto text-xs font-mono my-3 shadow-inner" {...props} />
  ),
  code: ({ className, children, ...props }: any) => {
    const isCodeBlock =
      /language-(\w+)/.test(className || "") ||
      (typeof children === "string" && children.includes("\n"));

    if (isCodeBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="bg-gray-100 text-pink-600 px-1.5 py-0.5 mx-0.5 rounded text-xs font-mono font-medium border border-gray-200/60"
        {...props}
      >
        {children}
      </code>
    );
  },
  blockquote: ({ ...props }: any) => (
    <blockquote className="border-l-4 border-blue-500 pl-3.5 py-1.5 text-gray-600 italic bg-blue-50/50 rounded-r-lg my-3 text-xs leading-relaxed" {...props} />
  ),
  table: ({ ...props }: any) => (
    <div className="overflow-x-auto my-3 border border-gray-200 rounded-lg">
      <table className="w-full text-left text-xs border-collapse divide-y divide-gray-200" {...props} />
    </div>
  ),
  th: ({ ...props }: any) => (
    <th className="bg-gray-50 px-3 py-2 font-semibold text-gray-700 border-b border-gray-200" {...props} />
  ),
  td: ({ ...props }: any) => (
    <td className="px-3 py-2 text-gray-600 border-b border-gray-100" {...props} />
  ),
  hr: () => <hr className="my-4 border-gray-200" />,
};

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>;
}