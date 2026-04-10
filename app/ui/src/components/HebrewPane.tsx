import type { Token } from '../types';

interface HebrewPaneProps {
  tokens: Token[];
  activeTokenId: string | null;
  highlightedTokenIds: string[];
  selectedTokenIds: string[];
  onHoverToken: (tokenId: string | null) => void;
  onPinToken: (tokenId: string) => void;
  onToggleToken: (tokenId: string) => void;
}

export function HebrewPane({
  tokens,
  activeTokenId,
  highlightedTokenIds,
  selectedTokenIds,
  onHoverToken,
  onPinToken,
  onToggleToken,
}: HebrewPaneProps) {
  return (
    <section className="pane pane-hebrew">
      <header className="pane-header">
        <h2>Hebrew source</h2>
        <span className="subtle">Canonical UXLC/WLC-derived text</span>
      </header>
      <div className="hebrew-token-grid" dir="rtl">
        {tokens.map((token) => {
          const active = activeTokenId === token.token_id;
          const linked = highlightedTokenIds.includes(token.token_id);
          const selected = selectedTokenIds.includes(token.token_id);
          return (
            <button
              key={token.token_id}
              className={`hebrew-token ${active ? 'active' : ''} ${linked ? 'linked' : ''} ${selected ? 'selected' : ''}`}
              onMouseEnter={() => onHoverToken(token.token_id)}
              onMouseLeave={() => onHoverToken(null)}
              onClick={() => {
                onToggleToken(token.token_id);
                onPinToken(token.token_id);
              }}
              type="button"
              title={`${token.token_id} • ${token.surface} • ${token.lemma} • ${token.strong}`}
              aria-pressed={selected}
            >
              <span className="surface">{token.surface}</span>
              <span className="token-meta">{token.token_id}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
