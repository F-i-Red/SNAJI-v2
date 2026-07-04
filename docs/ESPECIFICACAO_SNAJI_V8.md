# SNAJI — Especificação V8
## Sistema Nacional de Assistência Jurídica Inteligente

**Documento de especificação funcional e técnica**
Versão: 8.0 · Data: 3 de julho de 2026 · Estado: em desenvolvimento para Proof of Concept (Ministério da Justiça)

---

## 0. Enquadramento e limites deontológicos

O SNAJI presta **informação jurídica** de carácter geral e apoio à preparação e organização processual. O SNAJI **não presta consulta jurídica nem patrocínio**, atos reservados por lei a advogados e solicitadores (Lei n.º 49/2004, de 24 de agosto). Nenhum resultado produzido por este sistema substitui o aconselhamento de um profissional habilitado, nem constitui decisão judicial ou ato jurisdicional (arts. 202.º e 203.º da CRP).

Nos termos do Regulamento (UE) 2024/1689 (AI Act), os sistemas de IA utilizados na administração da justiça são classificados de **alto risco**: o SNAJI é desenhado para apoio cognitivo com supervisão humana efetiva, registo de auditoria integral e explicabilidade de cada resultado.

**Regras deontológicas codificadas por perfil:**
- Modo **Cidadão**: o sistema informa ("casos com estas características seguem tipicamente a via X"), nunca prescreve ("deve processar Y"). Remete sempre para profissional habilitado e, quando aplicável, para o apoio judiciário.
- Modo **Advogado/Magistrado**: acesso a ferramentas técnicas completas; o sistema apresenta fontes e argumentos contrapostos, nunca "a resposta certa".
- Modo **Juiz**: o sistema nunca formula recomendação decisória; apresenta síntese dos autos, normas, jurisprudência e argumentos de ambas as partes, com registo auditável de tudo o que foi exibido.

---

## 1. AgenteInstrutor (módulo de intake por compreensão)

Substitui a entrada de texto livre por um diálogo estruturado de instrução do caso, **antes** da classificação final e do RAG.

**Ciclo de funcionamento (inspirado no diagnóstico diferencial):**
1. O cidadão descreve o caso livremente.
2. O agente gera hipóteses jurídicas iniciais (via ClassificadorJuridico multi-área).
3. Identifica as lacunas de facto que confirmam ou eliminam cada hipótese:
   - **datas** → prescrição, caducidade, prazos de impugnação;
   - **existência e forma de contrato** → validade, prova;
   - **valor do dano/pedido** → alçada, competência, admissibilidade de recurso;
   - **identidade e qualidade das partes** → legitimidade;
   - **provas disponíveis** → documentos, testemunhas, perícias;
   - **local dos factos / domicílio** → competência territorial.
4. Faz **uma pergunta de cada vez**, escolhendo a que mais reduz a incerteza.
5. Atualiza a classificação e a confiança após cada resposta.
6. Termina quando: confiança ≥ limiar (ex.: 0,85) **ou** orçamento de perguntas esgotado (5–7 perguntas).

**Saída:** Ficha de Factos estruturada (partes, cronologia, relação jurídica, provas, danos, pedidos) — é esta ficha, e não o desabafo original, que alimenta o RAG e a pipeline de reasoning.

**Alertas prioritários do Instrutor** (mostrados antes de qualquer análise):
- alerta de prazo em risco ou expirado (a informação mais valiosa para o cidadão);
- alerta de via não judicial (crime → Ministério Público/órgão de polícia criminal; consumo → centro de arbitragem; dados pessoais → CNPD);
- alerta de apoio judiciário (encaminhamento para a Segurança Social quando há insuficiência de meios).

---

## 2. Motor de Cenários de Resolução

Para cada caso analisado, o sistema gera **até três cenários** de resolução, correspondentes a três lentes interpretativas reais da prática judiciária:

| Cenário | Lente | Pergunta orientadora |
|---|---|---|
| **Garantista** | Máxima proteção dos direitos fundamentais e garantias processuais | "Qual a solução que melhor protege a parte mais fraca e as garantias constitucionais?" |
| **Legalista / Positivista** | Aplicação estrita da letra da lei | "O que diz exatamente a norma, sem extensão interpretativa?" |
| **Consequencialista / Pragmático** | Ponderação dos efeitos práticos; orientação da jurisprudência maioritária | "Como têm os tribunais efetivamente decidido casos análogos, e com que efeitos?" |

**Regras do motor:**
- Só são apresentados os cenários **juridicamente viáveis**. Se apenas 1 ou 2 lentes produzem solução sustentável, apresentam-se apenas essas.
- Se as três lentes **convergem**, apresenta-se uma única solução com a indicação expressa "as três abordagens convergem" (sinal de caso juridicamente claro).
- Cada cenário inclui: fundamentação normativa (artigos verificados no corpus), jurisprudência de suporte (quando existente), riscos e contra-argumentos, e grau qualitativo de solidez (não percentagens — evita falsa precisão).
- No modo Cidadão, os cenários são informativos e nunca formulados como recomendação de ação.

---

## 3. Saída dupla: registo técnico + linguagem clara

Toda a análise é produzida em **dois registos simultâneos**, a partir da mesma fundamentação (mesmos factos, mesmas normas, mesmas citações — muda apenas a linguagem):

- **Registo técnico**: qualificação jurídica, normas com diploma/artigo/número, jurisprudência com ECLI, vias processuais próprias.
- **Registo cidadão** (linguagem clara): frases curtas, sem latinismos nem jargão ("exceção perentória" → "um argumento que, a provar-se, faz o pedido cair"), com glossário de termos clicável.

Regra de coerência: o registo cidadão é gerado **a partir do técnico** (nunca de forma independente) e validado pelo mesmo mecanismo anti-alucinação, para impedir divergência de conteúdo entre os dois.

---

## 4. Pesquisa direta por artigo e versionamento temporal

- Pesquisa imediata por referência exata: "art. 483.º CC", "art. 351.º CT", "art. 71.º CPP".
- Devolve: texto integral do artigo, epígrafe, diploma, estado de vigência, alterações sofridas.
- **Versionamento temporal**: cada artigo é armazenado com intervalo de vigência (`vigente_de`, `vigente_ate`, `redacao_dada_por`). O utilizador pode pedir a redação **em vigor à data dos factos** — essencial para advogados (a lei aplicável a um contrato de 2019 é a redação de 2019).
- Cada consulta devolve também a fonte oficial (ligação DRE) para verificação humana.

---

## 5. Corpus legislativo e jurisprudencial

### 5.1 Legislação — por escalões
- **Escalão 1 (PoC, ~15 MB de texto, ~8.000 artigos):** CRP, CC, CPC, CP, CPP, CT, CPA, CIRE, Código das Sociedades Comerciais, RGPD/Lei 58/2019, Lei de Defesa do Consumidor, Lei dos Julgados de Paz.
- **Escalão 2 (~40–60 MB):** os ~50 diplomas mais usados na prática forense (arrendamento, estrada, IRC/IRS/IVA e LGT, imigração, contraordenações, registo e notariado, etc.).
- **Fonte:** versões consolidadas do Diário da República (diariodarepublica.pt). Em contexto de PoC ministerial, **solicitar à DGPJ/AMA acesso oficial aos dados da legislação consolidada** — pedido a formular no primeiro contacto.
- O ficheiro `dre.py` atual usa endpoints não oficiais e cai sistematicamente para o corpus local: será substituído por um atualizador com fonte oficial e relatório de sincronização (diplomas novos, alterados e revogados desde a última execução), com aprovação humana antes da integração de cada alteração no corpus.

### 5.2 Jurisprudência — estratégia de prestígio primeiro
- **Fase 1:** Acórdãos Uniformizadores de Jurisprudência (AUJ) do STJ e acórdãos de fixação de jurisprudência penal — poucas centenas de documentos, valor jurídico máximo (vinculam a orientação dos tribunais).
- **Fase 2:** acórdãos do STJ e do Tribunal Constitucional dos últimos 10 anos nas áreas cobertas.
- **Fase 3:** Relações (por área e por necessidade).
- **Fonte:** dgsi.pt (IGFEJ) e tribunalconstitucional.pt; identificação por **ECLI** (identificador europeu de jurisprudência) para citação inequívoca.

### 5.3 Arquitetura de dados (JSON + vetorial)
```
texto bruto (DRE/dgsi) → corpus.json (fonte de verdade, auditável)
                        → índice vetorial (embeddings PT) para pesquisa semântica
```
- O **JSON permanece a fonte de verdade**: é contra ele que o ValidadorCitacoes confirma cada citação letra a letra. O índice vetorial serve para *encontrar*; o JSON serve para *provar*.
- Embeddings em português (modelos PT-nativos já identificados no projeto); índice FAISS local no PoC, com migração para pgvector/PostgreSQL na versão institucional.
- Chunking por artigo (legislação) e por sumário + segmentos de fundamentação (acórdãos).
- Cada chunk transporta metadados: diploma/tribunal, artigo/ECLI, vigência, data, área jurídica, fonte oficial.

---

## 6. Qualidade de geração (fim das frases cortadas)

- Limites de geração elevados nas análises longas (4.000–8.000 tokens conforme a etapa).
- Verificação obrigatória do `stop_reason` de cada resposta do LLM:
  - se `max_tokens` → o sistema pede automaticamente a continuação ("continua exatamente de onde paraste") e concatena, até obter `end_turn`;
  - limite de segurança de continuações (ex.: 4) com registo em log.
- Nenhuma resposta é apresentada ao utilizador sem terminação natural confirmada.

---

## 7. Intervenientes processuais — matriz completa (lugar e tempo de ação)

### 7.1 Novos papéis a acrescentar ao motor de audiências
| Papel | Função no sistema |
|---|---|
| **Assistente** (penal) | Vítima/ofendido constituído como colaborador do MP (arts. 68.º–69.º CPP); pode aderir à acusação, requerer prova e alegar após o MP |
| **Testemunha** | Depõe na fase de prova; sujeita a juramento; inquirida por quem a arrolou e contrainterrogada pela parte contrária |
| **Perito** | Apresenta e esclarece relatório pericial na fase de prova |
| **Demandante/Demandado civil** (penal) | Partes do pedido de indemnização civil enxertado (princípio da adesão, art. 71.º CPP) |
| **Escrivão / Oficial de justiça** | Lavra a ata de cada ato; no SNAJI é o agente que produz o registo auditável (encaixa na cadeia de hash existente) — presente em todas as fases, sem intervenção argumentativa |
| **Defensor oficioso** | Regra de substituição: a defesa nunca pode estar ausente; se o arguido não constitui mandatário, o sistema instancia defensor nomeado |
| **Intérprete** | Interveniente transversal, ativado quando uma parte não domina o português (art. 92.º CPP); ajuramentado na abertura |

### 7.2 Sequência penal (audiência de julgamento) — fases e quem age
| # | Fase | Intervêm | Notas de regra |
|---|---|---|---|
| 1 | Abertura | Juiz; Escrivão (ata); Intérprete (ajuramentação, se necessário) | Identificação das partes, objeto do processo |
| 2 | Acusação / Pedido | MP; Assistente (adesão); Demandante civil (pedido de indemnização) | Princípio da adesão: o pedido civil entra aqui |
| 3 | Contestação / Defesa | Defesa (mandatário ou defensor oficioso); Demandado civil | A defesa nunca está ausente |
| 4 | Réplica | MP / Assistente | Uma vez |
| 5 | Produção de prova | Testemunhas **da acusação primeiro, depois da defesa**; Peritos; declarações do arguido (se aceitar prestá-las — direito ao silêncio, sem desfavor) | Inquirição por quem arrolou → contrainterrogatório → esclarecimentos do juiz |
| 6 | Perguntas do juiz | Juiz ↔ qualquer interveniente | Loop até esclarecimento |
| 7 | Alegações finais | **Ordem legal: MP → Assistente → Demandante civil → Defesa** | A defesa fala sempre em último |
| 8 | **Últimas declarações do arguido** | Arguido | **Art. 361.º CPP — o arguido tem sempre a última palavra.** Fase nova a acrescentar ao motor |
| 9 | Deliberação | Juiz (interno) | — |
| 10 | Decisão | Juiz; Escrivão (notificação e depósito) | Sentença fundamentada: matéria de facto separada da matéria de direito |

### 7.3 Sequência civil (declarativa) — fases e quem age
| # | Fase | Intervêm | Notas |
|---|---|---|---|
| 1 | Petição inicial | Autor (mandatário) | Validação de pressupostos: legitimidade, competência, valor da causa |
| 2 | Citação | Escrivão → Réu | Prazo de contestação: 30 dias (art. 569.º CPC) |
| 3 | Contestação (e eventual reconvenção) | Réu | — |
| 4 | Audiência prévia / Saneador | Juiz; mandatários | Tentativa de conciliação; fixação do objeto do litígio e temas da prova |
| 5 | Audiência final — prova | Testemunhas; Peritos; **declarações de parte** | Regras de inquirição como no penal |
| 6 | Alegações | Autor → Réu | — |
| 7 | Sentença | Juiz; Escrivão | Facto e direito separados; admissibilidade de recurso em função da alçada |

### 7.4 Casos mistos — regimes de conjugação
1. **Adesão** (art. 71.º CPP): o pedido civil corre dentro do processo penal — uma audiência, duas decisões (penal + indemnizatória).
2. **Processos paralelos apensados**: áreas com tribunais distintos (ex.: penal + laboral); partilha de factos provados entre processos.
3. **Prejudicialidade**: um processo suspende a aguardar a decisão do outro.
O ClassificadorJuridico multi-área determina o regime; o motor de audiências instancia a tramitação correspondente.

---

## 8. Módulo Analista (DGPJ / gestão) — brainstorm consolidado

Perfil novo, sem acesso a casos individuais identificáveis — **anonimização por desenho**.

**Observatório da conflitualidade**
- Volumes de casos por área jurídica, evolução temporal, sazonalidade;
- Distribuição geográfica (comarca/distrito) — mapa de calor da litigância;
- Deteção de padrões emergentes (ex.: pico súbito de casos de arrendamento numa região; novo tipo de burla digital) com alertas automáticos;
- Temas em crescimento vs. em declínio (janelas móveis de 30/90/365 dias).

**Apoio à decisão política e legislativa**
- Simulação de impacto: "que percentagem dos casos analisados seria afetada pela alteração do art. X?";
- Identificação de zonas cinzentas da lei (casos em que o sistema devolve baixa confiança ou cenários fortemente divergentes — indicador objetivo de incerteza jurídica);
- Relatórios exportáveis (PDF/CSV) alinhados com os indicadores estatísticos da justiça (DGPJ/Estatísticas da Justiça).

**Qualidade e operação do próprio sistema**
- Taxa de groundedness (respostas com todas as citações validadas) e taxa de citações rejeitadas;
- Taxa de fallback (LLM → heurística; DRE → corpus local);
- Cobertura do corpus (áreas pedidas vs. áreas cobertas — orienta o crescimento do escalão 2);
- Latência, custo por análise, perguntas médias do Instrutor até classificação estável;
- Estado da sincronização legislativa (última atualização, diplomas pendentes de aprovação humana).

**Privacidade**
- Agregação mínima (k-anonimato: nenhum indicador é mostrado abaixo de um número mínimo de casos);
- Sem dados pessoais no armazém analítico; RGPD por defeito; registo de auditoria de acessos do próprio analista.

---

## 9. Ordem de implementação
1. **AgenteInstrutor** (`backend/app/reasoning/agente_instrutor.py`) + mecanismo anti-corte (§6) — desbloqueia tudo o resto.
2. **Corpus escalão 1** (textos integrais + processador robusto + versionamento) e pesquisa direta por artigo (§4, §5.1).
3. **Motor de audiências V2**: novos papéis, fase de últimas declarações, regimes de casos mistos (§7).
4. **Motor de Cenários** + saída dupla técnica/cidadão (§2, §3).
5. **Jurisprudência fase 1 (AUJ)** + índice vetorial (§5.2, §5.3).
6. **Módulo Analista** (§8).
7. **Guião de demonstração** para o Ministério (3 casos ensaiados: um laboral simples, um misto penal+civil com adesão, um de consumo com via arbitral).

---

*Documento preparado para integração no repositório SNAJI (sugestão: `docs/ESPECIFICACAO_V8.md`) e para apresentação institucional.*
