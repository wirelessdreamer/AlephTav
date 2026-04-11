const repoUrl = 'https://github.com/wirelessdreamer/AlephTav';
const docsUrl = `${repoUrl}/blob/main/docs/README.md`;
const readmeUrl = `${repoUrl}/blob/main/README.md`;

const quickStart = [
  './setup.sh',
  '.\\setup.ps1',
];

const fullSetup = [
  'source .venv/bin/activate',
  'python scripts/seed_project.py',
  'python scripts/import_psalms.py',
  'python scripts/build_indexes.py',
  'python scripts/validate_content.py',
  'python -m uvicorn app.api.main:app --reload',
  'npm run dev',
];

const workflows = [
  {
    title: 'Lexical analysis',
    description: 'Hover or pin Hebrew tokens to inspect lemma, morphology, syntax role, semantic role, glosses, and Psalms-wide occurrence context.',
    image: './screenshots/lexical-analysis.svg',
    alt: 'Lexical analysis reference view showing Hebrew token details and concordance context.',
  },
  {
    title: 'Translation and review',
    description: 'Compare canonical and alternate English renderings by layer, review provenance, and manage promotion workflow against exact Hebrew alignment anchors.',
    image: './screenshots/translation-workflow.svg',
    alt: 'Translation workflow reference view showing layered rendering and review controls.',
  },
];

export function WelcomePage() {
  return (
    <main className="welcome-shell">
      <section className="welcome-hero">
        <div className="hero-copy">
          <p className="eyebrow">AlephTav</p>
          <h1>Psalms Copyleft Workbench</h1>
          <p className="hero-summary">
            A local-first translation workbench for Hebrew-source Psalms with lexical inspection, alignment review, alternate renderings, audit trails, and release export.
          </p>
          <div className="hero-actions">
            <a className="hero-link hero-link-primary" href="#/workbench">
              Open Workbench
            </a>
            <a className="hero-link" href={readmeUrl}>
              README
            </a>
            <a className="hero-link" href={docsUrl}>
              Docs Index
            </a>
          </div>
        </div>
        <div className="hero-card">
          <h2>What It Covers</h2>
          <ul className="feature-list">
            <li>Hebrew token inspection with lexical and morphology context</li>
            <li>Layered English renderings from gloss through lyric variants</li>
            <li>Alignment editing, review state, drift warnings, and provenance checks</li>
            <li>Local API, CLI, JSON content store, and release bundle generation</li>
          </ul>
        </div>
      </section>

      <section className="welcome-section">
        <div className="section-heading">
          <p className="eyebrow">Run It</p>
          <h2>Quick local startup</h2>
          <p>Use the platform setup script to verify runtimes, install dependencies, run the default full rebuild, and launch both local services.</p>
        </div>
        <div className="command-grid">
          <article className="command-card">
            <h3>Setup scripts</h3>
            <pre>
              <code>{quickStart.join('\n')}</code>
            </pre>
          </article>
          <article className="command-card">
            <h3>Manual full rebuild</h3>
            <pre>
              <code>{fullSetup.join('\n')}</code>
            </pre>
          </article>
        </div>
      </section>

      <section className="welcome-section">
        <div className="section-heading">
          <p className="eyebrow">Usage</p>
          <h2>Two core workflows</h2>
          <p>The reference views below mirror the fixture-backed workbench flows used in local development and test setup.</p>
        </div>
        <div className="workflow-grid">
          {workflows.map((workflow) => (
            <article key={workflow.title} className="workflow-card">
              <img src={workflow.image} alt={workflow.alt} />
              <div className="workflow-copy">
                <h3>{workflow.title}</h3>
                <p>{workflow.description}</p>
              </div>
            </article>
          ))}
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
