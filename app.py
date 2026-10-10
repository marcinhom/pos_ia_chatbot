"""Tela inicial provisória do Space; as integrações serão implementadas nas próximas tarefas."""

import gradio as gr


with gr.Blocks(title="Assistente de Engenharia de Dados e IA") as demo:
    gr.Markdown("# Assistente de Engenharia de Dados e IA")
    gr.Markdown(
        "A estrutura inicial está pronta. O chat e as integrações com os provedores "
        "serão ativados nas próximas tarefas."
    )


if __name__ == "__main__":
    demo.launch()
