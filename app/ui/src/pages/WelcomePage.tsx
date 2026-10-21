const repoUrl = 'https://github.com/wirelessdreamer/AlephTav';
const docsUrl = `${repoUrl}/blob/main/docs/README.md`;
const readmeUrl = `${repoUrl}/blob/main/README.md`;
const publicSite = import.meta.env.VITE_PUBLIC_SITE === 'true';

const quickStart = [
  'git clone https://github.com/wirelessdreamer/AlephTav.git',
  'cd AlephTav',
  './setup.sh          # macOS / Linux',
  '.\\setup.ps1       # Windows PowerShell',
];

const fullSetup = [
  'Workbench: http://127.0.0.1:43173/#/workbench',
  'API:       http://127.0.0.1:43174',
];

const workflows = [
  {
    title: 'Brief, decide, translate',
    description: 'Prepare a translator’s briefing, inspect Hebrew and Greek beside each question, and record answers and notes. Saved decisions automatically guide translation and stay linked to its history.',
  },
  {
    title: 'Read Hebrew and Greek word by word',
    description: 'See source words with meanings underneath. Hover for lexical context or click to keep word study open; Hebrew and Greek share highlighting, outlines, keyboard access, and outside-click dismissal in Sources.',
  },
  {
    title: 'Follow the source into the song',
    description: 'Sources keeps a left-to-right flow map visible, with Hebrew, Greek, and mixed phrase contributions. Matching English lines highlight as you scroll, and the translation follows the source verse.',
  },
  {
    title: 'Arrange and explain your choices',
    description: 'Build stanzas, choruses, repeats, and added lines. Sources also shows saved arrangement context; its decision trail explains source choices without treating an added line as source text.',
  },
  {
    title: 'Import, revise, and review',
    description: 'Keep translations in separate projects, import existing lyrics, compare literal and lyrical readings, and review accuracy and creative liberties. Verse history records guidance, decisions, notes, and rebuilds.',
  },
  {
    title: 'Read on a phone, work in full',
    description: 'Phone views focus on verse comparison, word evidence, and review. Switch to the full workbench for briefing, arrangements, Sources, and advanced tools. Loading and retry messages keep pending work visible.',
  },
];

export function WelcomePage() {
  return (
    <main className={`welcome-shell${publicSite ? ' welcome-shell--public' : ''}`}>
      <section className="welcome-hero">
        <div className="hero-copy">
          <div className="hero-brand">
            <img src="./brand/alephtav-mark.svg" alt="" width="88" height="88" />
            <div>
              <p className="eyebrow">AlephTav</p>
              <h1>Psalms Copyleft Workbench</h1>
            </div>
          </div>
          <p className="hero-summary">
            Study the Hebrew and Greek, record your translation decisions, and trace them into a singable English setting. AlephTav keeps source words, briefing notes, arrangements, and review history together in a local Psalms workbench.
          </p>
          <div className="hero-actions">
            <a className="hero-link hero-link-primary" href={publicSite ? '#run-it' : '#/workbench'}>
              {publicSite ? 'Get started locally' : 'Open Workbench'}
            </a>
            <a className="hero-link" href={readmeUrl}>
              Source & setup
            </a>
            <a className="hero-link" href={docsUrl}>
              Docs Index
            </a>
          </div>
        </div>
        <div className="hero-card">
          <h2>Available in the workbench</h2>
          <ul className="feature-list">
            <li>Hebrew and Greek interlinear word study</li>
            <li>Saved briefing answers that guide translation</li>
            <li>Source flow, mixed phrases, and decision trails</li>
            <li>Song arrangements with contextual notes and history</li>
            <li>Projects, imports, exports, and a focused phone view</li>
          </ul>
        </div>
      </section>

      <section className="welcome-section" id="run-it">
        <div className="section-heading">
          <p className="eyebrow">Run It</p>
          <h2>Quick local startup</h2>
          <p>The workbench runs on your computer. Use Python 3.11+, Node.js 20+, and npm, then run the setup script for your platform to install dependencies, prepare data, and start the local UI and API.</p>
          {publicSite ? <p>This public site describes the application. Translation, saved projects, and assistant connections run in your local installation.</p> : null}
        </div>
        <div className="command-grid">
          <article className="command-card">
            <h3>Setup scripts</h3>
            <pre>
              <code>{quickStart.join('\n')}</code>
            </pre>
          </article>
          <article className="command-card">
            <h3>After setup</h3>
            <pre>
              <code>{fullSetup.join('\n')}</code>
            </pre>
          </article>
        </div>
      </section>

      <section className="welcome-section">
        <div className="section-heading">
          <p className="eyebrow">Usage</p>
          <h2>From source words to reviewed lyrics</h2>
          <p>These workflows are implemented in the current application. Codex-assisted briefing, translation, and analysis require a configured connection; generation and export also depend on the selected sources’ permissions.</p>
        </div>
        <div className="workflow-grid">
          {workflows.map((workflow) => (
            <article key={workflow.title} className="workflow-card">
              <div className="workflow-copy">
                <h3>{workflow.title}</h3>
                <p>{workflow.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="welcome-section">
        <div className="section-heading">
          <p className="eyebrow">Source coverage</p>
          <h2>A Psalms workspace with broader Greek lookup resources</h2>
          <p>Verse comparison retains the Hebrew Masoretic text. Greek Psalm readings use edition-specific Septuagint correspondence, including differences in numbering. Lexical lookup resources cover Septuagint and Greek New Testament forms; the translation workspace remains focused on Psalms.</p>
          <p>Word glosses are reading aids, not reviewed sentence translations. Proposed matches, unresolved words, and preview sources remain labeled. Source licenses and credits are available in dedicated disclosures, and release exports remain subject to source permissions and reviewer approval.</p>
        </div>
      </section>

      <section className="welcome-section welcome-section--compact">
        <div className="section-heading">
          <p className="eyebrow">Reference</p>
          <h2>Project docs</h2>
        </div>
        <div className="docs-grid">
          <a className="doc-card" href={docsUrl}>
            <strong>Documentation Index</strong>
            <span>Entry point for contribution, translation, audit, release, and source-policy docs.</span>
          </a>
          <a className="doc-card" href={`${repoUrl}/blob/main/docs/TRANSLATION_POLICY.md`}>
            <strong>Translation Policy</strong>
            <span>Canonical vs alternate rules, layer expectations, and rendering constraints.</span>
          </a>
          <a className="doc-card" href={`${repoUrl}/blob/main/docs/DATA_SOURCES.md`}>
            <strong>Data Sources</strong>
            <span>Source manifests, usage restrictions, and export/display policy.</span>
          </a>
        </div>
      </section>
    </main>
  );
}
