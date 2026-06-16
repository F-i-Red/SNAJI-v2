# SNAJI — Sistema Nacional de Assistência Jurídica Inteligente
**República Portuguesa · Versão 4.0.0**

Motor jurídico português completo com RAG (246 artigos reais), autenticação RBAC + CMD, workflow processual com prazos legais, audiências multi-agente e integração com fontes governamentais.

---

## O que está construído

### Fases completadas
| Fase | Descrição | Testes |
|------|-----------|--------|
| **1 — MVP** | RAG 246 artigos, consulta jurídica, geração de documentos, autenticação | 78 |
| **2 — Workflow** | Prazos legais automáticos (CPC/CPP/CT), notificações, gestão de processos | 97 |
| **3 — Audiências** | Debate multi-agente, fases processuais reais, provas, decisão fundamentada | 118 |
| **4 — Integrações** | DRE, CMD (Chave Móvel Digital), jurisprudência DGSI | 138 |

### Corpus jurídico real
- **246 artigos** de 6 diplomas: CRP, Código do Trabalho, Código Civil, RGPD, Código Penal, CPC+CPP
- **7 acórdãos** representativos (STJ, TRL, TC) com BM25 pesquisável
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

# Gerar corpus jurídico (já incluído, mas regenerar se necessário)
python app/rag/corpus/processador.py

# Arrancar o servidor
uvicorn app.main:app --reload --port 8000
```

O servidor arranca em `http://localhost:8000`
Documentação interactiva: `http://localhost:8000/docs`

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
│   │   ├── api/              # Rotas FastAPI (auth, análise, workflow, audiências, integrações)
│   │   ├── rag/              # Motor BM25 + corpus 246 artigos reais
│   │   │   └── corpus/       # CRP, CT, CC, RGPD, CP, CPC+CPP em texto
│   │   ├── reasoning/        # Pipeline de raciocínio jurídico
│   │   ├── workflow/         # Prazos legais automáticos (CPC/CPP/CT)
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
        └── types/            # Tipos TypeScript partilhados
```

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

## Correr os testes

```bash
cd backend
python -m pytest tests/ -v          # todos os testes com detalhe
python -m pytest tests/ -q          # sumário rápido
python -m pytest tests/test_rag.py  # apenas RAG
```

**Resultado esperado: 138 passed, 0 failed**

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

- [ ] Embeddings semânticos com pgvector (complementar ao BM25)
- [ ] Sincronização automática DRE (scraping ou API AMA)
- [ ] Integração Citius (sistema de gestão processual dos tribunais)
- [ ] Modo offline/soberano com modelo local
- [ ] App mobile (React Native)
- [ ] Certificação RGPD pela CNPD

---

*SNAJI — República Portuguesa · Construído com Python + FastAPI + React + TypeScript*
