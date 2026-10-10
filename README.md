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

A estrutura inicial do Space está preparada. A interface e as integrações com OpenRouter, Anthropic e OpenAI serão concluídas nas próximas tarefas.

## Personalização

As opções do assistente ficam em `config/assistant.yaml`. Edite esse arquivo pelo GitHub para ajustar nome, descrição, cores, logo, provedores, modelos, instruções e perguntas sugeridas.

O modelo OpenRouter do arquivo de exemplo foi copiado da ideia inicial do projeto. Confira se ainda está disponível na sua conta antes de usar; nomes e disponibilidade de modelos podem mudar.

## Chaves de API

As chaves de conversa devem ser cadastradas somente em **Settings → Secrets** do Hugging Face Space:

- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Cadastre apenas as chaves dos provedores que pretende usar. Nunca coloque uma chave no YAML, no código ou em arquivos do GitHub.

O token de publicação usado futuramente pelo GitHub Actions é outro segredo: `HF_TOKEN`, guardado nos Secrets do GitHub. Ele serve apenas para publicar no Space.

## Executar localmente

Requer Python 3.11 ou compatível:

1. Instale as dependências com `pip install -r requirements.txt`.
2. Inicie com `python app.py`.
3. Abra o endereço local informado pelo Gradio.

Esta tela inicial ainda não envia perguntas a provedores de IA.
