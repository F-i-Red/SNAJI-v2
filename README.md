<div align="center">

# ⚖️ SNAJI
### Sistema Nacional de Assistência Jurídica Inteligente

**IA jurídica soberana para Portugal — construída por um cidadão, para todos os cidadãos.**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)
[![Tests](https://img.shields.io/badge/Testes-172%20passing-brightgreen?style=flat)]()

</div>

---

Motor jurídico português completo com RAG (246 artigos reais), autenticação RBAC + CMD, workflow processual com prazos legais, audiências multi-agente e integração com fontes governamentais.

---

## Contexto

O SNAJI nasceu da convicção de que o acesso à justiça não pode depender da capacidade financeira do cidadão. Em Portugal, a distância entre os direitos consagrados e o seu exercício efectivo é ainda demasiado grande.

Este projeto foi desenvolvido individualmente, com recurso ao assistente de IA **Claude Pro (Anthropic)** — cuja subscrição mensal e energia foram os únicos custos diretos do projeto. É, em si mesmo, uma demonstração do que um cidadão pode construir quando tem acesso às ferramentas certas.

---

## O que é e não é o SNAJI?

O SNAJI não é um chatbot com leis coladas. É um **sistema processual inteligente** que acompanha o cidadão, o advogado e o magistrado em cada fase do processo judicial português — com fundamentação real, integridade garantida e soberania de dados.

Desenvolvido integralmente em Portugal, com legislação portuguesa real como base de conhecimento.

---

## Funcionalidades

### 🧠 Assistência Jurídica com RAG
Respostas fundamentadas em legislação portuguesa vigente — Código Civil, Código Penal, CPC, CRP e outros — com citação de fontes e mecanismos anti-alucinação.

### ⚙️ Gestão de Processos
Workflow processual completo: criação, tramitação, atribuição de papéis, controlo de prazos e estados. Cada intervenção é registada com hash criptográfico para garantir imutabilidade.

### 🎭 Simulação de Audiências
Simulação de audiências judiciais com múltiplos agentes: juiz, acusação, defesa e testemunhas. Útil para preparação, formação e análise processual.

### 👤 Controlo de Acesso por Perfil (RBAC)
Quatro perfis diferenciados com permissões específicas:

| Perfil | Acesso |
|---|---|
| Cidadão | Consulta jurídica, acompanhamento do próprio processo |
| Advogado | Gestão de clientes, processos, documentos |
| Magistrado | Supervisão, decisão, audiências |
| Administrador | Gestão total do sistema |

### 📚 Jurisprudência e Legislação
Integração com normas do Diário da República Eletrónico. Pesquisa híbrida (BM25 + semântica) sobre corpus jurídico português.

### 🔒 Segurança e Soberania
- Hashes criptográficos em todas as intervenções
- Suporte nativo a modelos de IA locais (sem dependência obrigatória de APIs externas)
- Dados permanecem em território nacional

---

### Fases completadas
| Fase | Descrição | Testes |
|------|-----------|--------|
| **1 — MVP** | RAG 246 artigos, consulta jurídica, geração de documentos, autenticação | 78 |
| **2 — Workflow** | Prazos legais automáticos (CPC/CPP/CT), notificações, gestão de processos | 97 |
| **3 — Audiências** | Debate multi-agente, fases processuais reais, provas, decisão fundamentada | 118 |
| **4 — Integrações** | DRE, CMD (Chave Móvel Digital), jurisprudência DGSI | 138 |

### Corpus jurídico real
- **246 artigos** de 6 diplomas: CRP, Código do Trabalho, Código Civil, RGPD, Código Penal, CPC+CPP
- **13 acórdãos** representativos (STJ, TRL, TC) com BM25 pesquisável
- Anti-alucinação determinístico — citações validadas contra corpus

---

## Arranque rápido

### Pré-requisitos
- Python 3.12+
- Node.js 18+
- (Opcional para funcionalidades completas) Chave API Anthropic

### 1. Backend

```bash
cd backend

# Copiar e preencher variáveis de ambiente
cp .env.example .env
# Editar .env — obrigatório: JWT_SECRET (qualquer string longa)
# Opcional: ANTHROPIC_API_KEY (para análise LLM real)

# Instalar dependências
pip install -r requirements.txt
pip install pypdf

# Gerar corpus jurídico (já incluído, mas regenerar se necessário)
python app/rag/corpus/processador.py

# Arrancar o servidor
uvicorn app.main:app --reload --port 8000
```

O servidor arranca em `http://localhost:8000`
Documentação interactiva: `http://localhost:8000/docs`

### Ou

No CMD, dentro da pasta backend:
```bash
1. py -3.12 -m venv .venv — força a versão python 3.12.10 que também é usada no SNAJI
2. .venv\Scripts\activate.bat — deve aparecer (.venv) no início da linha
3. pip install -r requirements.txt — atenção: isto descarrega ~2 GB (inclui os modelos de embeddings), demora vários minutos;
3. pip install pypdf
4. copy .env.example .env
5. depois notepad .env — preenche ANTHROPIC_API_KEY= (a tua chave), JWT_SECRET= (uma frase longa qualquer inventada por ti) e DATABASE_URL=sqlite:///./snaji.db
6. python -m uvicorn app.main:app --reload — dentro do venv, o python já funciona

Ao arrancar, verás os logs do SNAJI e podes abrir no browser http://localhost:8000/health (deve responder "status: ok" com os componentes) e http://localhost:8000/docs (a documentação interativa da API, onde as rotas do Instrutor aparecem).
```

### 2. Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Arrancar em desenvolvimento
npm run dev
```

A interface abre em `http://localhost:5173`

---

## Contas de demonstração

| Papel | Email | Password |
|-------|-------|----------|
| Cidadão | cidadao@snaji.gov.pt | Cidad2024! |
| Advogado | advogado@snaji.gov.pt | Advog2024! |
| Magistrado | magistrado@snaji.gov.pt | Magis2024! |
| Analista | analista@snaji.gov.pt | Anali2024! |
| Admin | admin@snaji.gov.pt | Admin2024! |

---

## Ficheiro .env mínimo para arrancar

```env
# Obrigatório
JWT_SECRET=qualquer-string-longa-e-aleatoria-minimo-32-caracteres
DATABASE_URL=postgresql://user:pass@localhost/snaji  # ou sqlite:///snaji.db em dev
ANTHROPIC_API_KEY=sk-ant-...  # opcional — sem ela usa modo stub

# Opcional — só para integrações governamentais reais
CMD_CLIENT_ID=...
CMD_CLIENT_SECRET=...
CMD_REDIRECT_URI=http://localhost:8000/api/v1/auth/cmd/callback
CMD_AMBIENTE=sandbox
```

> **Sem ANTHROPIC_API_KEY**: o sistema funciona em modo stub — RAG, workflow, audiências e testes funcionam todos. O motor LLM produz respostas genéricas baseadas nas normas do corpus, sem análise semântica completa.

---

## Arquitectura

```
snaji/
├── backend/
│   ├── app/
│   │   ├── agents/           # Agentes de IA especializados
│   │   ├── api/              # Rotas FastAPI (auth, análise, workflow, audiências, integrações)
│   │   ├── core/             # Configuração e utilitários centrais
│   │   ├── rag/              # Motor BM25 + corpus 246 artigos reais
│   │   │   └── corpus/       # CRP, CT, CC, RGPD, CP, CPC+CPP em texto
│   │   ├── reasoning/        # Pipeline de raciocínio jurídico
│   │   ├── workflow/         # Prazos legais automáticos (CPC/CPP/CT)
│   │   ├── orchestrator/     # Orquestração de workflows
│   │   ├── audiencias/       # Motor de audiências multi-agente
│   │   ├── agents/           # Juiz, Acusação, Defesa, Perito
│   │   ├── processes/        # Repositório de processos jurídicos
│   │   ├── documents/        # Processamento PDF/Word
│   │   ├── generation/       # Geração de petições, contestações, recursos
│   │   ├── security/         # JWT, RBAC, Argon2, dependências FastAPI
│   │   ├── integrations/     # DRE, CMD, Jurisprudência
│   │   ├── notifications/    # Alertas de prazos
│   │   └── db/               # Repositórios (memória → PostgreSQL)
│   └── tests/                # 138 testes (unit + integração)
│       ├── test_rag.py
│       ├── test_auth.py
│       ├── test_reasoning.py
│       ├── test_integration.py
│       ├── test_workflow.py
│       ├── test_audiencias.py
│       └── test_integracoes.py
│
└── frontend/
    └── src/
        ├── pages/            # Dashboard, Consulta, Processos, Audiências, Documentos, Auditoria
        ├── components/       # Layout, sidebar adaptativa por perfil
        ├── auth/             # Store Zustand + gestão de sessão
        ├── services/         # Cliente Axios com interceptores JWT
        ├── styles/           # Estilos globais
        └── types/            # Tipos TypeScript partilhados
```

**Stack:**  FastAPI · PostgreSQL · Redis · React 18 · Vite · Docker

---

## API — Endpoints principais

### Autenticação
```
POST /api/v1/auth/login          → Login com email + password
GET  /api/v1/auth/me             → Dados do utilizador actual
GET  /api/v1/auth/cmd/iniciar    → Iniciar autenticação CMD (gov.pt)
```

### Análise jurídica (Fase 1)
```
POST /api/v1/analysis            → Analisar caso com RAG + LLM
GET  /api/v1/fontes              → Listar diplomas disponíveis
POST /api/v1/documentos/upload   → Upload PDF/Word + análise
POST /api/v1/gerar-documento     → Gerar petição/contestação/recurso
```

### Processos (Fase 1+2)
```
GET  /api/v1/processos                        → Listar processos
POST /api/v1/processos                        → Criar processo
GET  /api/v1/processos/{id}                   → Detalhe + histórico
POST /api/v1/processos/{id}/avancar-workflow  → Avançar fase + prazos automáticos
GET  /api/v1/processos/{id}/prazos            → Prazos com análise de urgência
GET  /api/v1/notificacoes                     → Alertas de prazos críticos
GET  /api/v1/workflow/dashboard               → Visão agregada de prazos em risco
```

### Audiências (Fase 3)
```
POST /api/v1/audiencias                       → Criar audiência
GET  /api/v1/audiencias/{id}/fases            → Estado das fases
POST /api/v1/audiencias/{id}/intervencao      → Submeter intervenção humana
POST /api/v1/audiencias/{id}/intervencao-ia   → Gerar intervenção com IA
POST /api/v1/audiencias/{id}/prova-ficheiro   → Apresentar prova (PDF/etc.)
POST /api/v1/audiencias/{id}/decidir          → Proferir decisão final
```

### Integrações Gov (Fase 4)
```
GET  /api/v1/integracoes/dre/pesquisar        → Pesquisa no DRE
GET  /api/v1/integracoes/dre/vigencia         → Verificar artigo em vigor
GET  /api/v1/integracoes/jurisprudencia       → Pesquisa de acórdãos
GET  /api/v1/integracoes/jurisprudencia/norma → Acórdãos por norma
GET  /api/v1/integracoes/estado               → Estado de todas as integrações
```

---

## Início rápido

### Pré-requisitos
- Docker e Docker Compose
- Node.js 18+
- Python 3.11+

### Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/F-i-Red/SNAJI-Sistema-Nacional-de-Assistencia-Juridica-Inteligente.git
cd SNAJI-Sistema-Nacional-de-Assistencia-Juridica-Inteligente

# 2. Configurar variáveis de ambiente
cp backend/.env.example backend/.env
# Editar backend/.env com as suas chaves

# 3. Lançar com Docker
cd backend
docker-compose up --build

# 4. Frontend (terminal separado)
cd frontend
npm install
npm run dev
```

A aplicação fica disponível em `http://localhost:5173`  
A API em `http://localhost:8000`  
Documentação interativa em `http://localhost:8000/docs`
Status do sistema em 'http://localhost:8000/health'

---

## Testes

```bash
cd backend
pytest                    # todos os testes
pytest tests/ -v          # com output detalhado
pytest --cov=app tests/   # com cobertura
```

## Correr os testes

```bash
cd backend
python -m pytest tests/ -v          # todos os testes com detalhe
python -m pytest tests/ -q          # sumário rápido
python -m pytest tests/test_rag.py  # apenas RAG
```

## Limpeza do frontend (reset):

```bash
cd C:\SNAJI\frontend
rmdir /s /q node_modules
del package-lock.json
```

---

## Para produção (.gov)

1. **LLM soberano**: substituir `ANTHROPIC_API_KEY` por modelo local (Mistral/Llama fine-tuned em português jurídico) via Ollama ou vLLM
2. **Base de dados**: activar PostgreSQL com pgvector para embeddings semânticos
3. **CMD**: registar a aplicação em autenticacao.gov.pt e preencher `CMD_CLIENT_ID`/`CMD_CLIENT_SECRET`
4. **DRE**: negociar acesso API directo com AMA/DGPJ para sincronização automática de legislação
5. **Kubernetes**: usar o `infra/kubernetes/` existente
6. **Certificados**: HTTPS obrigatório; usar certificados da SCEE (Sistema de Certificação Electrónica do Estado)

---

## Roadmap

- [ ] Vector store híbrido (BM25 + embeddings `bge-m3`)
- [ ] Geração de PDF processual com cabeçalho de tribunal
- [ ] Modo colaboração (advogado + cliente em simultâneo)
- [ ] Análise comparativa de acórdãos semelhantes
- [ ] Exportação de dossiê completo (processo + documentos + decisão)
- [ ] Integração com CITIUS / SISAAE
- [ ] Dark mode
- [ ] Embeddings semânticos com pgvector (complementar ao BM25)
- [ ] Sincronização automática DRE (scraping ou API AMA)
- [ ] Integração Citius (sistema de gestão processual dos tribunais)
- [ ] Modo offline/soberano com modelo local
- [ ] App mobile (React Native)
- [ ] Certificação RGPD pela CNPD

---

## Licença

[MIT](LICENSE) — livre para usar, estudar, modificar e distribuir.

---

<div align="center">

Desenvolvido por **Frederico Guilherme Sarmento Ferreira de Magalhães** e **Claude 4.6/Fable 5**

*"A justiça não pode ser um privilégio."*

</div>

---

*SNAJI — República Portuguesa · Construído com Python + FastAPI + React + TypeScript*
