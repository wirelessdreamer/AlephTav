# Documentation Index

This project publishes a static GitHub Pages welcome page, but the actual translation workbench runs locally against the FastAPI backend.

Start here:

- [`../README.md`](../README.md): local setup, quick demo run, screenshot refresh, and test commands

Core workflow and policy docs:

- [`CONTRIBUTING.md`](CONTRIBUTING.md): contributor workflow and repo expectations
- [`TRANSLATION_POLICY.md`](TRANSLATION_POLICY.md): canonical vs alternate rendering policy
- [`REVIEW_POLICY.md`](REVIEW_POLICY.md): review gates, roles, and promotion expectations
- [`AUDIT_POLICY.md`](AUDIT_POLICY.md): audit requirements, open-concern reporting, and release checks
- [`STYLE_PROFILES.md`](STYLE_PROFILES.md): rendering style profiles and target constraints
- [`DATA_SOURCES.md`](DATA_SOURCES.md): upstream sources, licenses, and usage restrictions
- [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md): release workflow, protection rules, and export bundles
- [`research/local_translation_model_report.md`](research/local_translation_model_report.md): local Hebrew-to-English model research baseline and benchmark plan
- Generate the integrated research portfolio dashboard: `python scripts/generate_research_portfolio_dashboard.py`
- Generate the visual model research dashboard: `python scripts/generate_local_model_research_report.py`
- Generate the visual Psalms corpus profile: `python scripts/generate_psalms_corpus_profile.py`
- Generate the visual contextual evaluation report: `python scripts/generate_psalms_contextual_evaluation_report.py`
- Generate the visual Tanakh lexical context profile: `python scripts/generate_tanakh_lexical_context_report.py`
- Generate the lexeme context readiness audit: `python scripts/generate_lexeme_context_readiness_report.py`
- Generate the canonical context network: `python scripts/generate_canonical_context_network_report.py`
- Generate the witness/reception readiness audit: `python scripts/generate_witness_reception_readiness_report.py`
- Generate the reception interpretation boundary ledger: `python scripts/generate_reception_interpretation_boundary_report.py`
- Generate visual seed context packets: `python scripts/generate_psalms_seed_context_packets.py`
- Generate the 100-unit benchmark expansion plan: `python scripts/generate_benchmark_expansion_plan.py`
- Generate the benchmark context/reception matrix: `python scripts/generate_benchmark_context_reception_matrix.py`
- Generate the contextual pressure atlas: `python scripts/generate_contextual_pressure_atlas.py`
- Generate contextual benchmark coverage gaps: `python scripts/generate_contextual_benchmark_coverage_report.py`
- Generate contextual gap benchmark supplement: `python scripts/generate_contextual_gap_benchmark_supplement.py`
- Generate priority unit dossiers: `python scripts/generate_priority_unit_dossiers.py`
- Generate priority benchmark supplement: `python scripts/generate_priority_benchmark_supplement.py`
- Generate integrated benchmark suite: `python scripts/generate_integrated_benchmark_suite.py`
- Generate contextual expanded benchmark suite: `python scripts/generate_contextual_expanded_benchmark_suite.py`
- Generate scholarly authority readiness audit: `python scripts/generate_scholarly_authority_readiness_report.py`
- Score integrated benchmark real results: `python scripts/score_local_model_benchmark_results.py --suite reports/research/integrated_benchmark_suite.json --results reports/research/local_model_benchmark_results.jsonl --json-output reports/research/integrated_benchmark_result_audit.json --html-output reports/research/integrated_benchmark_result_audit.html`
- Generate integrated review signoff plan: `python scripts/generate_review_signoff_plan.py --suite reports/research/integrated_benchmark_suite.json --audit reports/research/integrated_benchmark_result_audit.json --json-output reports/research/integrated_review_signoff_plan.json --csv-output reports/research/integrated_review_signoff_template.csv --html-output reports/research/integrated_review_signoff_plan.html`
- Generate the local model benchmark suite: `python scripts/generate_local_model_benchmark_suite.py`
- Generate model cross-examination packets: `python scripts/generate_model_cross_exam_protocol.py`
- Generate local runtime readiness audit: `python scripts/generate_local_runtime_readiness_report.py`
- Generate local model asset inventory: `python scripts/generate_local_model_asset_inventory.py`
- Generate structured-output tuning report: `python scripts/generate_structured_output_tuning_report.py`
- Generate real model smoke-test report: `python scripts/generate_real_model_smoke_test_report.py`
- Run local model benchmark tasks: `python scripts/run_local_model_benchmark_suite.py --model-profile docs/research/local_model_profile_template.json --limit 1`
- Run Windows Ollama benchmark bridge: `python scripts/run_windows_ollama_benchmark_suite.py --model gemma4:26b --model-profile-id google/gemma-4-26B-A4B-it --limit 1`
- Score local model benchmark results: `python scripts/score_local_model_benchmark_results.py`
- Generate review signoff plan and CSV: `python scripts/generate_review_signoff_plan.py`

Visual reference:

- Lexical analysis reference view: [`../app/ui/public/screenshots/lexical-analysis.svg`](../app/ui/public/screenshots/lexical-analysis.svg)
- Translation workflow reference view: [`../app/ui/public/screenshots/translation-workflow.svg`](../app/ui/public/screenshots/translation-workflow.svg)
