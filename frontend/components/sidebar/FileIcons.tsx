import React from "react";

export function renderFileSvgIcon(
  ext: string,
  isPdf?: boolean,
  isImg?: boolean,
  isCode?: boolean,
  fileName?: string
) {
  const e = (ext || "").toLowerCase().replace(/^\./, "");
  const name = (fileName || "").toLowerCase();

  // Images
  if (isImg || ["png", "jpg", "jpeg", "gif", "webp", "svg", "ico"].includes(e)) {
    return (
      <svg className="w-3.5 h-3.5 text-purple-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    );
  }

  // PDF
  if (isPdf || e === "pdf") {
    return (
      <svg className="w-3.5 h-3.5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    );
  }

  // Archives
  if (["zip", "tar", "gz", "rar", "7z"].includes(e)) {
    return (
      <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
      </svg>
    );
  }

  // Git files
  if (name.includes(".git") || e === "gitignore" || e === "gitmodules") {
    return (
      <svg className="w-3.5 h-3.5 text-orange-500 shrink-0" fill="currentColor" viewBox="0 0 24 24">
        <path d="M2.6 10.59L8.38 4.8a1.5 1.5 0 012.12 0l1.41 1.41-2.42 2.42a2 2 0 00-1.42 1.42L6.1 8.08a.5.5 0 00-.7.7l1.97 1.97a2 2 0 102.83 2.83l2.83-2.83a2 2 0 10-1.42-1.42l-2.42 2.42-1.41-1.41 5.78-5.78a1.5 1.5 0 012.12 0l5.78 5.78a1.5 1.5 0 010 2.12l-5.78 5.78a1.5 1.5 0 01-2.12 0L2.6 12.71a1.5 1.5 0 010-2.12z"/>
      </svg>
    );
  }

  // PHP
  if (e === "php") {
    return (
      <span className="w-3.5 h-3.5 rounded-[3px] bg-indigo-500/20 text-indigo-300 font-mono text-[8px] font-bold flex items-center justify-center shrink-0 border border-indigo-500/35 leading-none">
        PHP
      </span>
    );
  }

  // TypeScript
  if (e === "ts" || e === "tsx") {
    return (
      <span className="w-3.5 h-3.5 rounded-[3px] bg-blue-500/20 text-blue-400 font-mono text-[8px] font-bold flex items-center justify-center shrink-0 border border-blue-500/35 leading-none">
        TS
      </span>
    );
  }

  // JavaScript
  if (["js", "jsx", "mjs", "cjs"].includes(e)) {
    return (
      <span className="w-3.5 h-3.5 rounded-[3px] bg-amber-400/20 text-amber-300 font-mono text-[8px] font-bold flex items-center justify-center shrink-0 border border-amber-400/35 leading-none">
        JS
      </span>
    );
  }

  // JSON
  if (e === "json") {
    return (
      <span className="w-3.5 h-3.5 rounded-[3px] bg-yellow-500/20 text-yellow-300 font-mono text-[8px] font-bold flex items-center justify-center shrink-0 border border-yellow-500/35 leading-none">
        &#123;&#125;
      </span>
    );
  }

  // Python
  if (e === "py") {
    return (
      <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
        <path d="M11.927 0c-3.414 0-5.467.568-5.467 2.457v2.107h5.467v.702h-7.66C1.94 5.266 0 7.37 0 9.873c0 2.502 1.637 4.545 4.267 4.545h1.2v-2.107c0-2.046 1.76-3.864 3.867-3.864h5.467V6.32c0-1.89-2.053-2.457-5.467-2.457h2.592V0h-2.592zm-2.07 1.405a.703.703 0 110 1.406.703.703 0 010-1.406zm2.143 14.05v2.107c0 2.046-1.76 3.864-3.867 3.864H2.666v2.126c0 1.889 2.053 2.457 5.467 2.457h2.592v3.864h-2.592c3.414 0 5.467-.568 5.467-2.457v-2.107H8.133v-.702h7.66c2.327 0 4.267-2.104 4.267-4.607 0-2.502-1.637-4.545-4.267-4.545h-1.2v2.107zm2.07 7.135a.703.703 0 110-1.406.703.703 0 010 1.406z" />
      </svg>
    );
  }

  // Database / SQL
  if (["sql", "sqlite", "sqlite3", "db"].includes(e)) {
    return (
      <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <ellipse cx="12" cy="5" rx="9" ry="3" strokeWidth={1.8}/>
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" strokeWidth={1.8}/>
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" strokeWidth={1.8}/>
      </svg>
    );
  }

  // HTML
  if (e === "html" || e === "htm") {
    return (
      <span className="w-3.5 h-3.5 rounded-[3px] bg-orange-500/20 text-orange-400 font-mono text-[8px] font-bold flex items-center justify-center shrink-0 border border-orange-500/35 leading-none">
        &lt;&gt;
      </span>
    );
  }

  // CSS / SCSS
  if (["css", "scss", "sass", "less"].includes(e)) {
    return (
      <span className="w-3.5 h-3.5 rounded-[3px] bg-sky-500/20 text-sky-400 font-mono text-[8px] font-bold flex items-center justify-center shrink-0 border border-sky-500/35 leading-none">
        #
      </span>
    );
  }

  // Markdown
  if (["md", "mdx", "markdown"].includes(e)) {
    return (
      <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 13h6M9 17h4" />
      </svg>
    );
  }

  // Config / Env / YAML
  if (name.startsWith(".env") || ["yml", "yaml", "toml", "ini", "conf", "config"].includes(e)) {
    return (
      <svg className="w-3.5 h-3.5 text-amber-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    );
  }

  // Generic code files
  if (isCode || ["sh", "bash", "zsh", "c", "cpp", "rs", "go", "java"].includes(e)) {
    return (
      <svg className="w-3.5 h-3.5 text-slate-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    );
  }

  // Default document file
  return (
    <svg className="w-3.5 h-3.5 text-slate-400/80 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}
