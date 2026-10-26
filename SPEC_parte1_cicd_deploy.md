# SPEC — Assistente de IA no ar (Parte 1: CI/CD e deploy)

**Status:** aprovada — implementação em andamento  
**Idioma do app e desta especificação:** português do Brasil  
**Base:** `IDEIA_parte1.md` e decisões confirmadas pelo responsável pelo projeto.

## 1. Objetivo, público e escopo

### Objetivo

Construir e publicar um chat de acesso público que responda, em português e de forma didática, dúvidas de alunos sobre Engenharia de Dados e Inteligência Artificial. A pessoa responsável pelo projeto poderá personalizar o assistente por um único arquivo YAML editado diretamente no GitHub.

O app aceitará credenciais dos três provedores — OpenRouter, Anthropic e OpenAI — e funcionará com qualquer um deles sozinho. O YAML determinará a ordem dos provedores e o modelo de cada um. Em cada conversa, o app tentará, em ordem, somente os provedores que tenham uma chave correspondente cadastrada nos Secrets do Hugging Face Spaces. Se uma chamada falhar, tentará o próximo provedor disponível. Se todos falharem, apresentará em português o motivo de cada falha, sem revelar credenciais.

### Público

- Alunos que querem tirar dúvidas introdutórias ou aprofundar conhecimentos de Engenharia de Dados e Inteligência Artificial.
- Responsável pelo projeto, que editará configuração e conteúdo sem precisar alterar código.

### Incluído nesta parte

- Interface de chat em Gradio, com cabeçalho, identidade visual, instruções, limite de resposta e botões de perguntas sugeridas.
- Integração individual com OpenRouter, Anthropic e OpenAI, com fallback pela ordem definida no YAML.
- Configuração do app em um único arquivo YAML versionado no GitHub.
- Chaves dos provedores guardadas somente como Secrets do Hugging Face Spaces.
- Validação automática da configuração, dos arquivos referenciados e de possíveis chaves expostas antes do deploy.
- Publicação automática no Hugging Face Spaces após alterações aprovadas na branch principal do GitHub.
- Testes locais automatizados sem chamadas pagas às APIs e roteiro de teste manual após configuração dos Secrets.

### Fora desta parte

- Base de conhecimento feita com documentos próprios (Parte 2).
- Domínio próprio e interface inteiramente personalizada fora dos componentes do Gradio (Parte 3).
- Login, perfis, histórico persistente ou compartilhamento de conversas.
- Escolha de modelo por quem usa o chat; essa decisão pertence ao YAML.
- Garantia de disponibilidade, créditos, gratuidade ou desempenho de qualquer provedor/modelo.

## 2. Stack escolhida e restrições do Hugging Face

### Stack

- **Linguagem:** Python 3.11.
- **Interface e servidor do chat:** Gradio, usando o SDK Gradio do Hugging Face Spaces.
- **Configuração:** um arquivo YAML chamado `config/assistant.yaml`. O YAML será lido e validado no início do app e também no pipeline antes de publicar.
- **Chamadas aos provedores:** HTTP por `requests`, com um adaptador separado para cada API. Isso evita que usar OpenRouter exija uma chave OpenAI ou que um provedor dependa da conta/chave de outro. Cada provedor precisa apenas da própria chave e do respectivo modelo configurado.
- **Validação de dados:** PyYAML e validações explícitas do projeto. Erros devem citar o campo que precisa ser corrigido.
- **Testes:** pytest, usando respostas simuladas. Os testes automatizados não usam chaves reais nem consomem créditos.
- **CI/CD:** GitHub Actions para validar e, se tudo passar, sincronizar os arquivos com o Space.
- **Hospedagem:** Hugging Face Spaces com SDK Gradio.

### Restrições e decisões de hospedagem

- O repositório do Space exige um `README.md` com metadados YAML do Hugging Face no início do arquivo, incluindo `sdk: gradio` e `app_file: app.py`. Esse bloco é distinto de `config/assistant.yaml`, que contém as opções do assistente.
- Dependências Python serão declaradas em `requirements.txt`; o Space instala essas dependências durante a construção.
- As credenciais das APIs serão configuradas manualmente em **Settings → Secrets** do Space com estes nomes exatos: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` e `OPENAI_API_KEY`. O código somente as lê do ambiente de execução. Não haverá arquivo `.env` com credenciais no repositório.
- O app não exigirá todas as chaves. Uma chave ausente desativa apenas seu provedor. Se nenhuma chave dos provedores listados estiver configurada, o app exibirá instruções para configurar pelo menos uma, sem tentar chamadas.
- O token usado pelo GitHub Actions para publicar no Space é diferente das chaves dos provedores. Ele será criado como token Hugging Face com permissão de escrita somente no Space e guardado nos GitHub Actions Secrets com o nome `HF_TOKEN`. Esse token não é colocado no código nem usado para chamadas de conversa.
- O Space é público para os usuários do chat; não deve conter chaves nem dados privados. Como não haverá login nem histórico, as conversas não serão salvas pelo app.
- A pipeline sincronizará o conteúdo do repositório GitHub com o Space. O conteúdo removido do GitHub também poderá ser removido do Space na sincronização; o GitHub será a fonte oficial dos arquivos.
- A gratuidade e os requisitos para executar Spaces Gradio podem mudar conforme plano e política do Hugging Face. Antes da implantação, o responsável deve confirmar na conta se pode criar/executar o Space no hardware pretendido.
- A pipeline deve usar versões fixadas ou controladas das Actions e dependências. Atualizações devem ser feitas conscientemente e verificadas por uma execução da CI.

### Fontes oficiais consultadas

- [Configuração dos Spaces](https://huggingface.co/docs/hub/en/spaces-config-reference) — metadados, SDK e arquivo principal.
- [Dependências em Gradio Spaces](https://huggingface.co/docs/hub/main/spaces-dependencies) — uso de `requirements.txt`.
- [Publicação de Spaces com GitHub Actions](https://huggingface.co/docs/hub/spaces-github-actions) — sincronização e secret `HF_TOKEN`.
- [Secrets do GitHub Actions](https://docs.github.com/en/actions/concepts/security/secrets) — armazenamento de segredo do token de publicação.

## 3. Estrutura de arquivos do projeto

### Situação verificada no GitHub

O repositório GitHub encontrado para este projeto é [`marcinhom/pos_ia_chatbot`](https://github.com/marcinhom/pos_ia_chatbot), branch padrão `main`. Na data desta especificação, o repositório está vazio; portanto, ainda não há arquivos ou diretórios reais para comparar com a proposta. O destino informado para publicação no Hugging Face é `marciomrcunha/chatbot_IA`. Os identificadores do GitHub e do Hugging Face são diferentes e devem ser tratados como repositórios de serviços distintos. A estrutura abaixo é uma estrutura inicial sugerida pela spec, não uma descrição de arquivos já existentes. A primeira tarefa deve confirmar o repositório/branch GitHub de trabalho e criar ou ajustar essa estrutura sem substituir arquivos preexistentes.

### Estrutura proposta

```text
.
├── .github/
│   └── workflows/
│       └── deploy-space.yml       # validação e publicação automática
├── assets/
│   └── logo.png                  # logo opcional, incluída no GitHub
├── config/
│   └── assistant.yaml            # único arquivo de configuração do assistente
├── tests/
│   ├── test_config.py            # campos, tipos e referências
│   ├── test_providers.py         # chamadas simuladas e fallback
│   └── test_chat.py              # integração simulada com a interface/lógica
├── app.py                        # interface Gradio e inicialização
├── config_loader.py              # leitura e validação do YAML
├── providers.py                  # adaptadores HTTP e seleção/fallback
├── requirements.txt              # dependências do Space
├── requirements-dev.txt          # dependências para testes e validação
├── README.md                     # metadados obrigatórios do Space + instruções
├── SPEC_parte1_cicd_deploy.md    # requisitos e plano aprovados do projeto
├── .gitignore                    # ignora caches, ambientes e arquivos locais
└── .gitleaks.toml                # regras/ajustes do detector de credenciais, se necessários
```

O único arquivo para personalização normal é `config/assistant.yaml`. O `README.md` também contém metadados técnicos obrigatórios do Space, mas não será usado para mudar personalidade, modelos ou cores do app. Nenhum arquivo de `sources/` deste espelho do projeto deve ser editado.

## 4. Contrato do arquivo de configuração

Arquivo: `config/assistant.yaml`. Campos desconhecidos, tipos incorretos, valores vazios em campos obrigatórios ou referências inválidas devem impedir a publicação, com mensagem clara em português indicando o campo e a correção esperada.

| Campo | Obrigatório | Tipo e valores aceitos | Padrão |
|---|---|---|---|
| `assistant.name` | Sim | Texto não vazio, até 60 caracteres | Sem padrão; precisa ser informado |
| `assistant.description` | Sim | Texto não vazio, até 180 caracteres | Sem padrão; precisa ser informado |
| `assistant.logo` | Não | Caminho relativo à raiz do repositório; arquivo PNG, JPG, JPEG ou WEBP existente dentro de `assets/`; ou `null` | `null` (mostrar ícone/nome sem imagem) |
| `assistant.logo_height_px` | Não | Número inteiro entre 24 e 160 | `64` |
| `appearance.primary_color` | Sim | Cor hexadecimal `#RRGGBB` | Sem padrão; precisa ser informada |
| `appearance.background_color` | Sim | Cor hexadecimal `#RRGGBB` | Sem padrão; precisa ser informada |
| `providers` | Sim | Lista ordenada de 1 a 3 entradas, sem provedor repetido | Sem padrão; precisa ser informada |
| `providers[].name` | Sim | Um de `openrouter`, `anthropic`, `openai` | Sem padrão |
| `providers[].model` | Sim | Texto não vazio com o identificador exato do modelo aceito pelo provedor indicado | Sem padrão |
| `generation.max_output_tokens` | Não | Inteiro de 1 a 1024; o app nunca solicitará mais de 1024 tokens de resposta | `1024` |
| `assistant.instructions` | Sim | Texto não vazio; instruções em português sobre papel, público, estilo e limites do assistente | Sem padrão; precisa ser informado |
| `assistant.example_questions` | Não | Lista de 0 a 6 textos não vazios, cada um com até 120 caracteres | `[]` |

### Regras adicionais do contrato

- A ordem da lista `providers` é a ordem de preferência e de fallback. A lista pode ter só um provedor. Todo provedor listado precisa ter o seu próprio `model`.
- As chaves **não são campos do YAML**. O mapeamento fixo é `openrouter` → `OPENROUTER_API_KEY`, `anthropic` → `ANTHROPIC_API_KEY`, `openai` → `OPENAI_API_KEY`.
- Se uma chave estiver ausente ou vazia, o respectivo provedor é ignorado e o app tenta o próximo que tenha chave. Se o provedor não estiver listado, não será usado, mesmo que haja chave cadastrada.
- É válido listar somente um provedor. Não é obrigatório listar os três. É inválido repetir o mesmo provedor na lista.
- Identificadores de modelo mudam ao longo do tempo e são específicos do provedor; a validação local pode verificar que o texto não está vazio, mas somente a API confirma se o nome/modelo está disponível para aquela conta.
- O `logo` é opcional. Se definido, a validação confirma que o caminho existe, está dentro de `assets/` e tem extensão permitida. Arquivo ausente ou caminho fora da pasta permitida bloqueia o deploy.
- O app aceitará somente cores hexadecimais de seis dígitos. A pipeline também verificará contraste suficiente entre texto e fundos usados pelo chat, com limite documentado e mensagem de correção.
- O limite de resposta desta versão é de até 1024 tokens. O padrão é 1024; se o YAML informar um valor menor, esse valor menor será respeitado. Valor maior que 1024 é inválido e bloqueia a publicação. Cada adaptador deve traduzir o limite para o parâmetro equivalente da API sem ultrapassar 1024.

## 5. Requisitos funcionais

- **RF1 — Abrir e conversar:** o usuário acessa um link público do Hugging Face Spaces e envia perguntas pelo chat.
- **RF2 — Idioma e didática:** toda a interface, mensagens de erro e instruções padrão são em português do Brasil. O assistente responde de forma didática ao público indicado no YAML.
- **RF3 — Personalizar cabeçalho e aparência:** nome, descrição, cores, logo opcional e altura da logo vêm do YAML.
- **RF4 — Perguntas sugeridas:** mostrar as perguntas de exemplo configuradas como botões clicáveis; não mostrar botões quando a lista estiver vazia.
- **RF5 — Usar instruções configuradas:** enviar as instruções de `assistant.instructions` ao provedor junto do contexto da conversa.
- **RF6 — Limitar resposta:** aplicar `generation.max_output_tokens` ao pedido de cada provedor conforme o parâmetro suportado por sua API.
- **RF7 — Três provedores independentes:** suportar chamadas diretas às APIs OpenRouter, Anthropic e OpenAI. Cada integração funciona quando apenas sua própria chave está configurada; nenhuma chave de outro provedor é requisito.
- **RF8 — Seguir ordem de preferência:** considerar os provedores na mesma ordem em que aparecem em `providers`.
- **RF9 — Ignorar provedor sem chave:** não enviar requisição a um provedor sem seu Secret correspondente; seguir para o próximo configurado.
- **RF10 — Tentar alternativa em falha:** diante de erro de rede, timeout, limite de uso, falta de crédito, indisponibilidade, modelo inválido ou outro erro de API, registrar a falha sanitizada e tentar o próximo provedor com chave.
- **RF11 — Informar falhas completas:** quando todos os provedores elegíveis falharem, exibir uma mensagem em português com o nome de cada provedor tentado e motivo compreensível retornado/classificado, sem chave, cabeçalho de autorização, conteúdo de segredo ou dado de configuração sensível.
- **RF12 — Tratar ausência de chaves:** quando nenhum provedor listado tiver chave, informar quais nomes de Secrets precisam ser adicionados nas configurações do Space; não tentar chamada externa.
- **RF13 — Tratar configuração inválida:** se a configuração não puder ser carregada ou validada, não iniciar o chat em estado enganoso; exibir/registrar erro claro de configuração e impedir a publicação pela CI.
- **RF14 — Não persistir conversas:** não gravar conversas em banco, arquivo ou analytics próprio; manter apenas o contexto necessário à sessão de chat ativa.
- **RF15 — Atualizar após push:** após push válido na branch principal, executar validação e atualizar o Space automaticamente.
- **RF16 — Preservar a publicação anterior em erro:** falha de validação impede o passo de sincronização. Uma sincronização com falha não deve ser relatada como publicada com sucesso; o Space que estava ativo deve continuar acessível conforme o comportamento de deploy do Hugging Face.
- **RF17 — Proteger credenciais:** não incluir chaves de provedor no código, YAML, logs, mensagens, artefatos da CI ou no repositório. Executar scanner de segredos na pipeline e bloquear quando detectar uma credencial.
- **RF18 — Exibir origem sem expor segredos:** em caso de sucesso, a interface pode informar qual provedor respondeu, sem exibir chave/token.

## 6. Verificações de testes funcionais

Os testes automatizados devem usar HTTP simulado e valores de chave falsos de teste. Não devem chamar provedores reais, usar créditos nem exigir Secrets reais. O teste manual de integração só ocorre depois da configuração de pelo menos uma chave no Space.

- **T1 — Configuração válida mínima:** validar um YAML válido com um único provedor e confirmar que a configuração é aceita.
- **T2 — Configuração inválida:** remover um campo obrigatório, trocar tipo ou informar uma cor inválida; confirmar erro que identifica o campo e bloqueio da validação.
- **T3 — Modelo de cada provedor:** configurar separadamente OpenRouter, Anthropic e OpenAI como provedor único; confirmar que cada adaptador pode ser selecionado sem exigir outras chaves.
- **T4 — Um provedor por vez em execução:** simular uma chave presente de cada vez e resposta bem-sucedida; confirmar que somente o provedor correspondente recebe requisição.
- **T5 — Provedor sem chave:** listar dois ou três provedores e disponibilizar apenas uma chave; confirmar que os demais são ignorados sem tentativa de chamada.
- **T6 — Ordem de preferência:** configurar dois provedores; fazer o primeiro responder com sucesso e confirmar que o segundo não é chamado.
- **T7 — Fallback por limite/sem crédito:** simular erro de limite ou saldo no primeiro e sucesso no segundo; confirmar tentativa na ordem e retorno da segunda resposta.
- **T8 — Fallback por indisponibilidade/rede:** simular timeout ou erro de serviço no primeiro e sucesso no seguinte; confirmar recuperação.
- **T9 — Falha de todos:** simular erros diferentes em todos os provedores elegíveis; confirmar que a mensagem lista cada nome e respectivo motivo, sem segredos.
- **T10 — Nenhuma chave:** não fornecer Secrets; confirmar instruções de configuração e nenhuma chamada externa.
- **T11 — Logo e cores:** testar logo existente, `logo: null`, caminho inexistente, caminho fora de `assets/`, extensão proibida e cor fora do formato; confirmar aceitação/rejeição esperada.
- **T12 — Perguntas sugeridas:** testar lista vazia e lista preenchida; confirmar ausência ou exibição dos botões e que clicar envia a pergunta.
- **T13 — Instruções e limite:** confirmar que a instrução configurada é enviada e o limite de tokens chega ao campo apropriado de cada API.
- **T14 — Varredura de segredos:** adicionar em branch de teste um padrão de chave fictícia reconhecido pelo scanner; confirmar falha antes de sincronizar o Space. Remover o padrão e confirmar sucesso.
- **T15 — Deploy automático:** fazer uma alteração válida na branch principal e confirmar execução sequencial de validação e sincronização; confirmar falha da validação impede publicação.
- **T16 — Interface em português:** conferir cabeçalho, placeholders, botões, estado inicial e mensagens de falha na interface.

## 7. Pipeline de deploy com GitHub Actions e configuração manual

### Fluxo automático

1. Disparar a pipeline em pull requests e em pushes para `main`.
2. Preparar Python 3.11 e instalar dependências de desenvolvimento fixadas.
3. Validar sintaxe e contrato de `config/assistant.yaml`, incluindo campos obrigatórios, lista e ordem de provedores, cores, números e unicidade.
4. Validar logo opcional e referências locais, garantindo que não apontem para fora de `assets/`.
5. Rodar os testes automatizados sem credenciais reais e sem chamadas à internet.
6. Rodar um scanner de segredos no conteúdo versionado (por exemplo, Gitleaks), bloqueando a publicação se detectar chave/token provável. A verificação precisa cobrir arquivos rastreados e o histórico relevante conforme a configuração adotada.
7. Somente em push válido na branch `main`, sincronizar os arquivos para o Space `marciomrcunha/chatbot_IA` com a Action oficial `huggingface/hub-sync`, ou mecanismo oficial equivalente escolhido na implementação. O destino padrão é `HF_SPACE_ID=marciomrcunha/chatbot_IA` (valor não secreto); o token de escrita será lido de `secrets.HF_TOKEN`.
8. Se qualquer passo anterior falhar, marcar o workflow como falho e não executar sincronização. Após sincronizar, acompanhar o estado de construção do Space e apresentar o resultado/link nos logs do workflow quando disponível.

### Configuração manual que o responsável precisa fazer

1. Confirmar ou criar o Space público `marciomrcunha/chatbot_IA` na conta Hugging Face indicada, com SDK Gradio.
2. Confirmar os limites/plano de execução atuais do Space Gradio na conta e selecionar hardware permitido.
3. No Space, abrir **Settings → Secrets** e adicionar uma ou mais chaves, usando os nomes exatos `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. Adicionar somente as chaves que realmente possui; nenhuma vai para o GitHub.
4. Criar no Hugging Face um token de acesso com escopo de escrita apenas no Space escolhido.
5. No repositório GitHub, em **Settings → Secrets and variables → Actions**, criar o Secret `HF_TOKEN` com esse token. Se a pipeline usar uma variável para o destino, criar `HF_SPACE_ID` com o valor `marciomrcunha/chatbot_IA`.
6. Confirmar que Actions estão habilitadas para o repositório e que a branch principal se chama `main`, ou ajustar o gatilho para o nome usado.
7. Enviar o conteúdo do projeto para o GitHub. Fazer primeiro um push/PR de validação; após CI verde, alterações em `main` serão publicadas automaticamente.
8. Abrir a URL do Space e realizar os testes manuais T4 e T16 com uma chave válida. Para provar fallback real, configurar dois provedores e provocar uma falha controlada no primeiro, sem expor chaves.

### Fronteira importante entre segredos

As chaves de conversa dos provedores vivem exclusivamente nos **Secrets do Hugging Face Space**. O único segredo que precisa estar no GitHub Actions é o token `HF_TOKEN` para a pipeline poder publicar no Space. Nunca copiar as chaves OpenRouter, Anthropic ou OpenAI para GitHub Secrets, YAML, workflow, issues ou logs.

## 8. Critérios de aceite

- [ ] O repositório tem a estrutura proposta ou uma estrutura equivalente documentada, sem sobrescrever arquivos existentes.
- [ ] O app inicia como Space Gradio e mostra nome, descrição e aparência do YAML.
- [ ] O arquivo `config/assistant.yaml` é o único lugar de personalização normal do assistente.
- [ ] Cada um dos três provedores funciona quando está sozinho e somente sua própria chave está configurada.
- [ ] A ordem configurada é respeitada e provedores sem chave são pulados.
- [ ] Erros do primeiro provedor causam tentativa no próximo; falhas totais mostram motivo por provedor em português.
- [ ] Nenhuma chave de API aparece no código, no YAML, no GitHub, nos logs ou na interface.
- [ ] A CI rejeita configuração incorreta, referência de logo quebrada e segredo detectável antes de publicar.
- [ ] Testes automatizados funcionam sem conexão com APIs e sem consumir créditos.
- [ ] Um push válido na branch principal atualiza o Space; uma validação malsucedida não sincroniza arquivos.
- [ ] Cabeçalho, chat, exemplos e mensagens de erro estão em português.
- [ ] Não há login nem persistência de conversas nesta parte.
- [ ] O README explica como editar o YAML, configurar Secrets e entender erros comuns em linguagem simples.
- [ ] O Space público abre e passa pelo roteiro de teste manual com ao menos um provedor.

## 9. Ordem das tarefas de implementação — uma tarefa por vez

Cada tarefa deve ser implementada e apresentada para revisão/teste antes de iniciar a seguinte. Depois da aprovação da SPEC, solicitar exatamente: **" Implemente a tarefa 1 da spec e me mostre como testar. "**

1. **Tarefa 1 — Confirmar e preparar a estrutura:** conferir o repositório GitHub real e a branch, criar estrutura base sem sobrescrever arquivos e acrescentar o README de Space, dependências iniciais, `.gitignore` e um YAML de configuração de exemplo válido. Se o repositório continuar vazio, estabelecer a estrutura proposta nesta SPEC.
2. **Tarefa 2 — Validador do YAML:** implementar leitura, regras do contrato, verificações de cores/logo e mensagens amigáveis; acrescentar testes T1, T2 e T11.
3. **Tarefa 3 — Adaptadores independentes:** implementar chamadas HTTP para OpenRouter, Anthropic e OpenAI, com tradução de formato de mensagens/limite; testar cada provedor isoladamente por simulação (T3, T4 e T13).
4. **Tarefa 4 — Fallback e diagnóstico:** implementar seleção pela ordem, ignorar chave ausente, classificar erros, sanitizar mensagens e acumular os motivos; testar T5 a T10 e T18.
5. **Tarefa 5 — Interface Gradio:** montar cabeçalho, aparência, exemplos clicáveis e chat sem persistência; testar T12 e T16.
6. **Tarefa 6 — Testes integrados e segurança:** completar testes simulados e scanner de segredos, corrigindo qualquer vazamento ou lacuna; testar T14.
7. **Tarefa 7 — CI de validação:** criar workflow de pull request/push para instalar ambiente, validar YAML, rodar testes e scanner, ainda sem publicação automática; confirmar que falhas bloqueiam o job.
8. **Tarefa 8 — Publicação automática:** adicionar sincronização em `main`, documentar `HF_TOKEN` e `HF_SPACE_ID` e confirmar que só publica após CI verde (T15).
9. **Tarefa 9 — Configuração e teste no Hugging Face:** criar/configurar Space e Secrets manualmente, verificar construção, testar chamada real de um provedor e, se houver duas chaves disponíveis, fallback controlado.
10. **Tarefa 10 — Revisão de aceite e guia final:** percorrer todos os critérios, atualizar instruções para iniciante, listar limitações observadas e entregar os passos de manutenção.

## 10. Erros comuns e como resolver

| Erro | Causa provável | Como resolver |
|---|---|---|
| A CI diz que falta campo ou que o tipo está incorreto | YAML incompleto ou recuo incorreto | Abrir `config/assistant.yaml`, conferir o nome do campo, os dois-pontos e o recuo indicado na mensagem da CI. YAML usa espaços; não usar tabulação. |
| A CI rejeita a cor | Cor fora do padrão aceito | Usar seis dígitos hexadecimais, por exemplo `#1A2B3C`, incluindo `#` e aspas se necessário. |
| A CI não encontra a logo | Caminho incorreto, arquivo não enviado ou extensão não permitida | Colocar a imagem em `assets/`, conferir maiúsculas/minúsculas e atualizar o caminho relativo no YAML; ou usar `null`. |
| O app diz que nenhum provedor tem chave | Secret ausente, nome diferente ou sem provedor com chave na lista | No Settings do Space, cadastrar o Secret com o nome exato do provedor e reiniciar/reconstruir o Space se necessário. Confirmar que esse provedor aparece em `providers`. |
| O modelo não é encontrado | Identificador incorreto, removido ou indisponível para a conta | Conferir o nome do modelo na documentação/painel do provedor e corrigir o valor `model` associado a ele no YAML. |
| O primeiro provedor falha e não há resposta | Nenhum próximo provedor listado tem chave válida ou todos falharam | Ver a mensagem sanitizada do chat; confirmar ordem, Secrets, crédito/limites e nomes de modelo. |
| O scanner bloqueia um commit | Uma chave real pode ter sido versionada ou texto parece uma credencial | Não copiar o valor para logs. Remover a chave do arquivo, revogar/rotacionar imediatamente qualquer credencial real exposta e então limpar o histórico do Git conforme necessário antes de publicar. |
| O workflow não encontra `HF_TOKEN` | Secret do deploy ausente, com nome errado ou sem permissão | Criar/atualizar `HF_TOKEN` em GitHub Actions Secrets com token Hugging Face de escrita no Space correto. |
| A sincronização vai ao Space errado | `HF_SPACE_ID` aponta para outro nome/organização | Corrigir a variável para `conta-ou-organizacao/nome-do-space` e confirmar o destino antes do próximo deploy. |
| A CI passa, mas o Space falha ao construir | Dependência/versão incompatível, metadado do Space errado ou erro de inicialização | Abrir os logs de build do Space e corrigir a dependência, `README.md` ou erro citado; fazer novo push e acompanhar a CI. |
| A resposta excede ou ignora o limite esperado | Os provedores interpretam limites de tokens de forma diferente | Verificar o limite máximo aceito pelo provedor, ajustar `generation.max_output_tokens` e confirmar o parâmetro específico do adaptador. |
| O Space Gradio não pode iniciar no plano atual | Limite ou requisito de assinatura/hardware alterado pelo Hugging Face | Conferir a página atual de Settings/planos e selecionar uma opção disponível para a conta antes de repetir o deploy. |
| Conversas desaparecem ao recarregar | Persistência não faz parte desta versão | Isso é esperado nesta parte; histórico salvo ou conta exigem definição e implementação posterior. |

---

**Fim da SPEC — aprovada pelo responsável; implementação iniciada pela Tarefa 1.**

