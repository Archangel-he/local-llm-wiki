function renderInline(text: string) {
  return text.split(/(\[\[[^\]]+\]\])/g).map((part, index) =>
    part.startsWith("[[") && part.endsWith("]]") ? (
      <span className="markdown-wikilink" key={`${part}-${index}`}>
        {part}
      </span>
    ) : (
      part
    ),
  );
}

export function MarkdownPreview({ blocks }: { blocks: string[] }) {
  return (
    <div className="markdown-preview">
      {blocks.flatMap((block, blockIndex) =>
        block.split(/\r?\n/).map((line, lineIndex) => {
          const key = `${blockIndex}-${lineIndex}`;
          if (line.startsWith("# ")) {
            return <h2 key={key}>{renderInline(line.slice(2))}</h2>;
          }
          if (line.startsWith("## ")) {
            return <h3 key={key}>{renderInline(line.slice(3))}</h3>;
          }
          if (line.startsWith("- ")) {
            return (
              <p className="markdown-list-item" key={key}>
                {renderInline(line.slice(2))}
              </p>
            );
          }
          if (!line.trim()) return null;
          return <p key={key}>{renderInline(line)}</p>;
        }),
      )}
    </div>
  );
}
