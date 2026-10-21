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

const walkthrough = [
  {
    title: 'Choose your direction before you translate',
    image: 'translator-briefing.jpg',
    alt: 'Psalm 26 translator’s briefing with translation questions, saved answers, and Hebrew and Greek reading context.',
    description: 'Should Psalm 26 open with “judge me” or “vindicate me”? Read the context, choose an answer, and add your notes. Saved answers guide the translation automatically, so you do not have to repeat your decisions in a separate prompt.',
  },
  {
    title: 'Shape the words into a song',
    image: 'song-arrangement.jpg',
    alt: 'Psalm 26 in Arrangement, with editable song sections, lyric lines, and source references.',
    description: 'Work beyond verse boundaries: give a phrase its own line, build stanzas, or bring back a chorus. Keep explanations beside the lines that compress, expand, or depart from the original wording.',
  },
  {
    title: 'Return to the reasons behind a line',
    image: 'translation-history.jpg',
    alt: 'Saved Psalm 26 briefing and guidance history, preserving the decisions behind the translation.',
    description: 'Come back to a draft and see the briefing, answers, and guidance that shaped it. Review the recorded decisions alongside the translation instead of reconstructing why you chose a particular phrase.',
  },
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

      <section className="welcome-section walkthrough" aria-labelledby="walkthrough-title">
        <div className="section-heading">
          <p className="eyebrow">The workbench in action</p>
          <h2 id="walkthrough-title">See a psalm become a song</h2>
          <p>Start with a psalm or import a lyric draft. Explore what the words mean, decide how to render them, and shape a singable English setting while keeping its connection to the source. Here is Psalm 26 in the running application.</p>
          <p className="walkthrough-hint">Select any screenshot to see it at full size.</p>
        </div>
        <figure className="walkthrough-feature">
          <a href="./screenshots/current/source-flow.jpg" target="_blank" rel="noopener noreferrer" aria-label="Enlarge screenshot: Follow a lyric back to its source">
            <img src="./screenshots/current/source-flow.jpg" width="1265" height="712" alt="Sources view connects Hebrew and Greek words on the left to English lyric lines on the right with colored ribbons and meanings beneath each word." fetchPriority="high" />
          </a>
          <figcaption className="workflow-copy">
            <p className="eyebrow">Read · Compare · Trace</p>
            <h3>Follow a lyric back to its source</h3>
            <p>Why does this draft say “I please you in your truth” where the Hebrew speaks of walking? Read both originals with word meanings underneath, then follow the ribbons into the English lyric: this line draws on the Greek. Colors distinguish Hebrew, Greek, and phrases drawing on both. Click a word for closer study; matching lyric lines highlight as you move through the source.</p>
          </figcaption>
        </figure>
        <div className="walkthrough-grid">
          {walkthrough.map((flow) => (
            <figure className="walkthrough-card" key={flow.image}>
              <a href={`./screenshots/current/${flow.image}`} target="_blank" rel="noopener noreferrer" aria-label={`Enlarge screenshot: ${flow.title}`}>
                <img src={`./screenshots/current/${flow.image}`} width="1265" height="712" alt={flow.alt} loading="lazy" />
              </a>
              <figcaption className="workflow-copy">
                <h3>{flow.title}</h3>
                <p>{flow.description}</p>
              </figcaption>
            </figure>
          ))}
        </div>
        <details className="walkthrough-credits">
          <summary>About these examples and source credits</summary>
          <p>These screenshots show a local Psalm 26 draft and its saved study context. Drafts and proposed lexical matches remain subject to review.</p>
          <p>Hebrew: Tanach.us UXLC/WLC (public domain), with <a href="https://github.com/Clear-Bible/macula-hebrew">MACULA Hebrew</a> word data (CC BY 4.0) and <a href="https://github.com/openscriptures/morphhb">Open Scriptures Hebrew Bible</a> morphology (Open Scriptural Data).</p>
          <p>Greek: H. B. Swete, <i>The Old Testament in Greek according to the Septuagint</i>, vol. 2 (Cambridge, 1896), Psalms; transcribed from page images by the rahlfs1931-psalter project (CC BY-SA 4.0). Word meanings use <a href="https://www.STEPBible.org">STEP Bible</a>, based on work at Tyndale House Cambridge (TBESG brief Greek definitions and TIPNR names, CC BY 4.0), reformatted and matched to proposed lemmas; and <a href="https://github.com/QuantForgeSoftware/lxx">QuantForgeSoftware/lxx</a> Morpheus analyses of the First1KGreek Swete transcription (CC BY-SA 4.0), matched to local Swete spellings as unreviewed candidates.</p>
          <p>Additional Greek dictionary context: <i>A Greek-English Lexicon</i>, Liddell, Scott, Jones and McKenzie, Clarendon Press, provided by <a href="https://github.com/PerseusDL/lexica/">Perseus Digital Library</a> with National Endowment for the Humanities funding (CC BY-SA 4.0). Lookup keys convert Beta Code and omit quantity marks; brief English entries and explicit dictionary cross-references are retained as proposed matches. License terms: <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> and <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p>
        </details>
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
