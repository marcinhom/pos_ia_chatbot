---
title: Assistente de Engenharia de Dados e IA
emoji: 💬
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
---

# Assistente de Engenharia de Dados e IA

Chat didático em português sobre Engenharia de Dados e Inteligência Artificial.

## Situação do projeto

O app, os três provedores de IA, a interface, os testes automatizados e a validação contínua estão implementados. A Tarefa 8 acrescenta publicação automática: depois que uma alteração aprovada chega à branch `main`, o GitHub Actions valida o projeto e, se essa validação passar, sincroniza os arquivos com o Space `marciomrcunha/chatbot_IA`.

## Personalização

As opções do assistente ficam em `config/assistant.yaml`. Edite esse arquivo pelo GitHub para ajustar nome, descrição, cores, logo, provedores, modelos, instruções e perguntas sugeridas.

O modelo OpenRouter do arquivo de exemplo foi copiado da ideia inicial do projeto. Confira se ainda está disponível na sua conta antes de usar; nomes e disponibilidade de modelos podem mudar.

## Chaves de API dos provedores

As chaves usadas pelo chat devem ser cadastradas somente em **Settings → Secrets** do Hugging Face Space:

- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Cadastre apenas as chaves dos provedores que pretende usar. Nunca coloque uma chave no YAML, no código ou em arquivos do GitHub.

## Configurar a publicação automática

O repositório GitHub publica no Space por meio de dois valores nas configurações do próprio repositório:

1. Em **Settings → Secrets and variables → Actions → Secrets**, crie o Secret `HF_TOKEN`. Use um token Hugging Face com permissão de escrita somente no Space `marciomrcunha/chatbot_IA`.
2. Na mesma página, abra **Variables** e crie a variável `HF_SPACE_ID` com o valor `marciomrcunha/chatbot_IA`. Esse nome de conta e Space não é segredo.
3. Confirme que o Space existe, é público, usa SDK Gradio e tem o arquivo `README.md` com os metadados acima.
4. Em **Settings → Secrets** do Space, cadastre as chaves de API que deseja usar, com os nomes listados na seção anterior.

O `HF_TOKEN` autoriza apenas a publicação. Ele não substitui as chaves das APIs e não deve ser usado como chave do chat.

## Como a validação e publicação funcionam

- Em um pull request, o GitHub instala Python 3.11, valida `config/assistant.yaml`, executa os testes e procura credenciais expostas. O Space não é alterado.
- Quando o pull request é aprovado e integrado em `main`, a mesma validação é executada. Somente depois de todos os passos passarem o GitHub Actions sincroniza os arquivos com o Space.
- A sincronização copia o conteúdo do repositório e também reflete remoções. O GitHub é a fonte oficial dos arquivos do projeto.
- Depois da sincronização, o Hugging Face constrói e inicia o Space. Confira **Actions** no GitHub e **App → Logs** nas configurações do Space para acompanhar o resultado.
- Se a validação falhar, a etapa de publicação não roda. Se `HF_TOKEN` ou `HF_SPACE_ID` estiver ausente/incorreto, a publicação falha com uma mensagem de configuração.

## Executar e validar localmente

Requer Python 3.11 ou compatível. Na pasta do projeto:

1. Instale as dependências de desenvolvimento com `python -m pip install -r requirements-dev.txt`.
2. Valide a configuração com `python config_loader.py`.
3. Execute os testes com `python -m pytest -q`.
4. Verifique possíveis credenciais com `gitleaks git . --config .gitleaks.toml --redact`.
5. Para abrir o app localmente, execute `python app.py` e abra o endereço informado pelo Gradio.

Os testes automatizados simulam as respostas dos provedores; eles não precisam de chaves reais nem consomem créditos. Para conferir a publicação de verdade, use a aba **Actions** do GitHub e abra o Space em https://huggingface.co/spaces/marciomrcunha/chatbot_IA.

