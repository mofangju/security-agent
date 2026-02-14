# Security Agent — Multi-Agent WAF Assistant PoC

An end-to-end security demo with **SafeLine WAF** (real open-source WAF) and **Lumina**, an AI-powered security assistant that helps engineers operate their WAF through natural language.

## Architecture

```
┌──────────┐     ┌─────────────────────┐     ┌──────────┐
│  Client   │────▶│     SafeLine WAF    │────▶│ Pet Shop │
│  Traffic  │     │  (7 Docker containers) │     │  (Flask) │
│  Generator│     │  - Tengine proxy    │     │ Vulnerable│
└──────────┘     │  - AI detector      │     │  Web App  │
┌──────────┐     │  - Management UI    │     └──────────┘
│  Attacker │────▶│  - PostgreSQL       │
│  Traffic  │     │  - REST API         │
│  Generator│     └─────────┬───────────┘
└──────────┘               │ logs + API
                           ▼
                  ┌─────────────────────┐
                  │   🤖 Lumina          │
                  │   (AI Assistant)    │
                  │                     │
                  │ 7 Agent Nodes:      │
                  │ • Monitor           │
                  │ • Log Analyst       │
                  │ • Config Manager    │
                  │ • Threat Intel      │
                  │ • Rule Tuner        │
                  │ • Reporter          │
                  │ • RAG Agent         │
                  │                     │
                  │ Tools:              │
                  │ • SafeLine API      │
                  │ • CVE Lookup        │
                  │ • RAG Search        │
                  └─────────────────────┘
```

## Meet Lumina 🤖

**Lumina** is the AI-powered security assistant at the heart of this project. Built with LangGraph, Lumina acts as your intelligent WAF co-pilot — understanding natural language requests from engineers and translating them into SafeLine WAF operations.

Lumina has **7 specialist capabilities**:
- 📊 **Monitor** — real-time traffic stats and anomaly detection
- 🔍 **Log Analyst** — attack event analysis and pattern recognition
- ⚙️ **Config Manager** — WAF mode switching, IP blocking, rule management
- 🕵️ **Threat Intel** — CVE/CWE correlation and OWASP mapping
- 🔧 **Rule Tuner** — false positive investigation and whitelist creation
- 📋 **Reporter** — structured incident report generation
- 📚 **Documentation Expert** — answers "how do I..." questions via RAG

A supervisor node routes each engineer request to the right specialist, making Lumina feel like a single knowledgeable assistant.

## Components

| Component | Description |
|---|---|
| **Pet Shop** | Vulnerable Flask web app (SQLi, XSS, path traversal, command injection) |
| **SafeLine** | Open-source WAF with semantic analysis engine, REST API, web dashboard |
| **Lumina** | LangGraph AI assistant — helps engineers monitor, configure, and troubleshoot SafeLine |
| **Traffic Generators** | Simulate legitimate users and attackers |
| **RAG Pipeline** | ChromaDB + hybrid search over SafeLine docs, OWASP guides, IR playbooks |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An LLM provider key (OpenAI, Google Gemini, or local vLLM)

### Setup
```bash
# Clone and set up virtual environment
cd security-agent
uv venv                    # creates .venv/
source .venv/bin/activate  # activate the venv
uv pip install -e ".[dev]" # install all deps (including dev tools)
cp .env.example .env
# Edit .env with your LLM API key and SafeLine token

# Start SafeLine + Pet Shop
docker compose up -d

# Ingest docs into RAG knowledge base
python -m security_agent.ingest

# Register Pet Shop in SafeLine
python -m security_agent.setup_site
```

## Demo Walkthrough (5 Phases, ~16 min)

### Phase 1: Normal Traffic (~2 min)
```bash
python -m security_agent.traffic --mode client
```
Legitimate users browse Pet Shop. SafeLine logs clean traffic.

### Phase 2: Attack Without WAF Blocking (~2 min)
```bash
python -m security_agent.traffic --mode attacker
```
Attacks succeed — SQLi dumps DB, XSS payloads execute. SafeLine logs attacks but is in detect-only mode.

### Phase 3: Engineer Asks Lumina for Help (~5 min)
```bash
python -m security_agent.assistant
```
Interactive chat with Lumina:
- **"What's happening?"** → Lumina reads SafeLine logs, identifies 23 attacks
- **"Enable blocking"** → Lumina switches SafeLine to BLOCK mode via API
- **"Block that IP"** → Lumina adds attacker IP to SafeLine blacklist

### Phase 4: Verify Protection (~2 min)
```bash
python -m security_agent.traffic --mode attacker
```
All attacks now blocked (403). Lumina confirms via SafeLine stats API.

### Phase 5: Post-Incident (~5 min)
- **False positive tuning** → customer can't search "script writing tips"
- **CVE correlation** → map attacks to OWASP categories
- **Incident report** → structured report with timeline, impact, recommendations
- **How-to questions** → RAG answers from SafeLine docs

## SafeLine REST API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `GET /api/open/events` | Read attack events |
| `GET /api/stat/qps` | Real-time traffic stats |
| `GET /api/dashboard/intercepts` | Block statistics |
| `GET/PUT /api/open/global/mode` | Protection mode (block/detect/off) |
| `GET/POST /api/open/policy` | Custom WAF rules |
| `GET/POST /api/open/ipgroup` | IP blacklist/whitelist |
| `GET /api/open/records/acl` | Blocked request details |
| `POST /api/open/site` | Register protected sites |
| `GET/POST /api/open/global/acl` | Rate limiting rules |

## Tech Stack

| Layer | Technology |
|---|---|
| WAF | SafeLine (Docker, semantic analysis) |
| Web App | Flask + SQLite |
| AI Framework | LangGraph |
| LLM Providers | vLLM, OpenAI, Google Gemini |
| Vector DB | ChromaDB |
| Search | Hybrid (semantic + BM25 + RRF) |
| Evaluation | RAGAS |

## Project Structure

```
security-agent/
├── docker-compose.yml          # SafeLine + Pet Shop
├── pyproject.toml
├── .env.example
├── src/security_agent/
│   ├── config.py               # Settings
│   ├── petshop/                # 🐾 Vulnerable web app
│   ├── assistant/              # 🤖 Lumina AI assistant (LangGraph)
│   │   ├── graph.py            # Supervisor graph
│   │   ├── state.py            # Agent state
│   │   ├── nodes/              # 7 specialist nodes
│   │   └── cli.py              # Interactive chat
│   ├── tools/                  # 🔧 SafeLine API, CVE, RAG
│   ├── rag/                    # 📚 ChromaDB pipeline
│   ├── llm/                    # 🧠 Multi-provider LLM
│   ├── traffic/                # 🚦 Client + attacker generators
│   ├── eval/                   # 📊 Evaluation framework
│   └── finetune/               # 🎯 Fine-tuning scaffolding
├── data/docs/                  # RAG knowledge base
├── tests/
└── scripts/
```

## License

MIT
