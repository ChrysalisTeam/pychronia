# Replacing the AIML djinns with an LLM + RAG

Analysis written on 2026-11-14. Nothing described here is implemented yet.

Goal: make the "artificial intelligence" ability answer through a real LLM (e.g. a local
model served by LM Studio) instead of AIML, while restricting its answers to content from
the encyclopedia or other fixed sources, and keeping the portal's authentication as the
gatekeeper of the chat.

Recommendation in one sentence: keep the existing ability as the shell, replace only the
`DjinnProxy` engine, and use neither a vector DB nor a RAG framework.

Caveat: library and version details below were written from memory, without checking
current documentation. Verify them before implementing (in particular the MariaDB version
that introduced `VECTOR`).


## Current state

- `pychronia_game/views/abilities/artificial_intelligence_mod.py` holds
  `ArtificialIntelligenceAbility` and the `DjinnProxy` singleton wrapping a `python-aiml`
  kernel, enabled by the `ACTIVATE_AIML_BOTS` setting.
- The ability already declares `ACCESS = UserAccess.character`,
  `REQUIRES_CHARACTER_PERMISSION = True` and `REQUIRES_GLOBAL_PERMISSION = True`.
- Per-user chat history is stored in the ability's private data (`_inputHistory`,
  `_outputHistory`), and `bot_max_answers` / `terminal_answers` act as a per-user quota.
- `get_bot_response()` is a `@transaction_watcher` method which holds
  `djinn_singleton_lock` during the whole AIML call.
- The frontend (`templates/abilities/artificial_intelligence.html`) posts the
  `process_user_sentence` action through AJAX and expects a JSON `{response: ...}`.
- The `Encyclopedia` datamanager module (`datamanager/datamanager_modules.py`) stores
  articles as static pages of category `encyclopedia`, each with regex `keywords`;
  `get_encyclopedia_matches()` does keyword-based search, and each character has a
  `known_article_ids` list.


## Recommended architecture

```
browser --POST (existing AJAX)--> ArtificialIntelligenceAbility   (auth + quotas, unchanged)
                                        |
                                        +- retrieve: keyword regex + embeddings (in-process, numpy)
                                        +- generate: OpenAI-compatible HTTP call --> LM Studio (localhost only)
```

- **Authentication:** nothing to build. Access checks are already done by the ability, and
  the LLM is called server-side from Django. Bind LM Studio to localhost so that browsers
  never reach it directly.
- **LLM client:** the `openai` package pointed at LM Studio's OpenAI-compatible endpoint
  (`http://localhost:1234/v1`), used for both chat completions and embeddings. The same
  code then works with Ollama, llama.cpp's `llama-server`, vLLM or a cloud API, by
  changing a base URL in settings.
- **Retrieval:** embed article chunks once, keep them as a numpy matrix in memory, and do
  a brute-force cosine similarity. An encyclopedia of a few hundred articles is searched
  in microseconds this way.
- **Hybrid search:** union the embedding hits with `get_encyclopedia_matches()`.
  Embedding models handle invented proper nouns poorly, and the per-article keyword
  regexes cover exactly that case.
- **New dependencies:** `openai` and `numpy` only (and `python-aiml` can go). LangChain
  and LlamaIndex are not worth it here: the whole pipeline is about 150 lines, and they
  add heavy, fast-churning dependencies.


## Vector storage options

| Option | Verdict |
|---|---|
| numpy in memory, with an on-disk cache keyed by content hash and embedding model | Recommended; enough up to tens of thousands of chunks |
| `sqlite-vec` (single file, no server) | The next step if the corpus grows large |
| MariaDB native `VECTOR` | Not available on the prod 11.4; it arrived around 11.7, so it needs an upgrade to 11.8 LTS (to be verified) |
| Chroma, Qdrant, pgvector | An extra service to operate, with no benefit at this scale |

Embeddings should not be stored in ZODB: they bloat the pickles and are purely derived
data.


## sqlite-vec in more detail

This is the store to switch to if the corpus grows to thousands of pages (roughly 10,000
to 50,000 chunks). At that size brute-force search is still fast (a few milliseconds);
what breaks with the in-memory numpy approach is around it:

- **Memory:** 50,000 vectors of 1024 floats is about 200 MB, copied in each Django worker.
- **Startup:** every worker loads that matrix when it starts.
- **Updates:** editing one article should rewrite a few rows, not a whole cache file.
- **Filtering:** "only this djinn's whitelist" or "only articles this character knows"
  becomes a `WHERE` clause instead of hand-written numpy masks.

The facts below were checked on 2026-11-14 against the project's README
(https://github.com/asg017/sqlite-vec) and its Python guide
(https://alexgarcia.xyz/sqlite-vec/python.html), except where stated otherwise.

### How it works

`sqlite-vec` is a small C extension loaded into SQLite. It adds a new kind of table,
`vec0`, whose rows hold a vector plus optional ordinary columns.

```python
import sqlite3, sqlite_vec

db = sqlite3.connect("encyclopedia_index.sqlite")
db.enable_load_extension(True)
sqlite_vec.load(db)
db.enable_load_extension(False)

db.execute("CREATE VIRTUAL TABLE chunks USING vec0(embedding float[1024])")

# insert: a numpy float32 array is accepted directly
db.execute("INSERT INTO chunks(rowid, embedding) VALUES (?, ?)", (42, vector.astype("float32")))

# search: the 5 nearest chunks to the question's vector
rows = db.execute(
    "SELECT rowid, distance FROM chunks WHERE embedding MATCH ? ORDER BY distance LIMIT 5",
    (question_vector.astype("float32"),),
).fetchall()
```

- **Storage:** each vector is stored as a compact binary blob (4 bytes per number),
  inside the normal SQLite file.
- **Search:** the `MATCH ... ORDER BY distance LIMIT n` query computes the distance
  between the question vector and the stored vectors, and returns the closest `n`. This
  is believed to be a full scan (brute force) in optimised C; the README does not say so
  explicitly.
- **Linking to the content:** the `rowid` points to a regular table holding the chunk
  text, article id and category, joined as usual.
- **Extra columns:** the `vec0` table can also carry metadata, auxiliary and
  partition-key columns, allowing filters in the same query. The README mentions them
  without detail; the exact syntax is not verified.

### Pros

- **No server:** one `pip install sqlite-vec` and one file; backup is a file copy.
- **Plain SQL:** joins, `WHERE` filters and transactions work as in any SQLite database.
- **Hybrid search in one place:** SQLite's built-in FTS5 full-text index can live in the
  same file, next to the vectors.
- **Shared across workers:** all Django processes read the same file, instead of each
  holding a copy in memory.
- **Incremental updates:** editing an article means replacing a few rows.
- **Small and portable:** no dependencies, runs on Windows and Linux.

### Cons

- **Pre-1.0:** the README warns "expect breaking changes". Tolerable here, since the
  index is derived data which can be rebuilt, but the version must be pinned.
- **Brute-force search:** query time grows linearly with the number of chunks. The
  repository contains files named for IVF and DiskANN indexes, but the README does not
  document them, so an approximate index should not be counted on.
- **Single writer:** SQLite allows one write at a time. Fine for an index written only
  when articles change.
- **Python build requirements:** the `sqlite3` module must allow extension loading. The
  Python bundled with macOS does not; the standard Windows and Linux builds are believed
  to (not verified).
- **SQLite version:** 3.41 or later is recommended, and some features need it. Check with
  `python -c "import sqlite3; print(sqlite3.sqlite_version)"`. On Windows the SQLite
  bundled with Python cannot be swapped, so upgrading it means upgrading Python.
- **One-person project:** maintained mainly by a single author, hence more abandonment
  risk than MariaDB or Postgres.
- **A second data store:** it sits beside ZODB and MariaDB, with its own file to deploy
  and keep in sync with the articles.

### Retrieval quality at that scale

With thousands of pages, the hard part becomes retrieval quality rather than the store:
many articles look vaguely relevant, and the right one may rank eighth instead of first.

- **Hybrid search:** keep combining keyword matches with embedding matches.
- **Reranking:** retrieve the top 30 or so cheaply, then have a small "reranker" model
  score each one against the question and keep the best five (bge-reranker is the usual
  companion to bge-m3).


## What makes it robust

1. **Restrict sources in code, not in the prompt.** Each djinn gets a whitelist in
   `specific_bot_properties` (static-page categories or article ids), and only those
   chunks are indexed for it. The model cannot leak what it never receives, whatever a
   player types.
2. **Refuse before calling the LLM.** If no chunk passes the similarity threshold and no
   keyword matches, return a canned in-character answer, like the existing
   `terminal_answers`.
3. **Constrain generation.** System prompt with the djinn persona and "answer only from
   the excerpts below, otherwise say you don't know"; low temperature; a `max_tokens`
   cap; only the last few turns of the existing history.
4. **Keep the LLM call out of the ZODB transaction and of the global lock.** Holding both
   is fine for AIML's milliseconds, not for a multi-second LLM call. Retrieve and generate
   first, then write the history in a short transaction.
5. **Fail gracefully.** Set an HTTP timeout and fall back to the existing
   `[DJINN IS OFFLINE]` path; `bot_max_answers` keeps serving as a per-user quota.
6. **Re-index on change.** The game master can edit static pages, so hash each chunk and
   re-embed only what changed, lazily, like the current `DJINN_PROXY` singleton.


## Practical notes

- **Chunking:** one chunk per article, with the title prefixed; split by paragraph only
  for long articles.
- **Embedding model:** pick a multilingual one (bge-m3 or multilingual-e5, for example)
  if the game content is in French.
- **Follow-up questions:** embed the previous and current user messages together, which
  avoids an extra LLM call to rewrite the query.
- **Production:** LM Studio is fine for development, but on a server Ollama or
  `llama-server` is easier to run as a service, with no code change.
- **Concurrency:** a local model serves requests more or less serially, and each one
  blocks a Django worker. Acceptable for a game with a few dozen players; streaming can
  be skipped in a first version, since the existing JSON POST works as is.


## Open decision

Should a djinn answer from every article of its whitelist, or only from the articles the
character has already discovered (`known_article_ids`)?

The second option is a one-line filter at retrieval time, but it changes gameplay: with
the first one, the chat becomes a way around the encyclopedia's discovery mechanic.
