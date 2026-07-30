declare module 'react-markdown' {
    import React from 'react';
  
    export interface ReactMarkdownProps {
      children?: string | null;
      className?: string;
      components?: Record<string, React.ComponentType<any>>;
      [key: string]: any;
    }
  
    const ReactMarkdown: React.ComponentType<ReactMarkdownProps>;
    export default ReactMarkdown;
  }