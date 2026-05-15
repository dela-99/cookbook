# Pre-Deployment Checklist for Chatbot

You built a RAG chatbot. It answers questions in dev. Now you're about to put it in front of real users — and the gap between "works on my laptop" and "trustworthy in production" is where most chatbot projects fail. This checklist covers the nine things I verify before deploying any retrieval-augmented chatbot.

## 1. Document Chunking — Semantic Chunking with Overlap

**What it means.** Instead of splitting documents at fixed character counts (which slices sentences mid-thought), you chunk based on semantic boundaries — paragraphs, sections, topic shifts. Each chunk overlaps with its neighbors by a configurable window (typically 10–20% of chunk size) so that an answer that spans two chunks isn't lost at the seam.

**Why it matters before deploy.** Fixed-size chunking produces fragments that start and end mid-sentence. When the retriever pulls one of those fragments, the LLM gets incomplete context and either hallucinates the missing parts or gives a vague non-answer. Semantic chunking with overlap ensures every retrieved piece is self-contained enough to be useful, and the overlap guarantees that boundary-spanning information appears in at least one chunk.

## 2. Retrieval — Hybrid Search (Vector Embeddings + BM25)

**What it means.** You run two retrieval paths in parallel. **Vector search** encodes the query and documents into dense embeddings and finds semantically similar chunks — great for paraphrased questions. **BM25** is a classic keyword-based scoring algorithm — great for exact names, IDs, error codes, and domain-specific terms that embeddings sometimes miss. Results from both paths are merged (usually via Reciprocal Rank Fusion) before re-ranking.

**Why it matters before deploy.** Pure vector search fails on exact-match queries. A user asking for "order #A7X-9021" needs lexical matching, not semantic similarity. Pure BM25 fails on paraphrased or conceptual questions. Hybrid search covers both failure modes. In production, user queries are unpredictable — some are natural language, some are copy-pasted identifiers — and hybrid retrieval handles the full spectrum without you having to guess which type will come next.

## 3. Re-Ranking — Cross-Encoder on Top 5 Chunks

**What it means.** After hybrid retrieval returns a broad set of candidate chunks (often 20–50), a **cross-encoder** re-ranker scores each chunk against the original query with full attention over both texts simultaneously. This is more accurate than the initial retrieval but too expensive to run over the entire corpus — so you only apply it to the top candidates. The top 5 re-ranked chunks proceed to the LLM.

**Why it matters before deploy.** Initial retrieval (both vector and BM25) optimizes for recall — casting a wide net. But what the LLM needs is precision: the 3–5 chunks most likely to contain the answer. Without re-ranking, irrelevant chunks sneak into the context window, diluting the signal and increasing hallucination risk. A cross-encoder catches the subtle relevance differences that bi-encoder embeddings miss.

## 4. Context Window Management — Top 3 Chunks Only

**What it means.** After re-ranking, you feed only the top 3 chunks into the LLM's context window — not the full set of retrieved documents. This is a deliberate constraint: less context, more focus.

**Why it matters before deploy.** LLMs degrade when you stuff too much into the context window. Research consistently shows that models attend poorly to information in the middle of long contexts ("lost in the middle" problem). More chunks also means more tokens, which means higher latency and cost per request. Three high-quality, re-ranked chunks give the model a focused, manageable context that produces more accurate and more consistent answers than twenty loosely-relevant paragraphs.

## 5. Data Privacy — PII Scrubbing and Output Filtering

**What it means.** Two filters, one on each side:
- **Input filter (PII scrubber):** Before anything touches the vector store or the LLM, strip personally identifiable information — names, emails, phone numbers, addresses, national IDs. Use pattern matching and NER models to catch them.
- **Output filter (toxicity filter):** Before the response reaches the user, run it through a toxicity/safety classifier to block harmful, biased, or inappropriate content the model might generate.

**Why it matters before deploy.** If PII ends up in your vector store, it can be retrieved and surfaced to other users — a data breach without a hack. If your chatbot generates toxic or biased responses, you have a PR incident and possibly a legal one. These filters are your last line of defense and the easiest ones to forget because they don't affect "happy path" testing. In production, edge cases are the norm.

## 6. Self-Correction — Grounding Verification

**What it means.** After the LLM generates an answer, a verification step checks whether the response is actually supported by the retrieved chunks. This can be a separate LLM call that asks: "Is this answer grounded in the provided context, or does it contain information not present in the sources?" If the answer isn't grounded, it gets flagged, regenerated, or replaced with a fallback.

**Why it matters before deploy.** LLMs hallucinate. Even with perfect retrieval, the model might extrapolate, infer, or invent details that feel plausible but aren't in the source material. A grounding check catches these fabrications before they reach the user. In domains where accuracy matters (legal, medical, financial, support), an ungrounded answer is worse than no answer — it erodes trust permanently.

## 7. Zero Results Handling — Saying "I Don't Know"

**What it means.** When retrieval returns no relevant chunks (or all chunks score below a confidence threshold), the chatbot must respond with a clear "I don't know" or "I don't have information on that" — never attempt to answer from parametric knowledge alone.

**Why it matters before deploy.** The default behavior of most LLMs is to always provide an answer, even when they have no supporting evidence. In a RAG system, this is dangerous: the user trusts the chatbot because it usually cites real documents. If it suddenly fabricates an answer for a topic not in the knowledge base, the user has no way to tell the difference. A strict "I don't know" policy preserves trust and gives you a clear signal (logged zero-result queries) for what content gaps to fill next.

## 8. Performance at Scale — HNSW Indexing

**What it means.** **HNSW** (Hierarchical Navigable Small World) is a graph-based algorithm for approximate nearest neighbor search. It builds a multi-layer graph over your embeddings that enables sub-linear search time — meaning query latency stays low even as your document corpus grows to millions of vectors.

**Why it matters before deploy.** Exact nearest neighbor search is O(n) — it scans every vector on every query. That's fine for 10,000 documents in dev. At 10 million documents in production with concurrent users, exact search becomes a bottleneck that kills latency and saturates compute. HNSW gives you ~95%+ recall at a fraction of the cost, keeping p95 response times under acceptable thresholds even under load. Tune the `ef_construction` and `M` parameters before deploy — they trade index build time and memory for search accuracy.

## 9. Semantic Caching — Skip the LLM for Repeated Questions

**What it means.** Before sending a query through the full RAG pipeline, compute its embedding and check against a cache of recent query embeddings. If a semantically similar query was asked recently (cosine similarity above a threshold), return the cached response directly — no retrieval, no re-ranking, no LLM call.

**Why it matters before deploy.** In production, query distributions follow a power law: a small number of questions account for a large share of traffic. Without caching, every one of those repeated questions burns the full pipeline cost — embedding, search, re-ranking, LLM generation. Semantic caching collapses that to a single similarity check and a cache lookup. The result: lower latency for users, lower cost for you, and reduced load on your LLM provider during traffic spikes. Set a TTL on cached entries so stale answers don't persist after knowledge base updates.

## TL;DR

Before you deploy your chatbot, walk the checklist:

1. **Document chunking** — semantic boundaries with overlap, not arbitrary character splits
2. **Retrieval** — hybrid search combining vector embeddings and BM25 for full coverage
3. **Re-ranking** — cross-encoder scoring the top candidates before anything hits the LLM
4. **Context window** — top 3 chunks only, less noise, more accurate answers
5. **Data privacy** — PII scrubbed on input, toxicity filtered on output
6. **Self-correction** — grounding verification ensures answers come from the context, not imagination
7. **Zero results** — strict "I don't know" policy, never fabricate when retrieval comes up empty
8. **Performance** — HNSW indexing for fast approximate search at scale
9. **Semantic caching** — similar queries served from cache, saving cost and latency

If any item is a "we'll add it post-launch," that's the one your users will notice first.
