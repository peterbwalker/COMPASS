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
- Retrieval is BM25 (keyword) by default, automatically upgraded to
  hybrid BM25 + semantic embeddings if `sentence-transformers` and
  `torch` are installed (see requirements.txt) -- no code changes
  needed, `get_retriever()` detects this itself. Embeddings catch
  passages that are conceptually relevant but share no vocabulary with
  the query (e.g. "fuel replenishment" matching a passage about
  "petroleum resupply"), which pure BM25 misses. A local GPU makes
  embedding generation faster but isn't required -- it runs on CPU too,
  just slower. See `src/doctrine/embeddings.py` for the embedding model
  used and how to swap it.
