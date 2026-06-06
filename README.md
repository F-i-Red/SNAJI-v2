<div align="center">

# ⚖️ SNAJI
### Sistema Nacional de Assistência Jurídica Inteligente

**IA jurídica soberana para Portugal — construída por um cidadão, para todos os cidadãos.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)
[![Tests](https://img.shields.io/badge/Testes-138%20passing-brightgreen?style=flat)]()

</div>

---

## O que é o SNAJI?

O SNAJI não é um chatbot com leis coladas. É um **sistema processual inteligente** que acompanha o cidadão, o advogado e o magistrado em cada fase do processo judicial português — com fundamentação real, integridade garantida e soberania de dados.

Desenvolvido integralmente em Portugal, por uma pessoa, com legislação portuguesa real como base de conhecimento.

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

## Arquitetura

```
SNAJI
├── backend/
│   └── app/
│       ├── agents/          # Agentes de IA especializados
│       ├── api/             # Endpoints REST (FastAPI)
│       ├── audiencias/      # Motor de simulação de audiências
│       ├── core/            # Configuração e utilitários centrais
│       ├── db/              # Modelos e acesso à base de dados
│       ├── documents/       # Gestão documental
│       ├── generation/      # Geração de texto jurídico
│       ├── integrations/    # Integrações externas (DRE, etc.)
│       ├── notifications/   # Sistema de notificações
│       ├── orchestrator/    # Orquestração de workflows
│       ├── processes/       # Lógica de processos judiciais
│       ├── rag/             # Retrieval-Augmented Generation
│       ├── reasoning/       # Módulo de raciocínio jurídico
│       ├── security/        # Autenticação, RBAC, integridade
│       └── workflow/        # Motor de estados processuais
│
└── frontend/
    └── src/
        ├── auth/            # Autenticação e sessão
        ├── components/      # Componentes React reutilizáveis
        ├── pages/           # Páginas por perfil de utilizador
        ├── services/        # Clientes de API
        ├── styles/          # Estilos globais
        └── types/           # Tipos TypeScript
```

**Stack:**  FastAPI · PostgreSQL · Redis · React 18 · Vite · Docker

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

---

## Testes

```bash
cd backend
pytest                    # todos os testes
pytest tests/ -v          # com output detalhado
pytest --cov=app tests/   # com cobertura
```

**138 testes** — cobrindo RAG, workflow, segurança, audiências e geração.

---

## Roadmap

- [ ] Vector store híbrido (BM25 + embeddings `bge-m3`)
- [ ] Geração de PDF processual com cabeçalho de tribunal
- [ ] Modo colaboração (advogado + cliente em simultâneo)
- [ ] Análise comparativa de acórdãos semelhantes
- [ ] Exportação de dossiê completo (processo + documentos + decisão)
- [ ] Integração com CITIUS / SISAAE
- [ ] Dark mode

---

## Contexto

O SNAJI nasceu da convicção de que o acesso à justiça não pode depender da capacidade financeira do cidadão. Em Portugal, a distância entre os direitos consagrados e o seu exercício efectivo é ainda demasiado grande.

Este projeto foi desenvolvido individualmente, com recurso ao assistente de IA **Claude Pro (Anthropic)** — cuja subscrição anual foi o único custo direto do projeto. É, em si mesmo, uma demonstração do que um cidadão pode construir quando tem acesso às ferramentas certas.

---

## Licença

[MIT](LICENSE) — livre para usar, estudar, modificar e distribuir.

---

<div align="center">

Desenvolvido por **Frederico Guilherme Sarmento Ferreira de Magalhães**

*"A justiça não pode ser um privilégio."*

</div>
