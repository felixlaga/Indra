# Phase 6: OpenAlex, observed citations, semantic retrieval and scanned PDFs

Phase 6 widens what a session can find and how well its evidence search works.

## OpenAlex as a source

`openalex` joins `arxiv` and `semantic_scholar` as a session source. OpenAlex is free, needs no key and covers journals and conferences across fields, not only preprints. The session form now selects arXiv and OpenAlex by default.

- Abstracts are rebuilt from OpenAlex's inverted index; authors, venue, year, citation and reference counts and the best open-access PDF link are kept.
- A work whose DOI is arXiv's DataCite DOI (`10.48550/arxiv.*`) is keyed as `arxiv:<id>`, the same key the arXiv source produces, so one preprint is stored once.
- Session date, citation-count and open-access filters map to OpenAlex filters.
- With several sources, results are interleaved by rank before the paper limit is applied, so each source contributes. A preprint and its journal version with the same normalized title are read once.
- `INDRA_CONTACT_EMAIL`, when set, is sent as OpenAlex's `mailto` to use its faster "polite pool". Nothing is sent when it is blank.

## Observed citations

After a branch selects papers, the worker looks them up in OpenAlex in one batched request per identifier type (OpenAlex ID, DOI, arXiv DOI) and stores each paper's OpenAlex ID, reference list and reference count. The research map already turns `metadata.references` into observed `cites` edges whenever both papers are in the session, so the citation graph now shows real citation paths instead of only inferred "related" links. A failed lookup adds a `citations: <error>` warning and the run continues.

## Semantic evidence retrieval (optional)

Set `INDRA_EMBEDDING_MODEL` (for example `sentence-transformers/all-MiniLM-L6-v2`) for the API and worker. The model is downloaded once into the Hugging Face cache and runs locally on CPU through the existing `transformers`/`torch` dependencies; it stays off when the variable is blank.

- Passage embeddings are computed when a paper is read and stored in `paper_chunks.embedding` (pgvector `vector`, or a float array in `--without-vectors` mode). They are never sent to API clients.
- A passage now qualifies as candidate evidence on word overlap (as before) **or** on meaning (cosine ≥ 0.5). Lexical and semantic ranks are combined with reciprocal rank fusion; exact-wording matches win ties. Each validation trace records `retrieval: hybrid:<model>` or `lexical`, and per-passage semantic scores.
- Retrieval still only nominates passages. Support or contradiction is decided by the verifier, never by similarity.
- If the model cannot load, the worker logs it, records `embedding_warning`, and continues with lexical retrieval.

## Scanned PDFs

Pages that have images but no text layer are OCR'd with PyMuPDF when the `tesseract` program is installed (`brew install tesseract` on macOS), up to 40 pages per PDF. The paper's source note says how many pages were OCR'd and that OCR text can contain recognition errors, or how many scanned pages were skipped and why (Tesseract missing or the page limit reached). Page numbers remain real; no section titles are invented.

## Verification — October 8, 2026

- 198 backend tests against memory and real Postgres. New coverage: OpenAlex mapping, filters, `mailto`, batched lookups, arXiv-DOI keys; observed `cites` edges produced from enrichment; failed lookups as warnings; source interleaving and title deduplication; hybrid ranking finding a paraphrase with no shared words; embeddings stored and kept out of API output; embedder failure falling back; OCR notes with and without Tesseract and the OCR page limit.
- 24 frontend tests, TypeScript checking and the production build; the source picker and paper identifiers were checked in the browser.
- Live, without a model: OpenAlex search returned papers with abstracts and reference lists; a six-paper arXiv + OpenAlex session completed with every paper matched to OpenAlex. Several publisher PDFs refused automated download (HTTP 403 or an HTML page) and fell back to abstracts, as designed.
- Not verified live: the embedding model (not downloaded during this work) and Tesseract OCR (not installed). Both paths are covered by tests with fakes.
