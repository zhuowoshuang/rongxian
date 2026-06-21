"use client";

interface MarkdownRendererProps {
  content: string;
}

function renderInline(text: string): JSX.Element {
  const parts: (string | JSX.Element)[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    const codeMatch = remaining.match(/`([^`]+)`/);
    let firstMatch: { type: string; index: number; full: string; content: string } | null = null;
    if (boldMatch && boldMatch.index !== undefined) firstMatch = { type: "bold", index: boldMatch.index, full: boldMatch[0], content: boldMatch[1] };
    if (codeMatch && codeMatch.index !== undefined) { if (!firstMatch || codeMatch.index < firstMatch.index) firstMatch = { type: "code", index: codeMatch.index, full: codeMatch[0], content: codeMatch[1] }; }
    if (!firstMatch) { parts.push(remaining); break; }
    if (firstMatch.index > 0) parts.push(remaining.slice(0, firstMatch.index));
    if (firstMatch.type === "bold") parts.push(<strong key={key++} className="font-semibold text-white">{firstMatch.content}</strong>);
    else if (firstMatch.type === "code") parts.push(<code key={key++} className="bg-white/5 text-primary-400 px-1 py-0.5 rounded text-xs font-mono">{firstMatch.content}</code>);
    remaining = remaining.slice(firstMatch.index + firstMatch.full.length);
  }

  return <>{parts}</>;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") { elements.push(<div key={key++} className="h-2" />); i++; continue; }

    if (line.trim().startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) { codeLines.push(lines[i]); i++; }
      i++;
      elements.push(<pre key={key++} className="bg-black/30 text-emerald-400 text-xs p-4 rounded-lg overflow-x-auto my-3 font-mono border border-white/[0.06]"><code>{codeLines.join("\n")}</code></pre>);
      continue;
    }

    if (line.startsWith("# ")) { elements.push(<h1 key={key++} className="text-xl font-bold mt-6 mb-3 text-white border-b border-white/[0.06] pb-2">{renderInline(line.slice(2))}</h1>); i++; continue; }
    if (line.startsWith("## ")) { elements.push(<h2 key={key++} className="text-lg font-bold mt-5 mb-2 text-dark-text">{renderInline(line.slice(3))}</h2>); i++; continue; }
    if (line.startsWith("### ")) { elements.push(<h3 key={key++} className="text-base font-semibold mt-4 mb-2 text-dark-text">{renderInline(line.slice(4))}</h3>); i++; continue; }

    if (line.startsWith("> ")) {
      const quoteLines: string[] = [line.slice(2)];
      while (i + 1 < lines.length && lines[i + 1].startsWith("> ")) { i++; quoteLines.push(lines[i].slice(2)); }
      elements.push(<blockquote key={key++} className="border-l-4 border-primary-500/40 pl-4 py-2 my-3 bg-primary-500/5 text-sm text-dark-text rounded-r-lg">{quoteLines.map((ql, qi) => <p key={qi}>{renderInline(ql)}</p>)}</blockquote>);
      i++; continue;
    }

    if (line.startsWith("|") && i + 1 < lines.length && lines[i + 1].startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].startsWith("|")) { tableLines.push(lines[i]); i++; }
      const headerCells = tableLines[0].split("|").filter(Boolean).map((c) => c.trim());
      const dataRows = tableLines.slice(2);
      elements.push(
        <div key={key++} className="overflow-x-auto my-3">
          <table className="w-full text-sm border-collapse">
            <thead><tr className="bg-white/[0.03]">{headerCells.map((h, hi) => <th key={hi} className="px-3 py-2 text-left font-semibold text-dark-text border-b border-white/[0.06]">{renderInline(h)}</th>)}</tr></thead>
            <tbody>{dataRows.map((row, ri) => {
              const cells = row.split("|").filter(Boolean).map((c) => c.trim());
              return <tr key={ri} className={ri % 2 === 0 ? "" : "bg-white/[0.02]"}>{cells.map((c, ci) => <td key={ci} className="px-3 py-2 border-b border-white/[0.03] text-dark-text">{renderInline(c)}</td>)}</tr>;
            })}</tbody>
          </table>
        </div>
      );
      continue;
    }

    if (line.trim().startsWith("---")) { elements.push(<hr key={key++} className="my-4 border-white/[0.06]" />); i++; continue; }

    if (line.match(/^\d+\.\s/)) {
      const text = line.replace(/^\d+\.\s/, "");
      elements.push(<div key={key++} className="flex gap-2 ml-4 my-1 text-sm"><span className="text-primary-400 font-medium">{line.match(/^\d+/)?.[0]}.</span><span className="text-dark-text">{renderInline(text)}</span></div>);
      i++; continue;
    }
    if (line.startsWith("- ")) { elements.push(<div key={key++} className="flex gap-2 ml-4 my-1 text-sm"><span className="text-primary-400">-</span><span className="text-dark-text">{renderInline(line.slice(2))}</span></div>); i++; continue; }

    elements.push(<p key={key++} className="text-sm my-2 leading-relaxed text-dark-text">{renderInline(line)}</p>);
    i++;
  }
  return <>{elements}</>;
}
