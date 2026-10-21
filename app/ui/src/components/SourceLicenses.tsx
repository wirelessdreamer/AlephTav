import type { BriefingGreekSources } from '../types';

/** Keep reading notes and source credits available once, outside the word cards. */
export function SourceLicenses({ sources }: { sources?: BriefingGreekSources }) {
  return <details className="source-licenses">
    <summary>Sources &amp; licenses</summary>
    <p>Word-by-word readings show dictionary meanings in source order, with alternatives separated by /.
      They are separate from saved verse translations. A ? marks an unresolved word; bracketed meanings
      need source or lexical review. The printed source text is unchanged.</p>
    {sources?.preview && sources.message ? <p>{sources.message}</p> : null}
    {sources?.source_attribution?.map((source, index) => <p key={index}>
      {source.attribution} · {source.license}
    </p>)}
  </details>;
}
