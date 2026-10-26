"""Interface do assistente Gradio configurada por ``config/assistant.yaml``."""

from __future__ import annotations

import gradio as gr

from chat import answer_message
from config_loader import AssistantConfig, load_config


def _styles(config: AssistantConfig) -> str:
    """Aplica as duas cores validadas pelo config_loader."""
    return f"""
    .gradio-container {{ background: {config.background_color} !important; }}
    #assistant-heading {{
        background: {config.primary_color};
        color: #FFFFFF;
        border-radius: 0.75rem;
        padding: 1rem;
    }}
    #assistant-heading h1, #assistant-heading p {{ color: #FFFFFF !important; }}
    """


def create_demo(config: AssistantConfig | None = None) -> gr.Blocks:
    """Monta a interface sem iniciar servidor, o que permite testá-la."""
    assistant_config = config or load_config()

    with gr.Blocks(
        title=assistant_config.name,
        css=_styles(assistant_config),
        theme=gr.themes.Soft(),
    ) as demo:
        with gr.Row(elem_id="assistant-heading"):
            if assistant_config.logo_path is not None:
                gr.Image(
                    value=str(assistant_config.logo_path),
                    label="Logo do assistente",
                    height=assistant_config.logo_height_px,
                    width=assistant_config.logo_height_px,
                    show_label=False,
                    show_download_button=False,
                    show_fullscreen_button=False,
                    container=False,
                    interactive=False,
                )
            with gr.Column():
                gr.Markdown(f"# {assistant_config.name}")
                gr.Markdown(assistant_config.description)

        gr.ChatInterface(
            fn=lambda message, history: answer_message(message, history, config=assistant_config),
            type="messages",
            chatbot=gr.Chatbot(
                type="messages", label="Conversa", height=480, allow_tags=False
            ),
            textbox=gr.Textbox(
                placeholder="Escreva sua pergunta e pressione Enviar...",
                label="Sua pergunta",
                lines=2,
                max_lines=6,
            ),
            examples=list(assistant_config.example_questions) or None,
            cache_examples=False,
            submit_btn="Enviar",
            stop_btn="Parar",
            save_history=False,
        )

    return demo


demo = create_demo()


if __name__ == "__main__":
    demo.queue().launch()
