# Doctrine corpus

Drop PDF or text files here to ground the COA generation agent in real
DoD logistics doctrine. This folder is empty by default — the pipeline
works fine without it (falls back to ungrounded LLM generation), and
starts using retrieved excerpts automatically as soon as files appear
here.

## What to add

See `docs/doctrine-references.md` for a curated starting list. Good
first additions, in priority order:

1. **Joint Concept for Contested Logistics (JCCL)** — Joint Staff J4, 2022
2. **JP 4-0, Joint Logistics** — the keystone joint doctrine document (2025 update)
3. **FM 4-0, Sustainment Operations** — Army doctrine, explicitly assumes
   contested-baseline logistics (Aug 2024)

Download these yourself from authoritative sources — this keeps you in
control of exactly which version of each document is in the corpus:

- **jcs.mil/Doctrine/Joint-Doctrine-Pubs/** — Joint Chiefs of Staff official doctrine library
- **armypubs.army.mil** — Army doctrine and field manuals
- **doctrine.af.mil** — Air Force doctrine publications and notes

## Notes

- PDFs are gitignored by default (see `.gitignore`) — they're often large,
  and redistributing official publications through your own repo isn't
  necessary when everyone can pull the current version from the source.
  If you want them version-controlled anyway (e.g., a private repo,
  fixed to a specific doctrine version for reproducibility), remove the
  `doctrine/*.pdf` line from `.gitignore`.
- The retrieval layer is a fresh load per process start. If you add or
  change files in this folder while the backend/notebook is already
  running, call `src.doctrine.retrieval.reset_retriever()` to force a
  reload, or just restart the process.
- Retrieval is keyword-based (BM25), not embeddings — no extra API key
  or cost, but it matches on shared vocabulary rather than semantic
  similarity. If a query and a relevant passage use very different
  wording for the same concept, it may not surface. Worth upgrading to
  embedding-based retrieval if that becomes a real limitation once the
  corpus grows.
