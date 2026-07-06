# AEO Failure-Mode Mapping: What GraphRAG Teaches Us About Answer Engine Optimization

**Status:** Working draft — base material for a follow-up article.
**Source project:** [`graphrag-demo/`](../) — a Neo4j + LangGraph + Bedrock GraphRAG pipeline built as a teaching artifact.

## Thesis

A GraphRAG pipeline and an AI answer engine (ChatGPT browsing, Perplexity, Google AI Overviews, Bing Copilot) do structurally the same job: **extract entities from a query, retrieve facts about those entities from a knowledge source, judge whether the facts are sufficient, then write a grounded answer.** The GraphRAG pipeline just makes every step explicit and inspectable — you can watch it fail.

That means every failure mode we can trigger and observe in `graphrag-demo` is a working model of a failure mode that happens invisibly when an answer engine tries to read a website. This document catalogs those mappings, each backed by an actual reproduced failure from the demo, not a hypothetical.

## The Core Mapping

| GraphRAG pipeline stage | What it does | Website / AEO equivalent | Failure mode |
|---|---|---|---|
| `extract_entities` | LLM pulls entity names from the question | A user's search query, or an answer engine's internal query rewriting | Query and source vocabulary don't match |
| `traverse_graph` (Cypher `MATCH`) | Exact-match lookup of entity names against graph node properties | Answer engine's retrieval/crawl step finding content on your site | Content uses different terminology than what's searched for → zero results |
| Triple formatting (`A --REL--> B`) | Facts are compressed into short, explicit subject-predicate-object statements | How your page presents a fact (prose vs. structured markup) | Verbose or implicit prose is expensive and unreliable for a model to parse |
| `check_sufficiency` | LLM judges if retrieved facts answer the question | An answer engine deciding whether to cite your page or look elsewhere / hedge | A page that *has* the answer but doesn't state it plainly reads as "insufficient" |
| Hop budget (`hops >= 2`) | Caps how many retrieval rounds are allowed before forcing an answer | Crawl depth / how many clicks deep an answer engine will go to find something | Answers buried too deep (or behind JS-only navigation) never get reached |
| `generate_answer` | LLM writes prose, told to cite only retrieved facts | The final answer engine output shown to a user, ideally with a citation to your page | Ungrounded generation = hallucination; the graph prevents this by construction |

## Failure Mode 1 — Entity / Vocabulary Mismatch

**What happened in the demo:**

The graph has a node `Feature {name: 'Multi-Region'}`. Asking:

```
python main.py "Which plan do I need for Multi-Region support?"
```

produced:

```
🔍 Extracted entities: ['plan', 'Multi-Region support']
📊 Retrieved 0 facts
```

The LLM extracted `"Multi-Region support"` — a perfectly reasonable paraphrase of the question — but the Cypher query does an **exact string match** (`WHERE e.name IN $names`) against the graph's stored node name, `"Multi-Region"`. The extra word broke the match completely. Zero facts retrieved, and the model was left generating a non-answer from nothing.

Rephrasing to match the graph's exact vocabulary (`"Which plan do I need for Multi-Region?"`) fixes it instantly — the underlying data didn't change, only whether the query happened to line up with how it was named.

**The AEO equivalent:** an answer engine trying to find "does this product support multi-region deployment" runs into the same wall if your site names the feature something like "Global Availability Zones" without ever using the phrase a user (or the model's own query rewriting) would reach for. The content exists. It just isn't reachable at the vocabulary layer.

**Practical fix for websites:**
- State the feature/concept using the terms your audience actually searches with, not just internal product naming.
- Where naming has to be different (marketing name vs. technical name), say both explicitly on the same page: *"Global Availability Zones (multi-region support) lets you..."*
- Keep terminology **consistent across every page** that mentions the same concept — pricing page, docs, FAQ. An answer engine assembling an answer from multiple pages needs the names to line up, exactly like the Cypher `MATCH` does.

## Failure Mode 2 — Implicit vs. Explicit Facts

**What happened in the demo:**

When facts *are* retrieved successfully, they arrive as tight triples:

```
Hybrid Search --IMPLEMENTED_BY -> REQUIRES--> Team (price: 99 USD)
```

This is what makes `generate_answer` reliable — the fact is unambiguous, self-contained, and cheap to reason over. Compare that to how the same fact might appear in unstructured prose: *"Advanced retrieval capabilities are part of our growth-oriented offering."* A human skimming a pricing page might parse that as "Hybrid Search needs the Team plan." A model doing exact retrieval over vague prose has no such guarantee — it has to infer, and inference is where hallucination risk lives.

**The AEO equivalent:** a page that states pricing/feature relationships as marketing prose forces the answer engine to infer a fact it should have been told directly. Inference is unreliable and, more importantly, **uncitable** — a model that had to guess won't (and shouldn't) attribute the guess to your page with confidence.

**Practical fix for websites:**
- State the fact once, plainly, near the top of the relevant section: *"Hybrid Search requires the Team plan ($99/mo) or higher."*
- Use structured data (`schema.org/Product`, `Offer`, `FAQPage`) to encode the same fact machine-readably — this is the direct analogue of a graph triple living in your page's `<head>`.
- Tables beat paragraphs for anything comparative (plan/feature matrices) — a table row is already close to a triple.

## Failure Mode 3 — False Confidence in Sufficiency Judgment

**What happened in the demo:**

The original guide code checked sufficiency like this:

```python
return "generate" if "SUFFICIENT" in verdict else "traverse"
```

`"SUFFICIENT"` is a substring of `"INSUFFICIENT"`. Every time the model correctly said *"INSUFFICIENT"*, the code matched the substring and treated it as *sufficient* anyway — silently skipping the retry loop and generating from incomplete facts regardless. The pipeline never crashed and never surfaced an error; it just quietly proceeded with confidence it hadn't earned. (Fixed in this repo — see [Design Notes](../README.md#design-notes--known-quirks) — but the failure mode is the interesting part.)

**The AEO equivalent:** this is the machine-reasoning version of an answer engine over-trusting a thin or tangential page. If a page technically *mentions* a topic without actually answering the question, a shallow relevance signal (keyword overlap, title match) can cause a model to treat "mentions the topic" as "answers the question" — and it will generate/cite with the same unearned confidence the buggy substring check had. There's no error message when this happens on a live answer engine; the answer just quietly ships slightly wrong, cited to a page that didn't really support it.

**Practical fix for websites:**
- Don't let a page merely *reference* an answer — state it. A page titled "Multi-Region Support" that only says "available on select plans" without naming which plan is the prose equivalent of the substring bug: technically on-topic, not actually sufficient.
- FAQ-style direct Q→A pairs reduce the surface area for this failure, because the "is this sufficient" judgment becomes close to trivial for the model.

## Failure Mode 4 — Retrieval Depth Limits

**What happened in the demo:**

`traverse_graph`'s Cypher already expands `[r*1..2]` — up to two relationship hops — in a single call. The `hops >= 2` counter in `pipeline.py` caps how many times the *whole node* can re-run before the pipeline is forced to answer with whatever it has, regardless of the sufficiency verdict. It's a safety valve against infinite loops, not a mechanism for going deeper.

**The AEO equivalent:** every crawler and retrieval system has a depth/budget limit — how many links deep it will follow, how many pages it will fetch, how much of a page it will read before giving up. Content that requires following three clicks from the entry point to reach the actual answer (buried in a PDF linked from a linked page, for instance) is content that will get "hop-budget capped" before an answer engine ever reaches it, and it will answer from whatever shallower, weaker information it already had.

**Practical fix for websites:**
- Put the answer within one hop of where a user (or crawler) would plausibly land — don't make critical facts reachable only through deep navigation chains.
- Avoid gating key facts behind JS-rendered interactions (accordions that only populate on click, chat-only pricing) that a crawler's retrieval budget won't spend time waiting on.

## Summary Checklist

Derived directly from the four failure modes above — apply this to any page you want an answer engine to read accurately:

- [ ] Does the page use the same terminology a user would actually search with, consistently across every page that touches the same concept?
- [ ] Is every important fact stated as an explicit, standalone sentence (or table row / structured-data field), not implied by surrounding marketing prose?
- [ ] Does the page directly answer the question it's about, rather than merely mentioning the topic?
- [ ] Is the answer reachable within one hop of a natural entry point, without requiring JS interaction or deep navigation?

## Methodology Note

Every failure mode above was reproduced live against a real (if small) knowledge graph and a real LLM (Amazon Nova Pro via Bedrock) — not simulated. The commands and outputs are captured verbatim from the working `graphrag-demo` project in this repo, so they can be re-run and re-verified rather than taken on faith.

## Next Steps for the Follow-Up Article

1. Expand each failure mode with a **before/after page rewrite example** (a fictional AcmeGraph docs page, rewritten to fix the mapped issue).
2. Add a fifth mapping once the demo is extended with a hybrid retrieval layer (per the original guide's "Extend for the follow-up article" section) — vocabulary mismatch is exactly what embedding-based fallback retrieval is meant to catch, which the pure-Cypher approach here cannot.
3. Screenshot the Neo4j Browser traversal next to the equivalent "if this were a webpage" mockup, side by side, for the visual explainer.
