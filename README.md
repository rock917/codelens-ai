<div align="center"> 
🔍 CodeLens AI
AI-Powered Developer Intelligence Platform
CI Backend Frontend License: MIT Python React FastAPI
  <br/> 
Upload any repository → Parse → Embed → Chat → Analyze → Generate
  <br/> 
🚀 Live Demo · 📡 API Docs · 🐛 Report Bug
  <br/> 
⚡ Backend on Render free tier — first request after inactivity takes ~50s to wake up

  </div> 
📌 What is CodeLens AI?
Most "chat with your code" tools just dump your files into ChatGPT. CodeLens AI is different.
It implements a production-grade RAG (Retrieval Augmented Generation) pipeline that:
- Parses source code using Python AST and Tree-sitter — understanding functions, classes, and imports
- Creates semantic chunks that never break a function mid-way
- Generates 384-dimensional embeddings locally using sentence-transformers
- Stores vectors in ChromaDB for lightning-fast semantic search
- Retrieves only the 5-8 most relevant chunks out of thousands using hybrid retrieval + multi-signal reranking
- Answers developer questions with exact file and line number citations
A 100,000 line codebase ≈ 3 million tokens. Sending it all to an LLM is impossible and expensive.
 CodeLens retrieves only what matters — making AI answers fast, accurate, and grounded.

🌐 Live URLs
	URL
🖥️ Frontend	https://codelens-ai-five.vercel.app
⚙️ Backend API	https://codelens-ai-gd81.onrender.com
📖 Swagger Docs	https://codelens-ai-gd81.onrender.com/docs


✨ Feature Overview
  <table> <tr> <td width="50%"> 
🧠 Repository Intelligence
- Python AST parsing — exact line numbers, signatures, docstrings
- JS/TS regex-based symbol extraction
- Dependency graph — tracks cross-file imports
- Importance scoring (0–100) per file
🤖 RAG Pipeline
- Semantic chunking (AST-boundary aware)
- Local embeddings — all-MiniLM-L6-v2 (free, no API key)
- ChromaDB vector storage with cosine similarity
- Hybrid retrieval + multi-signal reranking
- Token budget management (max 6000 tokens)
💬 AI Chat
- Streaming token-by-token responses (SSE)
- Exact file + line number citations
- Conversation memory for follow-ups
- Full markdown rendering
  </td> <td width="50%"> 
🛡️ Static Analysis
- Security: SQL injection, hardcoded secrets, weak crypto
- Complexity: cyclomatic complexity, nesting depth
- Code smells: long functions, too many parameters
- Repository health score (0–100)
⚡ Smart Summarization
- Selective: only HIGH importance files (~15%) get LLM summaries
- Background: runs after READY — never blocks the user
- Lazy: LOW importance files summarized on demand
- Saves ~80% of LLM API costs
🔄 Incremental Indexing
- MD5 hash per file — only changed files reprocessed
- Stale vector cleanup in ChromaDB
- 10x faster on subsequent re-indexing
  </td> </tr> </table> 
📸 Screenshots
🏠 Dashboard
<img src="docs/screenshots/dashboard.png" alt="CodeLens AI Dashboard" width="100%">

💬 AI Chat
<img src="docs/screenshots/chat.png" alt="CodeLens AI Chat" width="100%">

🔍 Code Analysis
<img src="docs/screenshots/analysis.png" alt="CodeLens AI Analysis" width="100%">

🏗️ System Architecture
┌────────────────────────────────────────────────────────────────────┐
│                    React + TypeScript (Vercel)                      │
│   Dashboard  │  Explorer  │  Search  │  Chat  │  Analysis  │  Gen  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  REST API  /  WebSocket  /  SSE
┌──────────────────────────────▼─────────────────────────────────────┐
│                      FastAPI Backend (Render + Docker)              │
│                                                                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Repository      │  │   RAG Engine     │  │ Analysis Engine  │  │
│  │ Service         │  │                  │  │                  │  │
│  │ ┌─────────────┐ │  │ ┌────────────┐  │  │ ┌────────────┐  │  │
│  │ │ AST Parser  │ │  │ │ Retriever  │  │  │ │ Security   │  │  │
│  │ │ JS Parser   │ │  │ │ Reranker   │  │  │ │ Complexity │  │  │
│  │ │ Chunker     │ │  │ │ Context    │  │  │ │ Smells     │  │  │
│  │ │ Embeddings  │ │  │ │ Builder    │  │  │ └────────────┘  │  │
│  │ └─────────────┘ │  │ └────────────┘  │  └──────────────────┘  │
│  └─────────────────┘  └──────────────────┘                        │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
              ┌────────────────┴──────────────────┐
              │                                   │
┌─────────────▼──────────────┐   ┌───────────────▼───────────────┐
│   Supabase PostgreSQL      │   │      ChromaDB (Vector DB)     │
│                            │   │                               │
│  repositories              │   │  384-dim embeddings           │
│  files / symbols           │   │  cosine similarity search     │
│  code_chunks               │   │  metadata filtering           │
│  analysis_issues           │   │  per-repository collections   │
│  conversations / messages  │   └───────────────────────────────┘
└────────────────────────────┘
                               │
              ┌────────────────┴──────────────────┐
              │                                   │
┌─────────────▼──────────────┐   ┌───────────────▼───────────────┐
│  sentence-transformers     │   │         Groq LLM API          │
│  all-MiniLM-L6-v2          │   │                               │
│  GPU (local) / CPU (Render)│   │  Fast inference (LPU chip)    │
│  384-dim vectors           │   │  Streaming responses          │
│  Free, no API key          │   │  30s timeout per request      │
└────────────────────────────┘   └───────────────────────────────┘
🔬 RAG Pipeline — Step by Step
User asks: "How does authentication work?"
              │
              ▼
  ┌───────────────────────┐
  │   1. EMBED QUESTION   │  sentence-transformers → 384-dim vector
  └───────────┬───────────┘
              │
              ▼
  ┌───────────────────────┐
  │  2. VECTOR SEARCH     │  ChromaDB cosine similarity → top 30 candidates
  └───────────┬───────────┘
              │
              ▼
  ┌───────────────────────┐
  │  3. HYBRID BOOST      │  Keyword matches + symbol name matches added
  └───────────┬───────────┘
              │
              ▼
  ┌───────────────────────┐
  │  4. MULTI-SIGNAL      │  Vector score + keyword overlap +
  │     RERANKING         │  symbol name match + file path match
  │                       │  → Top 8 selected
  └───────────┬───────────┘
              │
              ▼
  ┌───────────────────────┐
  │  5. TOKEN BUDGET      │  Max 6000 tokens — drop low-value chunks
  └───────────┬───────────┘
              │
              ▼
  ┌───────────────────────┐
  │  6. GROQ LLM          │  System prompt + context + question
  │     STREAMING         │  → SSE token-by-token response
  └───────────┬───────────┘
              │
              ▼
  ┌───────────────────────┐
  │  7. GROUNDED ANSWER   │  Answer + file path + symbol + line numbers
  └───────────────────────┘
🗂️ Ingestion Pipeline
  ZIP / GitHub URL
        │
        ▼
  ┌─────────────┐     status: UPLOADING
  │ File Filter │  →  Skip node_modules, .git, binary, minified
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     status: PARSING
  │   Parsers   │  →  Python AST / JS regex
  │             │     Extract: classes, functions, imports,
  │             │     line numbers, complexity
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     status: INDEXING
  │  Chunker +  │  →  Semantic chunks (AST-boundary aware)
  │  Importance │     Score each file 0-100
  │  Scorer     │     Save to PostgreSQL
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     status: ANALYZING
  │  Embeddings │  →  GPU (local) or CPU (Render)
  │  + ChromaDB │     384-dim vectors stored in ChromaDB
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     status: READY ✅
  │ Background  │  →  Summarize HIGH importance files
  │ Summarizer  │     (doesn't block the user)
  └─────────────┘
🧬 Importance Scoring
Signal	Points
Entry point file (main, index, app, server)	+25
HIGH keyword in path (auth, database, api, core)	+30
MEDIUM keyword in path (service, handler, utils)	+15
Number of dependent files (other files importing this)	+0 to +20
Number of symbols (capped at 20 points)	+0 to +20
High complexity score	+5 to +10


Score	Level	Action
≥ 60	HIGH 🔴	LLM summary generated during indexing
≥ 30	MEDIUM 🟡	Metadata only
< 30	LOW 🟢	Metadata only, summarized lazily on demand


🛠️ Tech Stack
Layer	Technology	Reason
Frontend	React 18 + TypeScript + Vite	Fast, type-safe, component-based
Styling	Tailwind CSS + Custom CSS vars	Dark theme, developer aesthetic
Backend	Python 3.11 + FastAPI	Async, auto-docs, Pydantic validation
ORM	SQLAlchemy (async)	Type-safe DB queries, async support
Database	Supabase PostgreSQL	Persistent, free tier, Singapore region
Vector DB	ChromaDB	Local, zero infra, cosine similarity
Embeddings	sentence-transformers (local)	Free, GPU/CPU aware, 384-dim
LLM	Groq API	10-20x faster than OpenAI, free tier
Parsing	Python AST + regex	Language-aware, accurate extraction
Real-time	WebSockets + SSE	Progress tracking + streaming chat
Containers	Docker + Docker Compose	Reproducible deployments
CI/CD	GitHub Actions (3 workflows)	Automated testing on every push
Deploy: Frontend	Vercel	Global CDN, auto-deploy
Deploy: Backend	Render	Docker support, Singapore region


📁 Project Structure
codelens-ai/
├── backend/
│   ├── main.py                          # FastAPI app + lifespan + CORS
│   ├── requirements.txt                 # CPU-only PyTorch for Render
│   ├── Dockerfile                       # Python 3.11-slim + libpq-dev
│   ├── .env.example
│   └── app/
│       ├── config/settings.py           # Pydantic settings (env vars)
│       ├── database/base.py             # Async SQLAlchemy + Supabase pooler
│       ├── models/
│       │   ├── repository.py            # Repository, File, Symbol, CodeChunk, AnalysisIssue
│       │   ├── conversation.py          # Conversation, Message
│       │   └── summary.py              # RepositorySummary
│       ├── schemas/
│       │   ├── repository.py            # Pydantic request/response schemas
│       │   └── chat.py
│       ├── api/routes/
│       │   ├── repository.py            # Upload, list, files, reindex, delete
│       │   ├── chat.py                  # SSE streaming chat
│       │   ├── search.py               # Semantic search
│       │   ├── analysis.py             # Static analysis
│       │   ├── summary.py              # Repository summaries
│       │   ├── generation.py           # Test + doc generation
│       │   ├── symbols.py              # Symbol extraction
│       │   └── websocket.py            # Real-time progress
│       └── services/
│           ├── repository_service.py    # Ingestion pipeline orchestrator
│           ├── file_filter.py          # Skip irrelevant files
│           ├── importance_scorer.py    # File importance 0-100
│           ├── chunker.py              # Semantic chunking (AST-aware)
│           ├── embedding_service.py    # GPU/CPU aware sentence-transformers
│           ├── vector_store.py         # ChromaDB wrapper
│           ├── incremental_indexer.py  # MD5 hash delta indexing
│           ├── summarization_service.py # Selective LLM summarization
│           ├── test_generator.py       # Unit test generation
│           ├── doc_generator.py        # Documentation generation
│           ├── parser/
│           │   ├── python_parser.py    # Python AST → symbols
│           │   ├── js_parser.py        # JS/TS regex → symbols
│           │   └── parser_factory.py   # Routes file to correct parser
│           ├── rag/
│           │   ├── rag_engine.py       # Main RAG pipeline
│           │   ├── reranker.py         # Multi-signal chunk reranking
│           │   └── context_builder.py  # Token budget management
│           ├── analyzer/
│           │   ├── analysis_engine.py
│           │   ├── complexity_analyzer.py
│           │   ├── security_analyzer.py
│           │   └── smell_analyzer.py
│           └── llm/
│               ├── base.py             # Abstract LLM provider
│               └── groq_provider.py    # AsyncGroq with 30s timeout
├── frontend/
│   ├── Dockerfile                       # Node 18 → nginx:alpine
│   ├── nginx.conf                       # React Router + API proxy
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                      # BrowserRouter + all routes
│       ├── index.css                    # Dark theme CSS variables
│       ├── services/api.ts              # Axios client + SSE streaming
│       ├── types/index.ts               # TypeScript interfaces
│       ├── components/
│       │   ├── layout/Sidebar.tsx
│       │   ├── layout/TopBar.tsx
│       │   └── ProgressTracker.tsx      # WebSocket live progress
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
│   ├── ci.yml                           # Backend + Frontend combined check
│   ├── backend.yml                      # Import checks + parser + chunker tests
│   └── frontend.yml                     # TypeScript check + build
├── render.yaml                          # Render deployment config
├── docker-compose.yml                   # Local Docker setup
└── .gitignore
🚀 Local Setup
Prerequisites
- Python 3.11+
- Node.js 20+
- Git
- Groq API key (free)
- Supabase account (free)
Backend
bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
Edit .env:
env
# Database (Supabase Session Pooler URL)
DATABASE_URL=postgresql://postgres.xxxx:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

# Groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2
USE_GPU=false

# Storage
CHROMA_PERSIST_DIR=./chroma_db
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=100

# CORS
FRONTEND_URL=http://localhost:5173
SECRET_KEY=your-secret-key-here
bash
uvicorn main:app --reload --port 8000
# ✅ CodeLens AI is ready at http://localhost:8000
# 📖 API docs at http://localhost:8000/docs
Frontend
bash
cd frontend
npm install
Create frontend/.env.local:
env
VITE_API_URL=http://localhost:8000
bash
npm run dev
# ✅ Frontend at http://localhost:5173
GPU Acceleration (Optional — NVIDIA only)
bash
# Uninstall CPU PyTorch
pip uninstall torch -y

# Install CUDA PyTorch
pip install torch==2.3.1+cu121 --index-url https://download.pytorch.org/whl/cu121
Set USE_GPU=true in your .env.
⚠️ Never change requirements.txt to CUDA. Render uses requirements.txt and has no GPU. Only your local .env should have USE_GPU=true.

Docker
bash
# Set environment variables
export GROQ_API_KEY=gsk_your_key_here
export DATABASE_URL=postgresql://...

docker-compose up --build
# ✅ App running at http://localhost:3000
📡 API Reference
Repositories
POST   /repositories/upload              Upload ZIP file
POST   /repositories/github              Clone GitHub repository
GET    /repositories                     List all repositories
GET    /repositories/{id}                Get repository details
GET    /repositories/{id}/status         Get processing status
GET    /repositories/{id}/stats          File, chunk, LOC statistics
GET    /repositories/{id}/files          List all files with metadata
GET    /repositories/{id}/files/{fid}/content   Get file source code
POST   /repositories/{id}/reindex        Incremental re-index
DELETE /repositories/{id}                Delete repository + vectors
Chat
POST   /chat                             Ask question (SSE streaming)
GET    /chat/conversations/{repo_id}     List conversations
GET    /chat/history/{conv_id}           Get conversation history
Search & Analysis
POST   /search                           Semantic code search
POST   /analysis/{repo_id}              Run static analysis
GET    /analysis/{repo_id}/issues        Get issues (filter by severity)
GET    /analysis/{repo_id}/summary       Health score + issue counts
Generation
POST   /generate/tests                   Generate unit tests
POST   /generate/docs                    Generate documentation
GET    /generate/symbols/{repo_id}/{fid} Get testable symbols
Real-time
WS     /ws/progress/{repo_id}            Live processing progress (WebSocket)
🔑 Key Design Decisions
Why RAG instead of sending the whole repo?
100K lines ≈ 3M tokens. No LLM context window fits that. Even if it did, cost would be $30-100 per query and quality would degrade. RAG retrieves 5-8 relevant chunks — making answers fast, accurate, and nearly free.

Why semantic chunking instead of fixed-size?
Fixed-size splits at arbitrary character counts, breaking functions mid-way. AST-based chunking respects function/class boundaries — every chunk is a complete, meaningful unit. This dramatically improves retrieval precision.

Why sentence-transformers locally instead of OpenAI Embeddings API?
Zero cost. all-MiniLM-L6-v2 runs on CPU or GPU, generates 384-dim embeddings, has no API key requirement, and no rate limits. For 10,000 chunks that's ~$1 on OpenAI — free with sentence-transformers.

Why ChromaDB instead of pgvector?
ChromaDB requires zero infrastructure. No PostgreSQL extension setup, no server configuration. The vector_store.py abstraction makes swapping to pgvector trivial when scaling to production.

Why background summarization?
Running LLM summarization during indexing blocked the READY status for 10-20+ minutes on Render's free CPU. Moving it to a background asyncio task with a 5-minute timeout means repos become READY in 2-3 minutes. Users chat immediately — summaries improve answers in the background.

Why Groq instead of OpenAI?
Groq's custom LPU (Language Processing Unit) hardware gives 10-20x faster inference. Free tier is generous. The BaseLLMProvider abstraction makes switching providers a one-file change.

Why two databases?
PostgreSQL stores structured relational data — repos, files, symbols, analysis issues, chat history. ChromaDB stores vector embeddings for semantic similarity search. They serve completely different query patterns and neither can efficiently replace the other.

⚠️ Limitations
- Parses Python, JavaScript, TypeScript only (extensible via parser_factory.py)
- GitHub cloning requires public repositories
- ChromaDB resets on Render restarts (ephemeral filesystem) — re-upload after restart
- Groq free tier: ~30 requests/minute rate limit
- Render free tier: 50+ second cold start after inactivity
- No authentication (single-user mode)
- Jupyter Notebook (.ipynb) not yet supported
🔮 Roadmap
- pgvector integration for persistent vector storage on PostgreSQL
- GitHub OAuth authentication
- Java, Go, Rust, C++ parser support
- Jupyter Notebook (.ipynb) ingestion
- PR diff analysis — "what changed and why?"
- Evaluation pipeline with Recall@K metrics
- Team collaboration with shared repositories
- VS Code extension
🎤 Interview Q&A
  <details> <summary><b>Explain your RAG pipeline</b></summary> 
The repository is parsed with Python AST (for Python) and regex-based parser (for JS/TS) into semantic chunks that respect function and class boundaries. Each chunk is embedded locally using sentence-transformers (all-MiniLM-L6-v2, 384 dimensions) and stored in ChromaDB. On query: embed the question, vector search returns top 30 candidates, hybrid boosting adds keyword and symbol matches, multi-signal reranking selects the top 8, token budget enforces a 6000-token limit, and the final context is sent to Groq with a system prompt that enforces source-grounded answers with file and line citations.
  </details> <details> <summary><b>Why not just send the whole repository to the LLM?</b></summary> 
A 100,000 line codebase is approximately 3 million tokens — far exceeding any LLM context window (typically 8K-128K tokens). Even if a model supported it, cost would be $30-100 per question and quality would degrade as the model loses focus with too much context. RAG retrieves only the 5-8 most relevant chunks, keeping cost near zero and answers focused.
  </details> <details> <summary><b>What is semantic chunking and why does it matter?</b></summary> 
Fixed-size chunking splits code at arbitrary character counts — potentially breaking a function in half. The first half has no meaning without the second. Semantic chunking uses the AST to identify where functions and classes begin and end. Every chunk is always a complete, meaningful unit. This dramatically improves retrieval precision because the LLM receives complete, self-contained code rather than fragments.
  </details> <details> <summary><b>How does importance scoring work?</b></summary> 
Every file is scored 0-100 using programmatic signals: entry point files get +25, paths containing keywords like auth/database/api get +30, incoming dependency count adds up to +20, symbol count adds up to +20. Files scoring ≥60 are HIGH and get LLM summaries during indexing. Low files are summarized lazily on demand. This reduces LLM API calls by approximately 80% compared to summarizing everything.
  </details> <details> <summary><b>Why two databases — PostgreSQL and ChromaDB?</b></summary> 
They serve completely different query patterns. PostgreSQL stores structured relational data — repositories, files, symbols, analysis issues, conversations — and answers queries like "give me all files in this repo with HIGH importance." ChromaDB stores 384-dimensional vectors and answers similarity queries like "find the 30 code chunks most semantically similar to this question." You cannot efficiently do cosine similarity search in PostgreSQL without pgvector, and you cannot do relational joins in ChromaDB. Both are necessary.
  </details> <details> <summary><b>What is incremental indexing?</b></summary> 
When a developer updates one file and re-indexes, there is no reason to re-embed all 500 files. At index time, an MD5 hash is stored per file. On re-index, the current hash is compared with the stored hash. Only changed files are re-parsed, re-chunked, and re-embedded. Old ChromaDB vectors for changed files are deleted first. Unchanged files are completely skipped — making subsequent re-indexing approximately 10x faster.
  </details> 
👨‍💻 About
Bobby Ahirwar B.Tech Chemical Engineering — IIT Hyderabad (Graduating 2027) 
This project demonstrates:
- AI/ML Engineering — RAG pipeline, embeddings, LLM integration, vector search
- Backend Engineering — async Python, FastAPI, WebSockets, SSE streaming
- Frontend Engineering — React, TypeScript, real-time UI
- Database Design — relational (PostgreSQL) + vector (ChromaDB) dual-database architecture
- Production Engineering — Docker, GitHub Actions CI/CD, GPU/CPU optimization, cloud deployment
📄 License
MIT © 2026 Bobby Ahirwar