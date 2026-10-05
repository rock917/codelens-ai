bash

cat > /mnt/user-data/outputs/README.md << 'ENDOFFILE'
<div align="center">

# 🔍 CodeLens AI

### AI-Powered Developer Intelligence Platform

[![CI](https://github.com/rock917/codelens-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/rock917/codelens-ai/actions/workflows/ci.yml)
[![Backend](https://github.com/rock917/codelens-ai/actions/workflows/backend.yml/badge.svg)](https://github.com/rock917/codelens-ai/actions/workflows/backend.yml)
[![Frontend](https://github.com/rock917/codelens-ai/actions/workflows/frontend.yml/badge.svg)](https://github.com/rock917/codelens-ai/actions/workflows/frontend.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

<br/>

**Upload any repository → Parse → Embed → Chat → Analyze → Generate**

<br/>

[🚀 Live Demo](https://codelens-ai-five.vercel.app) &nbsp;·&nbsp; [📡 API Docs](https://codelens-ai-gd81.onrender.com/docs) &nbsp;·&nbsp; [🐛 Report Bug](https://github.com/rock917/codelens-ai/issues)

<br/>

> ⚡ Backend runs on Render free tier — first request after inactivity may take ~50s to wake up.

</div>

---

## 📌 What is CodeLens AI?

Most "chat with your code" tools just dump your files into ChatGPT. **CodeLens AI is different.**

It implements a production-grade **RAG (Retrieval Augmented Generation)** pipeline that:

- Parses source code using **Python AST** and **regex-based parsers** — understanding functions, classes, and imports at a structural level
- Creates **semantic chunks** that never break a function mid-way
- Generates **384-dimensional embeddings** locally using sentence-transformers — **free, no API key needed**
- Stores vectors in **ChromaDB** for fast cosine-similarity search
- Retrieves only the **5–8 most relevant chunks** out of thousands using hybrid retrieval + multi-signal reranking
- Answers developer questions with **exact file path and line number citations**

> A 100,000 line codebase ≈ 3 million tokens. Sending it all to an LLM is impossible and expensive.
> CodeLens retrieves only what matters — making AI answers fast, accurate, and grounded.

---

## 🌐 Live URLs

| | URL |
|:---|:---|
| 🖥️ **Frontend** | https://codelens-ai-five.vercel.app |
| ⚙️ **Backend API** | https://codelens-ai-gd81.onrender.com |
| 📖 **Swagger Docs** | https://codelens-ai-gd81.onrender.com/docs |

---

## 📸 Screenshots

<table>
<tr>
<td align="center" width="50%">
<img src="docs/screenshots/dashboard.png" alt="Dashboard" width="100%"/>
<b>Dashboard</b><br/>
<sub>Repository statistics, health scores, LOC, chunks, and issue counts</sub>
</td>
<td align="center" width="50%">
<img src="docs/screenshots/analysis.png" alt="Analysis" width="100%"/>
<b>Code Analysis</b><br/>
<sub>Security issues, complexity metrics, code smells, and health score</sub>
</td>
</tr>
</table>

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

**🧠 Repository Intelligence**
- Python AST parsing — exact line numbers, signatures, docstrings
- JS/TS regex-based symbol extraction
- Dependency graph — tracks cross-file imports
- Importance scoring (0–100) per file

**🤖 RAG Pipeline**
- Semantic chunking (AST-boundary aware)
- Local embeddings — `all-MiniLM-L6-v2` (free, no API key)
- ChromaDB vector storage with cosine similarity
- Hybrid retrieval + multi-signal reranking
- Token budget management (max 6000 tokens)

**💬 AI Chat**
- Streaming token-by-token responses (SSE)
- Exact file + line number citations
- Conversation memory for follow-ups
- Full markdown rendering

</td>
<td width="50%" valign="top">

**🛡️ Static Analysis**
- Security: SQL injection, hardcoded secrets, weak crypto
- Complexity: cyclomatic complexity, nesting depth
- Code smells: long functions, too many parameters
- Repository health score (0–100)

**⚡ Smart Summarization**
- Selective: only HIGH importance files (~15%) get LLM summaries
- Background: runs after READY — never blocks the user
- Lazy: LOW importance files summarized on demand
- Saves ~80% of LLM API costs

**🔄 Incremental Indexing**
- MD5 hash per file — only changed files reprocessed
- Stale vector cleanup in ChromaDB
- 10x faster on subsequent re-indexing

</td>
</tr>
</table>

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              React + TypeScript  (Vercel CDN)                │
│   Dashboard  │  Explorer  │  Chat  │  Analysis  │  TestGen   │
└──────────────────────────┬───────────────────────────────────┘
                           │  REST  /  WebSocket  /  SSE
┌──────────────────────────▼───────────────────────────────────┐
│              FastAPI Backend  (Render · Docker)               │
│                                                              │
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────┐  │
│  │ Repository       │  │  RAG Engine    │  │  Analysis   │  │
│  │ Service          │  │                │  │  Engine     │  │
│  │  · AST Parser    │  │  · Retriever   │  │  · Security │  │
│  │  · JS Parser     │  │  · Reranker    │  │  · Complexity│ │
│  │  · Chunker       │  │  · Context     │  │  · Smells   │  │
│  │  · Embeddings    │  │    Builder     │  └─────────────┘  │
│  └──────────────────┘  └────────────────┘                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
┌──────────▼───────────┐   ┌──────────────▼──────────────┐
│  Supabase PostgreSQL │   │     ChromaDB (Vector DB)    │
│                      │   │                             │
│  · repositories      │   │  · 384-dim embeddings       │
│  · files / symbols   │   │  · cosine similarity search │
│  · code_chunks       │   │  · metadata filtering       │
│  · analysis_issues   │   │  · per-repo collections     │
│  · conversations     │   └─────────────────────────────┘
└──────────────────────┘
           │
           ├───────────────────────────────┐
           │                               │
┌──────────▼───────────┐   ┌──────────────▼──────────────┐
│  sentence-transformers│   │       Groq LLM API          │
│  all-MiniLM-L6-v2    │   │                             │
│  GPU (local)         │   │  · LPU fast inference       │
│  CPU (Render)        │   │  · Streaming SSE responses  │
│  384-dim · Free      │   │  · 30s timeout per request  │
└──────────────────────┘   └─────────────────────────────┘
```

---

## 🔬 RAG Pipeline

```
User question: "How does authentication work?"
        │
        ▼
[1] EMBED QUESTION
    sentence-transformers → 384-dim vector
        │
        ▼
[2] VECTOR SEARCH
    ChromaDB cosine similarity → top 30 candidates
        │
        ▼
[3] HYBRID BOOST
    Add keyword matches + symbol name matches
        │
        ▼
[4] MULTI-SIGNAL RERANKING
    · Vector similarity score
    · Keyword overlap bonus
    · Symbol name match bonus
    · File path match bonus
    → Top 8 chunks selected
        │
        ▼
[5] TOKEN BUDGET
    Max 6000 tokens — drop lowest-value chunks if over limit
        │
        ▼
[6] GROQ LLM  (streaming)
    System prompt + code context + question → SSE response
        │
        ▼
[7] GROUNDED ANSWER
    Answer text + file path + symbol name + line numbers
```

---

## 🗂️ Ingestion Pipeline

```
ZIP upload  /  GitHub URL
        │
        ▼  status: UPLOADING
[1] FILE FILTER
    Skip: node_modules · .git · binary files · minified JS
        │
        ▼  status: PARSING
[2] PARSERS
    Python  → AST (exact classes, functions, line numbers)
    JS / TS → Regex-based symbol extraction
        │
        ▼  status: INDEXING
[3] CHUNKER + IMPORTANCE SCORER
    Semantic chunks (AST-boundary aware)
    Score each file 0–100  →  HIGH / MEDIUM / LOW
    Save all to PostgreSQL
        │
        ▼  status: ANALYZING
[4] EMBEDDINGS + CHROMADB
    GPU (local RTX 2050)  or  CPU (Render)
    384-dim vectors stored in ChromaDB
        │
        ▼  status: READY ✅
[5] BACKGROUND SUMMARIZER
    Summarize HIGH importance files via Groq
    Runs after READY — never blocks the user
```

---

## 🧬 Importance Scoring

| Signal | Points |
|:---|:---:|
| Entry point file (`main`, `index`, `app`, `server`) | +25 |
| HIGH keyword in path (`auth`, `database`, `api`, `core`) | +30 |
| MEDIUM keyword in path (`service`, `handler`, `utils`) | +15 |
| Incoming dependency count (other files importing this) | 0 → +20 |
| Number of symbols (capped) | 0 → +20 |
| High complexity score | +5 → +10 |

| Score | Level | Action |
|:---:|:---:|:---|
| ≥ 60 | 🔴 **HIGH** | LLM summary generated during indexing |
| ≥ 30 | 🟡 **MEDIUM** | Metadata only |
| < 30 | 🟢 **LOW** | Metadata only — summarized lazily on demand |

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|:---|:---|:---|
| **Frontend** | React 18 + TypeScript + Vite | Fast, type-safe, component-based |
| **Styling** | Tailwind CSS + CSS variables | Dark theme, developer aesthetic |
| **Backend** | Python 3.11 + FastAPI | Async, auto-docs, Pydantic validation |
| **ORM** | SQLAlchemy (async) | Type-safe DB queries, async support |
| **Database** | Supabase PostgreSQL | Persistent, free tier, Singapore region |
| **Vector DB** | ChromaDB | Local, zero infra, cosine similarity |
| **Embeddings** | sentence-transformers (local) | Free, GPU/CPU aware, 384-dim |
| **LLM** | Groq API | 10–20x faster than OpenAI, free tier |
| **Parsing** | Python AST + regex | Language-aware, accurate extraction |
| **Real-time** | WebSockets + SSE | Progress tracking + streaming chat |
| **Containers** | Docker + Docker Compose | Reproducible deployments |
| **CI/CD** | GitHub Actions (3 workflows) | Automated testing on every push |
| **Frontend deploy** | Vercel | Global CDN, auto-deploy on push |
| **Backend deploy** | Render | Docker support, Singapore region |

---

## 📁 Project Structure

```
codelens-ai/
├── backend/
│   ├── main.py                           # FastAPI app · lifespan · CORS
│   ├── requirements.txt                  # CPU-only PyTorch for Render
│   ├── Dockerfile                        # python:3.11-slim + libpq-dev + git
│   ├── .env.example
│   └── app/
│       ├── config/settings.py            # Pydantic settings (env vars)
│       ├── database/base.py              # Async SQLAlchemy + Supabase pooler
│       ├── models/
│       │   ├── repository.py             # Repository · File · Symbol · CodeChunk · AnalysisIssue
│       │   ├── conversation.py           # Conversation · Message
│       │   └── summary.py               # RepositorySummary
│       ├── schemas/
│       │   ├── repository.py             # Pydantic request/response schemas
│       │   └── chat.py
│       ├── api/routes/
│       │   ├── repository.py             # Upload · list · files · reindex · delete
│       │   ├── chat.py                   # SSE streaming chat
│       │   ├── search.py                 # Semantic search
│       │   ├── analysis.py               # Static analysis
│       │   ├── summary.py                # Repository summaries
│       │   ├── generation.py             # Test + doc generation
│       │   ├── symbols.py                # Symbol extraction
│       │   └── websocket.py              # Real-time progress
│       └── services/
│           ├── repository_service.py     # Ingestion pipeline orchestrator
│           ├── file_filter.py            # Skip irrelevant files
│           ├── importance_scorer.py      # File importance 0–100
│           ├── chunker.py                # Semantic chunking (AST-aware)
│           ├── embedding_service.py      # GPU/CPU aware sentence-transformers
│           ├── vector_store.py           # ChromaDB wrapper
│           ├── incremental_indexer.py    # MD5 hash delta indexing
│           ├── summarization_service.py  # Selective LLM summarization
│           ├── test_generator.py         # Unit test generation
│           ├── doc_generator.py          # Documentation generation
│           ├── parser/
│           │   ├── python_parser.py      # Python AST → symbols
│           │   ├── js_parser.py          # JS/TS regex → symbols
│           │   └── parser_factory.py     # Routes file to correct parser
│           ├── rag/
│           │   ├── rag_engine.py         # Main RAG pipeline
│           │   ├── reranker.py           # Multi-signal chunk reranking
│           │   └── context_builder.py    # Token budget management
│           ├── analyzer/
│           │   ├── analysis_engine.py
│           │   ├── complexity_analyzer.py
│           │   ├── security_analyzer.py
│           │   └── smell_analyzer.py
│           └── llm/
│               ├── base.py               # Abstract LLM provider interface
│               └── groq_provider.py      # AsyncGroq with 30s timeout
├── frontend/
│   ├── Dockerfile                        # node:18-alpine → nginx:alpine
│   ├── nginx.conf                        # React Router + API proxy + WebSocket
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                       # BrowserRouter + all routes
│       ├── index.css                     # Dark theme CSS variables
│       ├── services/api.ts               # Axios client + SSE streaming
│       ├── types/index.ts                # TypeScript interfaces
│       ├── components/
│       │   ├── layout/Sidebar.tsx
│       │   ├── layout/TopBar.tsx
│       │   └── ProgressTracker.tsx       # WebSocket live progress
│       └── pages/
│           ├── Dashboard.tsx
│           ├── Repositories.tsx
│           ├── Explorer.tsx
│           ├── Search.tsx
│           ├── Chat.tsx
│           ├── Analysis.tsx
│           ├── TestGen.tsx
│           └── DocsGen.tsx
├── .github/workflows/
│   ├── ci.yml                            # Backend + Frontend combined
│   ├── backend.yml                       # Import checks · parser · chunker tests
│   └── frontend.yml                      # TypeScript check + Vite build
├── render.yaml                           # Render deployment config
├── docker-compose.yml                    # Local Docker setup
└── .gitignore
```

---

## 🚀 Local Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- [Groq API key](https://console.groq.com) — free
- [Supabase account](https://supabase.com) — free PostgreSQL

---

### 1. Clone

```bash
git clone https://github.com/rock917/codelens-ai.git
cd codelens-ai
```

### 2. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your actual values (see below)
```

**`.env` file:**

```env
# Supabase Session Pooler URL
DATABASE_URL=postgresql://postgres.xxxx:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-120b

EMBEDDING_MODEL=all-MiniLM-L6-v2
USE_GPU=false

CHROMA_PERSIST_DIR=./chroma_db
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=100

FRONTEND_URL=http://localhost:5173
SECRET_KEY=your-secret-key-here
```

```bash
uvicorn main:app --reload --port 8000
# ✅ API ready at http://localhost:8000
# 📖 Docs at  http://localhost:8000/docs
```

### 3. Frontend

```bash
cd ../frontend
npm install
```

**`frontend/.env.local`:**

```env
VITE_API_URL=http://localhost:8000
```

```bash
npm run dev
# ✅ UI ready at http://localhost:5173
```

### 4. GPU Acceleration (Optional — NVIDIA only)

```bash
pip uninstall torch -y
pip install torch==2.3.1+cu121 --index-url https://download.pytorch.org/whl/cu121
```

Set `USE_GPU=true` in your local `.env`.

> ⚠️ **Never change `requirements.txt` to CUDA.** Render has no GPU and uses `requirements.txt` directly. Only your local `.env` should have `USE_GPU=true`.

### 5. Docker (All-in-one)

```bash
export GROQ_API_KEY=gsk_your_key_here
export DATABASE_URL=postgresql://...

docker-compose up --build
# ✅ App at http://localhost:3000
```

---

## 📡 API Reference

### Repositories
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/repositories/upload` | Upload ZIP file |
| `POST` | `/repositories/github` | Clone GitHub repository |
| `GET` | `/repositories` | List all repositories |
| `GET` | `/repositories/{id}` | Get repository details |
| `GET` | `/repositories/{id}/status` | Processing status |
| `GET` | `/repositories/{id}/stats` | File · chunk · LOC statistics |
| `GET` | `/repositories/{id}/files` | List files with metadata |
| `GET` | `/repositories/{id}/files/{fid}/content` | Get file source code |
| `POST` | `/repositories/{id}/reindex` | Incremental re-index |
| `DELETE` | `/repositories/{id}` | Delete repository + vectors |

### Chat
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/chat` | Ask question (SSE streaming) |
| `GET` | `/chat/conversations/{repo_id}` | List conversations |
| `GET` | `/chat/history/{conv_id}` | Get conversation history |

### Search & Analysis
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/search` | Semantic code search |
| `POST` | `/analysis/{repo_id}` | Run static analysis |
| `GET` | `/analysis/{repo_id}/issues` | Get issues (filter by severity) |
| `GET` | `/analysis/{repo_id}/summary` | Health score + issue counts |

### Generation
| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/generate/tests` | Generate unit tests |
| `POST` | `/generate/docs` | Generate documentation |
| `GET` | `/generate/symbols/{repo_id}/{fid}` | Get testable symbols |

### Real-time
| Protocol | Endpoint | Description |
|:---|:---|:---|
| `WS` | `/ws/progress/{repo_id}` | Live processing progress |

---

## 🔑 Key Design Decisions

<details>
<summary><b>Why RAG instead of sending the whole repository?</b></summary>

100K lines ≈ 3M tokens. No LLM context window supports that. Even if it did, the cost would be $30–100 per query and answer quality degrades with too much context. RAG retrieves only the 5–8 most relevant chunks — keeping answers fast, accurate, and nearly free.

</details>

<details>
<summary><b>Why semantic chunking instead of fixed-size splitting?</b></summary>

Fixed-size chunking splits at arbitrary character counts — breaking functions mid-way and destroying semantic meaning. AST-based chunking respects function and class boundaries so every chunk is a complete, meaningful unit. This dramatically improves retrieval precision.

</details>

<details>
<summary><b>Why sentence-transformers locally instead of OpenAI Embeddings API?</b></summary>

Zero cost. `all-MiniLM-L6-v2` runs on CPU or GPU, generates 384-dim embeddings, requires no API key, and has no rate limits. For 10,000 chunks that would be ~$1 on OpenAI — completely free with sentence-transformers.

</details>

<details>
<summary><b>Why ChromaDB instead of pgvector?</b></summary>

ChromaDB runs locally with zero infrastructure — no PostgreSQL extension setup, no server. The `vector_store.py` abstraction makes swapping to pgvector for production a one-file change.

</details>

<details>
<summary><b>Why background summarization?</b></summary>

Running LLM summarization during indexing blocked the READY status for 10–20+ minutes on Render's free CPU. Moving it to a background asyncio task with a 5-minute timeout means repos become READY in 2–3 minutes. Users can chat immediately while summaries improve answers in the background.

</details>

<details>
<summary><b>Why Groq instead of OpenAI?</b></summary>

Groq's custom LPU (Language Processing Unit) hardware delivers 10–20x faster inference than OpenAI. The free tier is generous enough for a portfolio project. The `BaseLLMProvider` abstraction makes switching providers a one-file change.

</details>

<details>
<summary><b>Why two databases — PostgreSQL and ChromaDB?</b></summary>

They serve completely different query patterns. PostgreSQL stores structured relational data (repos, files, symbols, analysis issues, chat history) and answers queries like "give me all HIGH importance files in this repo." ChromaDB stores 384-dim vectors and answers semantic similarity queries. Neither can efficiently replace the other.

</details>

---

## ⚠️ Limitations

- Parses **Python, JavaScript, TypeScript** only — extensible via `parser_factory.py`
- GitHub cloning requires **public repositories**
- ChromaDB resets on Render restarts (ephemeral filesystem) — re-upload after restart
- Groq free tier: ~30 requests/minute rate limit
- Render free tier: ~50s cold start after inactivity
- No authentication system (single-user mode)
- Jupyter Notebook (`.ipynb`) not yet supported

---

## 🔮 Roadmap

- [ ] pgvector for persistent vector storage
- [ ] GitHub OAuth authentication
- [ ] Java, Go, Rust, C++ parser support
- [ ] Jupyter Notebook (`.ipynb`) ingestion
- [ ] PR diff analysis — "what changed and why?"
- [ ] Evaluation pipeline with Recall@K metrics
- [ ] Team collaboration with shared repositories
- [ ] VS Code extension

---

## 🎤 Interview Q&A

<details>
<summary><b>Explain your RAG pipeline end to end</b></summary>

The repository is parsed with Python AST (Python files) and a regex-based parser (JS/TS) into semantic chunks that respect function and class boundaries. Each chunk is embedded locally using sentence-transformers (`all-MiniLM-L6-v2`, 384 dimensions) and stored in ChromaDB. On query: the question is embedded, vector search returns top 30 candidates, hybrid boosting adds keyword and symbol name matches, multi-signal reranking selects the top 8 using vector score + keyword overlap + symbol match + path match, a token budget enforces a 6000-token limit, and the final context is sent to Groq with a system prompt that enforces source-grounded answers with exact file and line citations.

</details>

<details>
<summary><b>Why not just send the whole repository to the LLM?</b></summary>

A 100,000 line codebase is approximately 3 million tokens — far exceeding any LLM context window (typically 8K–128K tokens). Even if a model supported it, cost would be $30–100 per question and quality would degrade as the model loses focus with too much context. RAG retrieves only the 5–8 most relevant chunks, keeping cost near zero and answers focused and accurate.

</details>

<details>
<summary><b>How does importance scoring work and why does it save money?</b></summary>

Every file is scored 0–100 using programmatic signals: entry point files get +25, paths containing keywords like auth/database/api get +30, incoming dependency count adds up to +20, symbol count adds up to +20. Files scoring ≥60 are HIGH and get LLM summaries during indexing. Files scoring below 30 are summarized lazily on demand. This reduces LLM API calls by approximately 80% compared to summarizing every file.

</details>

<details>
<summary><b>Why two databases — PostgreSQL and ChromaDB?</b></summary>

They serve completely different query patterns. PostgreSQL stores structured relational data and answers structured queries — "give me all files in this repo with HIGH importance." ChromaDB stores 384-dimensional vectors and answers semantic similarity queries — "find the 30 code chunks most similar to this question." You cannot efficiently do cosine similarity search in standard PostgreSQL, and you cannot do relational joins in ChromaDB. Both are necessary.

</details>

<details>
<summary><b>What is incremental indexing?</b></summary>

At index time, an MD5 hash is stored per file. On re-index, the current file hash is compared with the stored hash. Only changed files are re-parsed, re-chunked, and re-embedded. Old ChromaDB vectors for changed files are deleted first. Unchanged files are completely skipped — making subsequent re-indexing approximately 10x faster on large repositories.

</details>

---

## 👨‍💻 Author

**Bobby Ahirwar**
B.Tech Chemical Engineering — IIT Hyderabad (Graduating 2027)

This project demonstrates:

| Area | What was built |
|:---|:---|
| **AI/ML Engineering** | RAG pipeline, embeddings, vector search, LLM integration |
| **Backend Engineering** | Async Python, FastAPI, WebSockets, SSE streaming |
| **Frontend Engineering** | React, TypeScript, real-time UI with streaming |
| **Database Design** | Relational (PostgreSQL) + vector (ChromaDB) dual-database architecture |
| **Production Engineering** | Docker, GitHub Actions CI/CD, GPU/CPU optimization, cloud deployment |

---

## 📄 License

[MIT](LICENSE) © 2026 Bobby Ahirwar