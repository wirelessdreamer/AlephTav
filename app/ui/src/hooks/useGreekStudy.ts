import { useEffect, useState } from 'react';

export type StudyIdentity = { study_snapshot_id: string; policy_revision_id: string };
export type Edition = StudyIdentity & { edition_id: string; text_revision_id: string };
export type GreekToken = { token_id: string; surface: string; position: number };
export type GreekUnit = { unit_id: string; ref: string; source_greek: string; tokens: GreekToken[] };
export type Presentation = { type: string; text?: string; children?: Presentation[] };
export type Attribution = { source_id: string; required_attribution: string; license: string };
export type Entry = {
  gloss?: string;
  entry_id: string; headword: string; attribution?: Attribution; presentation?: Presentation | Presentation[];
  citations?: { original_label: string; baseline: string; machine_reference?: string }[];
};
export type Analysis = {
  analysis_id: string; lemma?: string; lexeme_id?: string; status: string;
  scheme?: string; raw_tag?: string; features?: Record<string, string>;
  identifiers?: { scheme: string; value: string }[];
};
export type ConcordanceQuery = StudyIdentity & {
  query_kind: 'surface' | 'lexeme_id' | 'lemma_text' | 'identifier'; value: string;
  identifier_scheme?: string | null; analysis_scope: 'all' | 'reviewed' | 'proposed';
  analysis_selection: 'selected' | 'possible'; match_unit: 'token' | 'expression';
  expand_components: boolean;
};
export type WordCard = StudyIdentity & {
  token: GreekToken; analyses: Analysis[]; dictionary_entries: Entry[];
  query: ConcordanceQuery; counts: { total_matches: number; total_tokens: number; total_verses: number };
  source_attribution?: { source_id: string; attribution: string; license: string }[];
};
export type Occurrences = StudyIdentity & {
  total_matches: number; total_tokens: number; total_verses: number; next_cursor: string | null;
  coverage: { unresolved: number; statement: string };
  matches: { occurrence_id: string; unit_id: string; psalm: number; verse: number; surface: string }[];
};

export function studyUrl(path: string, params: object): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) search.set(key, String(value));
  });
  return `${path}?${search}`;
}

/** Abort and discard outdated project/edition/card responses, including first pages. */
export function useGreekStudy<T>(url: string | null, context: string) {
  const [result, setResult] = useState<{ key: string; data?: T; error?: string; loading: boolean }>(
    { key: '', loading: false },
  );
  const key = `${context}|${url}`;
  useEffect(() => {
    if (!url) return;
    const controller = new AbortController();
    let active = true;
    setResult({ key, loading: true });
    fetch(url, { signal: controller.signal }).then(async (response) => {
      if (!response.ok) {
        if (response.status === 409) throw new Error('Study changed. Restart Greek study to load a coherent view.');
        if (response.status === 403) throw new Error('This source is currently unavailable.');
        throw new Error('Could not load Greek study.');
      }
      return response.json() as Promise<T>;
    }).then((data) => {
      if (active) setResult({ key, data, loading: false });
    }).catch((error: Error) => {
      if (active && error.name !== 'AbortError') setResult({ key, error: error.message, loading: false });
    });
    return () => { active = false; controller.abort(); };
  }, [url, key]);
  return result.key === key ? result : { loading: Boolean(url), data: undefined, error: undefined };
}
