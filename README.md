# ⚖️ SNAJI

### Sistema Nacional de Assistência Jurídica Inteligente

**IA jurídica soberana para Portugal — construída por um cidadão, para todos os cidadãos.**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)
[![Tests](https://img.shields.io/badge/Testes-196%20passing-brightgreen?style=flat)](backend/tests)

---

Motor jurídico português completo com RAG (**6.770 artigos reais de 12 diplomas**), autenticação RBAC + CMD, workflow processual com prazos legais, audiências multi-agente, classificação jurídica multi-área e integração com fontes governamentais.

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

Respostas fundamentadas em legislação portuguesa vigente — 12 diplomas, do Código Civil ao CIRE — com citação de fontes, sinalização de artigos revogados e mecanismos anti-alucinação determinísticos.

### 🧭 Classificação Jurídica Multi-Área

Classificador jurídico que identifica a(s) área(s) de direito de um caso — incluindo casos mistos (multi-área) — com fallback heurístico gracioso quando o LLM não está disponível.

### ⚙️ Gestão de Processos e Casos

Workflow processual completo: criação, tramitação, atribuição de papéis, controlo de prazos e estados, com persistência de casos isolada por utilizador. Cada intervenção é registada com hash criptográfico para garantir imutabilidade.

### 🎭 Simulação de Audiências

Simulação de audiências judiciais com múltiplos agentes: juiz, acusação, defesa e testemunhas. Útil para preparação, formação e análise processual.

### 👤 Controlo de Acesso por Perfil (RBAC)

Quatro perfis diferenciados com permissões específicas:

| Perfil        | Acesso                                                |
| ------------- | ----------------------------------------------------- |
| Cidadão       | Consulta jurídica, acompanhamento do próprio processo |
| Advogado      | Gestão de clientes, processos, documentos             |
| Magistrado    | Supervisão, decisão, audiências                       |
| Administrador | Gestão total do sistema                               |

### 📚 Jurisprudência e Legislação

Integração com normas do Diário da República Eletrónico e **atualizador automático de acórdãos do STJ** (testado contra fixtures reais de stj.pt, sem dependência da rede). Pesquisa híbrida (BM25 + semântica) sobre o corpus jurídico português.

### 🔒 Segurança e Soberania

- Hashes criptográficos em todas as intervenções
- Suporte nativo a modelos de IA locais (sem dependência obrigatória de APIs externas)
- Dados permanecem em território nacional

---

## Fases completadas

| Fase                  | Descrição                                                                                    |
| --------------------- | -------------------------------------------------------------------------------------------- |
| **1 — MVP**           | RAG sobre legislação real, consulta jurídica, geração de documentos, autenticação            |
| **2 — Workflow**      | Prazos legais automáticos (CPC/CPP/CT), notificações, gestão de processos                    |
| **3 — Audiências**    | Debate multi-agente, fases processuais reais, provas, decisão fundamentada                   |
| **4 — Integrações**   | DRE, CMD (Chave Móvel Digital), jurisprudência DGSI                                          |
| **5 — Inteligência**  | Classificador jurídico multi-área, persistência de casos, atualizador de acórdãos, analytics |

## Corpus jurídico real

- **6.770 artigos** de **12 diplomas** (6.569 em vigor; 201 sinalizados como revogados), carregados em julho de 2026:

| Diploma                                                | Sigla | Artigos |
| ------------------------------------------------------ | ----- | ------- |
| Código Civil                                           | CC    | 2.382   |
| Código de Processo Civil                               | CPC   | 1.146   |
| Código das Sociedades Comerciais                       | CSC   | 641     |
| Código do Trabalho                                     | CT    | 601     |
| Código de Processo Penal                               | CPP   | 547     |
| Código Penal                                           | CP    | 429     |
| Código da Insolvência e da Recuperação de Empresas     | CIRE  | 328     |
| Constituição da República Portuguesa                   | CRP   | 296     |
| Código do Procedimento Administrativo                  | CPA   | 203     |
| Regulamento Geral sobre a Proteção de Dados            | RGPD  | 99      |
| Lei dos Julgados de Paz                                | LJP   | 69      |
| Lei de Defesa do Consumidor                            | LDC   | 29      |

- **64 acórdãos do STJ** com pesquisa BM25
- Anti-alucinação determinístico — citações validadas contra o corpus

## Testes

**196 testes automatizados — todos aprovados** (unitários + integração), executáveis sem chave de API (modo stub):

| Ficheiro                 | Testes | Âmbito                                          |
| ------------------------ | ------ | ----------------------------------------------- |
| `test_classificador.py`  | 43     | Classificação jurídica multi-área               |
| `test_integration.py`    | 24     | Integração ponta-a-ponta                        |
| `test_auth.py`           | 23     | Autenticação, JWT, RBAC                         |
| `test_audiencias.py`     | 22     | Motor de audiências multi-agente                |
| `test_integracoes.py`    | 21     | DRE, CMD, jurisprudência                        |
| `test_reasoning.py`      | 21     | Pipeline de raciocínio jurídico                 |
| `test_workflow.py`       | 19     | Prazos legais e estados processuais             |
| `test_rag.py`            | 12     | Motor RAG e validação de citações               |
| `test_casos.py`          | 6      | Persistência e isolamento de casos              |
| `test_atualizador.py`    | 5      | Atualizador de acórdãos STJ (fixtures reais)    |
| **Total**                | **196**|                                                 |

```bash
cd backend
python -m pytest tests/ -v          # todos os testes com detalhe
python -m pytest tests/ -q          # sumário rápido
python -m pytest --cov=app tests/   # com cobertura
```

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
Estado do sistema: `http://localhost:8000/health`

### Ou, no Windows (CMD), dentro da pasta backend:

```
1. py -3.12 -m venv .venv — força a versão python 3.12 usada no SNAJI
2. .venv\Scripts\activate.bat — deve aparecer (.venv) no início da linha
3. pip install -r requirements.txt — atenção: descarrega ~2 GB (inclui os modelos de embeddings), demora vários minutos
4. pip install pypdf
5. copy .env.example .env
6. notepad .env — preenche ANTHROPIC_API_KEY= (a tua chave), JWT_SECRET= (uma frase longa qualquer) e DATABASE_URL=sqlite:///./snaji.db
7. python -m uvicorn app.main:app --reload
```

> **Nota sobre o `.env`**: a configuração rejeita variáveis não reconhecidas. Se o arranque falhar com `Configuração inválida … extra_forbidden`, remove do `.env` as linhas não suportadas (ex.: `ALLOWED_ORIGINS`).

### 2. Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Arrancar em desenvolvimento
npm run dev
```

A interface abre em `http://localhost:5173`

### Ou com Docker

```bash
git clone https://github.com/F-i-Red/SNAJI-v2.git
cd SNAJI-v2/backend
cp .env.example .env   # editar com as suas chaves
docker-compose up --build

# Frontend (terminal separado)
cd ../frontend
npm install
npm run dev
```

---

## Contas de demonstração

| Papel      | Email                     | Password   |
| ---------- | ------------------------- | ---------- |
| Cidadão    | <cidadao@snaji.gov.pt>    | Cidad2024! |
| Advogado   | <advogado@snaji.gov.pt>   | Advog2024! |
| Magistrado | <magistrado@snaji.gov.pt> | Magis2024! |
| Analista   | <analista@snaji.gov.pt>   | Anali2024! |
| Admin      | <admin@snaji.gov.pt>      | Admin2024! |

---

## Ficheiro .env mínimo para arrancar

```env
# Obrigatório
JWT_SECRET=qualquer-string-longa-e-aleatoria-minimo-32-caracteres
DATABASE_URL=sqlite:///./snaji.db   # ou postgresql://user:pass@localhost/snaji
ANTHROPIC_API_KEY=sk-ant-...        # opcional — sem ela usa modo stub

# Opcional — só para integrações governamentais reais
CMD_CLIENT_ID=...
CMD_CLIENT_SECRET=...
CMD_REDIRECT_URI=http://localhost:8000/api/v1/auth/cmd/callback
CMD_AMBIENTE=sandbox
```

> **Sem ANTHROPIC_API_KEY**: o sistema funciona em modo stub — RAG, workflow, audiências, classificador e os 196 testes funcionam todos. O motor LLM produz respostas genéricas baseadas nas normas do corpus, sem análise semântica completa.

---

## Arquitectura

```
snaji/
├── backend/
│   ├── app/
│   │   ├── agents/           # Agentes de IA especializados (Juiz, Acusação, Defesa, Perito)
│   │   ├── analytics/        # Registo e análise de eventos de utilização
│   │   ├── api/              # Rotas FastAPI (auth, análise, workflow, audiências, integrações)
│   │   ├── audiencias/       # Motor de audiências multi-agente
│   │   ├── core/             # Configuração e utilitários centrais
│   │   ├── db/               # Repositórios (casos, processos; memória → PostgreSQL)
│   │   ├── documents/        # Processamento PDF/Word (+ OCR)
│   │   ├── generation/       # Geração de petições, contestações, recursos
│   │   ├── integrations/     # DRE, CMD, Jurisprudência
│   │   ├── notifications/    # Alertas de prazos
│   │   ├── orchestrator/     # Orquestração de workflows
│   │   ├── processes/        # Repositório de processos jurídicos
│   │   ├── rag/              # Motor BM25 + corpus 6.770 artigos reais
│   │   │   └── corpus/       # CC, CPC, CSC, CT, CPP, CP, CIRE, CRP, CPA, RGPD, LJP, LDC + acórdãos STJ
│   │   ├── reasoning/        # Pipeline de raciocínio, classificador jurídico, motor de cenários, agente instrutor
│   │   ├── security/         # JWT, RBAC, Argon2, dependências FastAPI
│   │   └── workflow/         # Prazos legais automáticos (CPC/CPP/CT)
│   ├── ferramentas/          # Atualizador de acórdãos STJ
│   └── tests/                # 196 testes (unit + integração)
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

**Stack:** FastAPI · PostgreSQL · Redis · React 18 · Vite · Docker

---

## API — Endpoints principais

### Autenticação

```
POST /api/v1/auth/login          → Login com email + password
GET  /api/v1/auth/me             → Dados do utilizador actual
GET  /api/v1/auth/cmd/iniciar    → Iniciar autenticação CMD (gov.pt)
```

### Análise jurídica

```
POST /api/v1/analysis            → Analisar caso com RAG + LLM
GET  /api/v1/fontes              → Listar diplomas disponíveis
POST /api/v1/documentos/upload   → Upload PDF/Word + análise
POST /api/v1/gerar-documento     → Gerar petição/contestação/recurso
```

### Processos

```
GET  /api/v1/processos                        → Listar processos
POST /api/v1/processos                        → Criar processo
GET  /api/v1/processos/{id}                   → Detalhe + histórico
POST /api/v1/processos/{id}/avancar-workflow  → Avançar fase + prazos automáticos
GET  /api/v1/processos/{id}/prazos            → Prazos com análise de urgência
GET  /api/v1/notificacoes                     → Alertas de prazos críticos
GET  /api/v1/workflow/dashboard               → Visão agregada de prazos em risco
```

### Audiências

```
POST /api/v1/audiencias                       → Criar audiência
GET  /api/v1/audiencias/{id}/fases            → Estado das fases
POST /api/v1/audiencias/{id}/intervencao      → Submeter intervenção humana
POST /api/v1/audiencias/{id}/intervencao-ia   → Gerar intervenção com IA
POST /api/v1/audiencias/{id}/prova-ficheiro   → Apresentar prova (PDF/etc.)
POST /api/v1/audiencias/{id}/decidir          → Proferir decisão final
```

### Integrações Gov

```
GET  /api/v1/integracoes/dre/pesquisar        → Pesquisa no DRE
GET  /api/v1/integracoes/dre/vigencia         → Verificar artigo em vigor
GET  /api/v1/integracoes/jurisprudencia       → Pesquisa de acórdãos
GET  /api/v1/integracoes/jurisprudencia/norma → Acórdãos por norma
GET  /api/v1/integracoes/estado               → Estado de todas as integrações
```

---

## Limpeza do frontend (reset)

```
cd frontend
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
- [ ] Modo offline/soberano com modelo local
- [ ] App mobile (React Native)
- [ ] Certificação RGPD pela CNPD

---

## Licença

[MIT](LICENSE) — livre para usar, estudar, modificar e distribuir.

---

Desenvolvido por **Frederico Guilherme Sarmento Ferreira de Magalhães** e **Claude 4.6/Fable 5**

*"A justiça não pode ser um privilégio."*

---

*SNAJI — República Portuguesa · Construído com Python + FastAPI + React + TypeScript*
