# SNAJI — Especificação V8.1
## Adenda à Especificação V8: estado de implementação, parecer externo e roadmap pós-PoC

Versão: 8.1 · Data: 4 de julho de 2026 · Complementa (não substitui) o documento `ESPECIFICACAO_V8.md`

---

## 1. Estado de implementação do roadmap V8 (§9)

| # | Componente | Estado | Números reais |
|---|---|---|---|
| 1 | **AgenteInstrutor** (intake por compreensão) | ✅ Em produção | Perguntas mistas (escolha/texto/data/valor), 3 famílias de alertas (prazos, via não judicial, apoio judiciário), Ficha de Factos estruturada; backend + API + página do cidadão |
| 2 | **Corpus legislativo — Escalão 1** | ✅ Completo | **6.770 artigos** de 12 diplomas integrais (CRP, CC, CPC, CP, CPP, CT, CPA, CIRE, CSC, RGPD, LDC, LJP), 7,1 MB, com deteção automática de lacunas, remoção de duplicados corrompidos e marcação de revogados |
| 3 | **Motor de Audiências V2** | ✅ Em produção | 11 papéis processuais; últimas declarações do arguido (art. 361.º CPP); ordem legal das alegações imposta pelo motor; regime de adesão (art. 71.º CPP); atas do escrivão em cadeia de hash verificável |
| 4 | **Motor de Cenários + saída dupla** | ✅ Em produção | 3 lentes (garantista/legalista/consequencialista), regra da convergência, solidez qualitativa, registo técnico + linguagem clara, validação anti-alucinação por cenário; página com interruptor de registo |
| 5 | **Jurisprudência real** | ✅ Operacional | **13 Acórdãos Uniformizadores reais do STJ** (segmentos integrais verificados; laboral, civil, penal, família, crédito, seguros, custas), pipeline dgsi→JSON com validação de normas contra o corpus, cruzamento bidirecional acórdão↔norma; aviso explícito nos logs se dados de demonstração estiverem em uso |
| 6 | **Módulo Analista** | ✅ Backend + API | Registo analítico anonimizado por desenho; observatório da conflitualidade, **índice de incerteza jurídica** (divergência das lentes), groundedness; k-anonimato (contagens <3 mascaradas); RBAC `VER_METRICAS` |
| 7 | Guião de demonstração | ⏳ Próximo | 3 casos ensaiados (laboral, misto penal+civil com adesão, consumo com via arbitral) |

**Novidade transversal (V8.1): Explicabilidade.** Qualquer análise de cenários pode ser pedida com `explicar: true`, devolvendo o percurso completo em 6 etapas: entrada → recuperação de normas (com pontuações de relevância) → geração das lentes (motor identificado) → validação anti-alucinação (citações validadas e rejeitadas, por lente) → regras de viabilidade/convergência → derivação da saída dupla. Responde diretamente aos deveres de transparência e rastreabilidade do Regulamento (UE) 2024/1689 (AI Act) para sistemas de alto risco.

Qualidade de engenharia: todos os módulos correm em dois modos (LLM pleno / determinístico de contingência), com mecanismo anti-corte de respostas (verificação de `stop_reason` com continuação automática) e testes de ponta a ponta executados sobre a aplicação completa.

---

## 2. Parecer técnico externo — triagem

O projeto foi submetido a escrutínio técnico externo (avaliação de arquitetura: 8,5–9/10). A triagem que se segue distingue o que **já existe** (o parecer avaliou a estrutura, não o código), o que é **aceite** para o roadmap, e o que é **recusado com fundamento**.

### 2.1 Apontado como em falta, mas já implementado
| Sugestão do parecer | Realidade no código |
|---|---|
| "Falta citar as fontes em toda a resposta" | Toda a análise cita normas **validadas letra a letra contra o corpus**; citações inexistentes são rejeitadas e exibidas ao utilizador; jurisprudência identificada por AUJ/processo |
| "Prompts por perfil (cidadão/advogado/magistrado)" | Saída dupla técnica/linguagem clara com regra de coerência (a versão cidadã deriva da técnica); deontologia codificada por papel (informar vs. prescrever) |
| "Reasoning baseado em agentes com supervisor" | 11 agentes processuais com instruções próprias no Motor de Audiências; AgenteInstrutor; orchestrator como supervisor — a extensão a agentes por área do direito é incremental sobre a arquitetura existente |
| "Explicabilidade do percurso" | Implementada na V8.1 (ver §1) |
| "Pesquisa híbrida BM25+embeddings" | Premissa invertida no parecer: a base atual é BM25 (não embeddings); a hibridização é **adicionar** a camada vetorial (ver §3) |
| Embrião de knowledge graph | Cruzamento bidirecional acórdão↔norma já operacional (`acordaos_por_norma`) |

### 2.2 Aceite — condicionado ao acesso institucional aos dados
| Sugestão | Posição | Condição |
|---|---|---|
| Pipeline automático DRE → parser → versionamento → vetores | **Aceite; é o desenho-alvo do §5.1 da V8** | Pedido institucional n.º 1 (legislação consolidada, DGPJ/AMA). Sem ele, "automático" = scraping frágil de fontes que bloqueiam robôs; os ficheiros de texto atuais são o andaime honesto do PoC, não o destino |
| Recolha automática de jurisprudência (STJ, TC, STA, Relações, TJUE, TEDH) | **Aceite como destino** | Pedido institucional n.º 2 (IGFEJ/dgsi). Até lá, pipeline manual curado (AUJ primeiro — qualidade sobre quantidade) |
| Versionamento temporal da lei + timeline "o que mudou neste artigo" | **Aceite; campos já previstos no processador** | Requer as redações históricas — vem com o pedido n.º 1 |

### 2.3 Aceite — roadmap técnico pós-PoC (sem dependências externas)
1. **Base vetorial** (pgvector — já consta do `requirements.txt`) + **pesquisa híbrida** BM25 + embeddings PT + re-ranking. Gatilho: crescimento do corpus para o Escalão 2 (~50 diplomas); com 6.770 artigos, o BM25 serve o PoC com folga.
2. **Agentes especializados por área do direito** (penal, laboral, civil, administrativo, europeu…) com supervisor — extensão do padrão `INSTRUCOES_AGENTES` existente.
3. **Knowledge graph jurídico** (norma revoga/altera norma; acórdão interpreta norma) — evolução natural dos metadados já recolhidos (revogados, contexto estrutural, normas citadas nos AUJ).
4. **Analisador de peças** (upload → verificação de todas as citações contra o corpus e vigência) — reutiliza o ValidadorCitacoes; já constava do levantamento de necessidades do perfil advogado.
5. **Templates adicionais** (explicar artigo, comparar redações, preparar audiência).
6. Painel visual do módulo Analista no frontend.

### 2.4 Recusado — com fundamento
| Sugestão | Fundamento da recusa |
|---|---|
| "Confiança: 96%" em cada resposta | **Falsa precisão.** Nenhum modelo distingue 94% de 96% em análise jurídica, mas o cidadão acreditará que sim e o magistrado desprezará quem finge saber. Mantém-se a solidez **qualitativa** (elevada/média/baixa) com riscos explicitados — decisão de produto deliberada e defensável |
| Gerador de peças processuais (contestação, petição, recurso) | **Risco deontológico** (atos próprios — Lei n.º 49/2004): como gerador de peças para juntar a processos, mobilizaria a Ordem dos Advogados contra o projeto. Admissível apenas como **minutas-tipo educativas**, claramente assinaladas |
| Scraping direto e imediato de todas as bases de tribunais | Método errado para o destino certo: as fontes bloqueiam acesso automatizado; a via é institucional (ver §4) |

---

## 3. Prioridades pós-PoC (ordem)
1. Acesso institucional aos dados (desbloqueia §2.2 por inteiro).
2. Pipeline automático de legislação com versionamento temporal.
3. Camada vetorial + pesquisa híbrida (Escalão 2 do corpus).
4. Analisador de peças + agentes por área.
5. Knowledge graph + timeline jurídica.
6. Workflow de processos paralelos e prejudicialidade (casos mistos entre tribunais — complemento do regime de adesão já implementado).

---

## 4. Pedidos institucionais (formulação pronta para a reunião)

**Pedido n.º 1 — Legislação consolidada.** "Para o proof of concept, solicitamos acesso aos dados da legislação consolidada do Diário da República (interlocução: DGPJ/AMA), destinado a alimentar o pipeline de atualização automática do corpus normativo, com versionamento temporal das redações."

**Pedido n.º 2 — Jurisprudência.** "Solicitamos acesso aos dados das bases jurídico-documentais do dgsi.pt (interlocução: IGFEJ), começando pelos acórdãos dos tribunais superiores, para indexação com validação cruzada contra o corpus normativo."

Nota estratégica: o sistema **já funciona sem estes acessos** (corpus integral do Escalão 1 e 13 AUJ reais em produção) — os pedidos aceleram e automatizam; não condicionam a demonstração. Esta independência é, em si, um argumento de maturidade.

---

*Documento para integração no repositório (sugestão: `docs/ESPECIFICACAO_V8.1.md`, ao lado da V8) e para apresentação institucional.*
