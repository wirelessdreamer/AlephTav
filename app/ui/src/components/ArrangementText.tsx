import { useState } from 'react';

import type { ArrangementView } from '../types';

/** The setting as a plain lyric sheet: title, then each section's label and sung lines. */
function lyricSheet(view: ArrangementView): string {
  const blocks: string[] = [view.arrangement.title];
  let sectionId: string | null = null;
  for (const sung of view.sung) {
    if (sung.section_id !== sectionId) {
      sectionId = sung.section_id;
      blocks.push(`\n[${sung.section_label || sung.kind}]`);
    }
    blocks.push(sung.line.text);
  }
  return blocks.join('\n');
}

/** The song setting as raw text, in sung order with repeats written out, to copy. */
export function ArrangementText({ view }: { view: ArrangementView }) {
  const text = lyricSheet(view);
  const [copied, setCopied] = useState<'yes' | 'failed' | null>(null);

  return (
    <div className="arr-text">
      <div className="arr-text__actions">
        <button
          type="button"
          className="btn-primary"
          onClick={() =>
            navigator.clipboard
              .writeText(text)
              .then(() => setCopied('yes'))
              .catch(() => setCopied('failed'))
          }
        >
          Copy text
        </button>
        <span className="subtle" aria-live="polite">
          {copied === 'yes' ? 'Copied.' : copied === 'failed' ? 'Copy failed; select the text instead.' : ''}
        </span>
      </div>
      <pre className="arr-text__sheet">{text}</pre>
    </div>
  );
}

export default ArrangementText;
