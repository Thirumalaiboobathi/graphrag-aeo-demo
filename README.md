# GraphRAG Demo — AcmeGraph

A local, working GraphRAG system: ask a question in plain English and get an answer grounded in a Neo4j knowledge graph, orchestrated by LangGraph, and written by an LLM on Amazon Bedrock. Every claim in the final answer traces back to a real graph fact — nothing is inferred or hallucinated.

> Ask *"Can I use Hybrid Search on the free Starter plan?"* and get back a direct, cited answer pulled from an actual Cypher traversal — not a guess.

**Companion article:** [Beyond SEO: AI-Agent-Readable Sites with Graphs and llms.txt](https://builder.aws.com/content/3G4x0sjXzKGRGdljxp19pwSmtGX/beyond-seo-ai-agent-readable-sites-with-graphs-and-llmstxt) (AWS Builder Center) — this repo is the **reasoning simulator** companion to that article, reproducing what an AI answer engine does under the hood. See also [docs/AEO-mapping.md](docs/AEO-mapping.md) for a detailed mapping between the failure modes reproduced here and real-world Answer Engine Optimization (AEO) issues, written as base material for a follow-up piece.

## Table of Contents

- [Why This Exists](#why-this-exists)
- [How This Connects to AEO](#how-this-connects-to-aeo)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Data Model](#data-model)
- [Usage](#usage)
- [Verifying the Graph Manually](#verifying-the-graph-manually)
- [Troubleshooting](#troubleshooting)
- [Design Notes & Known Quirks](#design-notes--known-quirks)
- [Key Takeaways](#key-takeaways)

## Why This Exists

This demo is not a website AEO tool — it's a **reasoning simulator**. It reproduces what happens inside an AI answer engine when it retrieves and connects facts, so you can see firsthand why structured content (knowledge graphs, Schema.org, llms.txt) leads to better AI answers than unstructured prose. Your website is the input. GPT is the pipeline. This demo shows you what that pipeline is actually doing under the hood.

Most "RAG" demos retrieve chunks of text and hope the LLM stitches them together correctly. This demo retrieves **structured facts** from a knowledge graph instead — so multi-hop questions ("does the cheapest plan that unlocks Feature X also happen to be the cheapest plan overall?") get answered deterministically by Cypher, and the LLM's only job is to read facts and write prose. The graph reasons; the model writes.

## How This Connects to AEO

| Dimension | AEO (real websites) | This Demo (local graph) |
|---|---|---|
| What the AI sees | Website HTML, JSON-LD, text | Neo4j graph nodes and edges |
| What the AI does | Extract entities, connect facts, generate answer | Extract entities, traverse graph, generate answer |
| What breaks it | Vague content, inconsistent naming, JS-only pages | Vague queries, mismatched entity names, missing nodes |
| Failure result | Not cited or hallucinated in AI answers | 0 facts retrieved or wrong answer generated |

***AEO tells you WHAT to build. This demo shows you WHY it works.***

## Architecture

```
                ┌─────────────┐
   question --> │   extract   │  LLM pulls entity names from the question
                └──────┬──────┘
                       │
                       v
                ┌─────────────┐
          ┌---> │  traverse   │  Cypher query walks 1-2 hops from entities
          │     └──────┬──────┘
          │            │
          │            v
          │     ┌─────────────┐
          └---- │ sufficient? │  LLM judges if facts answer the question
   (insufficient,└──────┬──────┘
    hops < 2)           │ sufficient (or hops >= 2)
                         v
                  ┌─────────────┐
                  │  generate   │  LLM writes the answer, citing only graph facts
                  └──────┬──────┘
                         │
                         v
                      answer
```

**Flow:** `extract` (LLM: question → entity names) → `traverse` (Cypher: entities → 1-2 hop facts) → `sufficient?` (LLM judges, loops back to `traverse` if not, capped at 2 hops) → `generate` (LLM: facts → cited answer).

## Tech Stack

| Layer | Choice |
|---|---|
| Graph database | Neo4j 5.20 Community (Docker) |
| Orchestration | LangGraph |
| LLM provider | Amazon Bedrock (`langchain-aws`) |
| Language | Python 3.10+ |
| Config | `python-dotenv` |

## Project Structure

```
graphrag-demo/
├── docker-compose.yml     # Neo4j Community container
├── requirements.txt       # Python dependencies
├── .env.example            # Environment variable template
├── README.md
├── data/                  # (reserved for future data files)
└── src/
    ├── __init__.py
    ├── load_graph.py      # Seeds the AcmeGraph sample dataset
    ├── pipeline.py        # LangGraph state machine: extract → traverse → check → generate
    └── main.py            # CLI entry point
```

## Prerequisites

- Docker Desktop, installed and running
- Python 3.10+
- AWS credentials configured (`aws configure`) with **Bedrock model access enabled** for at least one model (see [Troubleshooting](#troubleshooting) — access is not automatic even with valid credentials)
- ~2GB free disk space

## Setup

```bash
# 1. Start Neo4j
docker-compose up -d
# wait ~30-60s for it to finish initializing — check with: docker logs graphrag-neo4j

# 2. Create a virtual environment and install dependencies
python -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\Activate.ps1    # Windows PowerShell
# venv\Scripts\activate.bat    # Windows cmd.exe
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# edit .env: confirm the Neo4j credentials and set BEDROCK_MODEL_ID to a model
# your AWS account actually has access to (see Troubleshooting)

# 4. Load the sample AcmeGraph data
python src/load_graph.py
# expect: "✅ Loaded 10 nodes into the graph"

# 5. Ask a question
cd src
python main.py "Can I use Hybrid Search on the free Starter plan?"
```

**Windows note:** if `Activate.ps1` throws a script-execution error, run once (per user, no admin needed):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Your prompt should show `(venv)` once activation succeeds — if it doesn't, `python` is still resolving to the global interpreter and imports will fail.

## Data Model

A fictional product, **AcmeGraph**, modeled as a small graph:

| Node | Examples |
|---|---|
| `Product` | AcmeGraph |
| `Plan` | Starter ($0), Team ($99), Enterprise ($499) |
| `Feature` | Vector Index, Hybrid Search, Multi-Region |
| `Tool` | LangGraph |
| `Doc` | Hybrid Search Guide, Plans and Pricing |

Key relationships: `HAS_FEATURE`, `IMPLEMENTED_BY`, `REQUIRES`, `DOCUMENTED_IN`, `INTEGRATES_WITH`.

## Usage

```bash
python main.py "Can I use Hybrid Search on the free Starter plan?"
python main.py "What features does AcmeGraph offer and what do they cost?"
python main.py "Does AcmeGraph integrate with LangGraph?"
python main.py "Which plan do I need for Multi-Region?"
```

**Verified example output:**

```
❓ Question: Can I use Hybrid Search on the free Starter plan?
────────────────────────────────────────────────────────────
🔍 Extracted entities: ['Hybrid Search', 'Starter']
📊 Retrieved 8 facts
🧠 Sufficiency: INSUFFICIENT
📊 Retrieved 8 facts
────────────────────────────────────────────────────────────

✅ Answer:
No, you cannot use Hybrid Search on the free Starter plan. According to the
facts, Hybrid Search requires the Team plan, which costs 99 USD.

Relevant facts:
- Hybrid Search --IMPLEMENTED_BY -> REQUIRES--> Team (price: 99 USD)
```

Note: entity extraction quality is what makes or breaks a query. Phrasing that doesn't match a graph node's exact name (e.g. "Multi-Region support" instead of "Multi-Region") returns zero facts. This is a property of the demo, not a bug — see [Key Takeaways](#key-takeaways).

## Verifying the Graph Manually

Open the Neo4j Browser at http://localhost:7474 (login `neo4j` / `password123`) and run:

```cypher
MATCH (n) RETURN n
```

Multi-hop reasoning example — does the plan required for Hybrid Search actually beat the cheapest plan overall?

```cypher
MATCH (hs:Feature {name: 'Hybrid Search'})
      -[:IMPLEMENTED_BY*0..2]->(:Feature)
      -[:REQUIRES]->(required:Plan)
MATCH (cheapest:Plan)
WITH required, cheapest ORDER BY cheapest.price ASC LIMIT 1
RETURN required.name  AS requiredPlan,
       required.price AS requiredPrice,
       cheapest.name  AS cheapestPlan,
       cheapest.price AS cheapestPrice,
       required.price <= cheapest.price AS worksOnCheapest;
```

Expected: `Team | 99 | Starter | 0 | false` — one deterministic query answers what would otherwise take several LLM round-trips to reason about.

## Troubleshooting

**Neo4j won't start:**
```bash
docker-compose down
docker-compose up -d
docker logs graphrag-neo4j
```

**Connection refused on port 7687:** wait 30–60 seconds after `docker-compose up -d`; confirm the container is actually up with `docker ps`.

**`ModuleNotFoundError: No module named 'neo4j'` (or similar):** the venv isn't active in your current shell. On Windows, `activate.bat` only works in `cmd.exe`; if you're in PowerShell (`PS C:\...>` prompt) you need `.\venv\Scripts\Activate.ps1` instead — running the wrong one silently no-ops.

**`pip install` fails trying to compile `numpy` from source (`meson... NumPy requires GCC >= 8.4`):** this happens on newer Python versions (3.13+) if a pinned dependency forces `numpy<2.0`, which has no prebuilt wheel for that interpreter. Fix: use recent versions of `langgraph`/`langchain-aws` (already reflected in `requirements.txt`) — they support `numpy>=2`, which ships wheels for current Python versions.

**Bedrock `AccessDeniedException` / `ResourceNotFoundException` ("Model use case details have not been submitted"):** having valid AWS credentials is not the same as having Bedrock model access. Fix:
1. AWS Console → Bedrock → **Model access** → request/enable access for the model you want (this can take a few minutes to propagate, sometimes longer for Anthropic models specifically, which require a separate use-case form).
2. In the meantime, Amazon's own **Nova** models (e.g. `amazon.nova-pro-v1:0`) are often enabled by default and work with the same `ChatBedrock` client — just change `BEDROCK_MODEL_ID` in `.env`.
3. If you have Anthropic API access instead of Bedrock, swap the client in `src/pipeline.py`:
   ```python
   from langchain_anthropic import ChatAnthropic
   llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0)
   ```
   and add `ANTHROPIC_API_KEY` to `.env`.

**Entity extraction returns garbage or misses entities:** temperature is already pinned to 0; tighten the prompt in `extract_entities` (`src/pipeline.py`), or normalize/alias entity names before querying if your model's phrasing doesn't match the graph's exact node names.

## Design Notes & Known Quirks

- `traverse_graph`'s Cypher already expands `[r*1..2]` (up to 2 hops) in a single query, so a second traversal call on the same entities typically doesn't surface new facts — the "hop budget" mainly guards against infinite loops on a stubborn `INSUFFICIENT` verdict, not against actually deepening the search.
- Facts collected across hops aren't deduplicated against each other (only within a single traversal call), so the same fact can appear twice in a multi-hop answer's citation list. Cosmetic, not a correctness issue.

## Key Takeaways

1. **The graph does the reasoning, the LLM does the writing.** Every fact in the final answer comes from a Cypher query — nothing is inferred.
2. **Entity extraction quality determines everything downstream.** Bad or mismatched entity names mean empty traversals and no answer — the single most common failure mode of this whole approach.
3. **Hop budgets matter.** Without a bail-out condition, a persistently "insufficient" verdict can loop forever.
4. **Triples beat raw JSON.** Formatting graph results as `A --REL--> B` (instead of verbose Cypher JSON) is what the LLM reads well and cheaply.
5. **This scales down beautifully.** The same code runs on Neo4j Community locally and Amazon Neptune in production — Cypher is portable.
6. **The failure modes here mirror real AEO failures.** When entity extraction misses a node in this demo, it's the same mechanism that causes GPT to miss your product on a poorly-structured website — inconsistent naming, unclear entities, unlinked facts. Fix them in the graph and you understand how to fix them on a real site.
