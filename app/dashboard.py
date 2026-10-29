
from pathlib import Path

import requests
import pandas as pd
import streamlit as st

API_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 10
CHAT_TIMEOUT = 120

st.set_page_config(
    page_title="StockMind AI",
    page_icon="📦",
    layout="wide",
)

st.title("📦 StockMind AI")
st.caption(
    "Inteligência artificial aplicada ao monitoramento de estoque"
)


def api_get(endpoint: str, timeout: int = REQUEST_TIMEOUT):
    response = requests.get(
        f"{API_URL}{endpoint}",
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def show_api_error(error: requests.RequestException):
    if isinstance(error, requests.HTTPError):
        response = error.response

        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text

        st.error(f"Erro da API: {detail}")
    else:
        st.error(
            "Não foi possível conectar à API. "
            "Confira se o FastAPI está funcionando na porta 8000."
        )


def get_chat_error_message(error: requests.RequestException) -> str:
    """Converte erros da API em mensagens compreensíveis para o usuário."""
    if isinstance(error, requests.HTTPError):
        status_code = (
            error.response.status_code
            if error.response is not None
            else None
        )

        if status_code == 502:
            return (
                "O serviço de IA não conseguiu gerar uma resposta. "
                "Isso pode acontecer quando a cota do Gemini acaba "
                "ou o serviço fica temporariamente indisponível. "
                "Confira o terminal da API para identificar a causa."
            )

        if status_code == 503:
            return (
                "O serviço de IA está temporariamente indisponível. "
                "Tente novamente mais tarde."
            )

        if status_code == 422:
            return (
                "A pergunta ou o histórico enviado não foi aceito "
                "pela API. Tente enviar uma pergunta mais curta."
            )

        return f"A API retornou o erro HTTP {status_code}."

    return (
        "Não foi possível conectar à API. "
        "Verifique se o FastAPI está funcionando."
    )


# Inicializa o estado da sessão.
if "ai_report" not in st.session_state:
    st.session_state["ai_report"] = ""

if "stockmind_chat" not in st.session_state:
    st.session_state["stockmind_chat"] = []

if "stockmind_chat_error" not in st.session_state:
    st.session_state["stockmind_chat_error"] = ""


# Carrega os dados atualizados a cada execução do dashboard.
try:
    inventory = api_get("/inventory")
    analysis_data = api_get("/inventory/analyze")
    summary = api_get("/inventory/summary")
    movements = api_get("/movements?limit=10")

except requests.RequestException as error:
    show_api_error(error)
    st.stop()


# Indicadores principais.
st.subheader("📊 Indicadores do estoque")

col1, col2, col3 = st.columns(3)
col1.metric("Produtos cadastrados", summary["total_products"])
col2.metric("Unidades em estoque", summary["total_units"])
col3.metric("Produtos com estoque baixo", summary["low_stock"])

col4, col5, col6 = st.columns(3)
col4.metric("Produtos vencidos", summary["expired_products"])
col5.metric(
    "Vencimento em até 30 dias",
    summary["expiring_within_30_days"],
)
col6.metric(
    "Produtos com alertas",
    analysis_data["items_with_risks"],
)

st.divider()


# Visão geral do estoque.
risk_labels = {
    "LOW_STOCK": "Estoque baixo",
    "EXPIRING_SOON": "Vencimento próximo",
    "EXPIRED": "Produto vencido",
    "OVERSTOCK": "Estoque elevado",
}

st.subheader("📋 Visão geral do estoque")

results = analysis_data["results"]
df = pd.DataFrame(results)

if df.empty:
    st.info("Não existem itens cadastrados.")
else:
    df["risk_description"] = df["risks"].apply(
        lambda risks: ", ".join(
            risk_labels.get(risk, risk) for risk in risks
        ) if risks else "Sem alertas"
    )

    df["status"] = df["risks"].apply(
        lambda risks: "Atenção" if risks else "Normal"
    )

    selected_status = st.selectbox(
        "Filtrar itens",
        ["Todos", "Atenção", "Normal"],
    )

    filtered_df = df.copy()

    if selected_status != "Todos":
        filtered_df = filtered_df[
            filtered_df["status"] == selected_status
        ]

    display_df = filtered_df[
        [
            "name",
            "quantity",
            "minimum_quantity",
            "days_until_expiration",
            "risk_description",
            "status",
        ]
    ].rename(
        columns={
            "name": "Produto",
            "quantity": "Quantidade",
            "minimum_quantity": "Estoque mínimo",
            "days_until_expiration": "Dias até vencimento",
            "risk_description": "Alertas",
            "status": "Situação",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("📈 Quantidade por produto")
    chart_df = df[["name", "quantity"]].set_index("name")
    st.bar_chart(chart_df)


st.divider()


# Previsão de consumo com Machine Learning.
st.subheader("🔮 Previsão de consumo (Machine Learning)")
st.write(
    "Consulte a previsão de consumo gerada pelo modelo Random Forest. "
    "As previsões usam dados históricos sintéticos e servem para demonstração."
)

product_options = {
    1: "Luvas descartáveis",
    2: "Seringas descartáveis",
    3: "Máscaras cirúrgicas",
    4: "Gazes esterilizadas",
    5: "Álcool 70%",
}

forecast_col1, forecast_col2 = st.columns([3, 2])

with forecast_col1:
    selected_product_id = st.selectbox(
        "Produto para previsão",
        options=list(product_options.keys()),
        format_func=lambda product_id: product_options[product_id],
        key="forecast_product_id",
    )

with forecast_col2:
    forecast_horizon = st.slider(
        "Dias para prever",
        min_value=1,
        max_value=30,
        value=7,
        key="forecast_horizon",
    )

try:
    forecast_data = api_get(
        f"/ml/forecast/{selected_product_id}?horizon={forecast_horizon}",
        timeout=REQUEST_TIMEOUT,
    )

    forecast_records = forecast_data.get("forecast", [])
    forecast_df = pd.DataFrame(forecast_records)

    if forecast_df.empty:
        st.info("A API não retornou previsões para este produto.")
    else:
        forecast_df["date"] = pd.to_datetime(forecast_df["date"])
        forecast_df["predicted_consumption"] = pd.to_numeric(
            forecast_df["predicted_consumption"],
            errors="coerce",
        )
        forecast_df = forecast_df.dropna(
            subset=["date", "predicted_consumption"]
        )

        total_predicted = float(
            forecast_data.get(
                "total_predicted_consumption",
                forecast_df["predicted_consumption"].sum(),
            )
        )
        average_predicted = float(
            forecast_df["predicted_consumption"].mean()
        )

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Produto", product_options[selected_product_id])
        metric_col2.metric(
            f"Consumo previsto em {forecast_horizon} dias",
            f"{total_predicted:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )
        metric_col3.metric(
            "Média prevista por dia",
            f"{average_predicted:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )

        # Combina os últimos 30 dias históricos com o período previsto.
        history_path = (
            Path(__file__).resolve().parent.parent
            / "ml"
            / "data"
            / "historical_consumption.csv"
        )

        if history_path.exists():
            history_df = pd.read_csv(history_path, parse_dates=["date"])
            product_history = history_df[
                history_df["product_id"] == selected_product_id
            ].sort_values("date").tail(30)

            chart_parts = []

            if not product_history.empty:
                historical_chart = product_history[
                    ["date", "consumption"]
                ].rename(columns={"consumption": "Consumo histórico"})
                chart_parts.append(historical_chart)

            forecast_chart = forecast_df[
                ["date", "predicted_consumption"]
            ].rename(
                columns={"predicted_consumption": "Consumo previsto"}
            )
            chart_parts.append(forecast_chart)

            combined_chart = pd.concat(
                chart_parts,
                ignore_index=True,
                sort=False,
            ).sort_values("date").set_index("date")

            st.markdown("#### Histórico recente e previsão")
            st.line_chart(combined_chart, use_container_width=True)
            st.caption(
                "O histórico mostra os últimos 30 dias disponíveis; "
                "a previsão começa após a última data do conjunto de dados."
            )
        else:
            st.info(
                "O arquivo de histórico não foi encontrado. "
                "A previsão continua disponível, mas o gráfico comparativo "
                "não pode ser exibido."
            )

        st.markdown("#### Valores previstos por dia")
        table_df = forecast_df[
            ["date", "predicted_consumption"]
        ].rename(
            columns={
                "date": "Data",
                "predicted_consumption": "Consumo previsto",
            }
        )
        table_df["Data"] = table_df["Data"].dt.strftime("%d/%m/%Y")
        table_df["Consumo previsto"] = table_df["Consumo previsto"].round(2)
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
        )

except requests.RequestException as error:
    st.warning(
        "Não foi possível carregar a previsão de consumo. "
        "Confira se a API está ativa e se o endpoint de previsão está disponível."
    )
    with st.expander("Detalhes do erro"):
        show_api_error(error)
except (KeyError, TypeError, ValueError) as error:
    st.error(
        "A resposta de previsão não está no formato esperado. "
        f"Detalhes: {error}"
    )


st.divider()


# Registro de movimentações.
st.subheader("🔄 Movimentações de estoque")
st.write(
    "Registre entradas ou saídas. A API atualiza o saldo "
    "e mantém o histórico da operação."
)

if not inventory:
    st.info("Cadastre um produto antes de registrar movimentações.")
else:
    inventory_by_id = {
        item["id"]: item for item in inventory
    }

    with st.form("movement_form"):
        selected_item_id = st.selectbox(
            "Produto",
            options=list(inventory_by_id.keys()),
            format_func=lambda item_id: (
                f'{inventory_by_id[item_id]["name"]} '
                f'(saldo: {inventory_by_id[item_id]["quantity"]})'
            ),
        )

        movement_label = st.selectbox(
            "Tipo de movimentação",
            ["Entrada", "Saída"],
        )

        movement_quantity = st.number_input(
            "Quantidade",
            min_value=1,
            step=1,
            value=1,
        )

        movement_reason = st.text_input(
            "Motivo",
            placeholder="Ex.: reposição de estoque",
            max_chars=250,
        )

        movement_submitted = st.form_submit_button(
            "Registrar movimentação",
            type="primary",
        )

    if movement_submitted:
        if len(movement_reason.strip()) < 3:
            st.error("Informe um motivo com pelo menos 3 caracteres.")
        else:
            movement_type = (
                "IN" if movement_label == "Entrada" else "OUT"
            )

            try:
                response = requests.post(
                    f"{API_URL}/inventory/"
                    f"{selected_item_id}/movements",
                    json={
                        "movement_type": movement_type,
                        "quantity": int(movement_quantity),
                        "reason": movement_reason.strip(),
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()

                st.success("Movimentação registrada com sucesso!")
                st.rerun()

            except requests.RequestException as error:
                show_api_error(error)


# Histórico de movimentações.
st.subheader("🧾 Histórico recente")

if not movements:
    st.info("Nenhuma movimentação registrada até o momento.")
else:
    movements_df = pd.DataFrame(movements)
    movements_df["Tipo"] = movements_df["movement_type"].map(
        {"IN": "Entrada", "OUT": "Saída"}
    )

    history_df = movements_df[
        [
            "created_at",
            "item_name",
            "Tipo",
            "quantity",
            "reason",
            "balance_after",
        ]
    ].rename(
        columns={
            "created_at": "Data (UTC)",
            "item_name": "Produto",
            "quantity": "Quantidade movimentada",
            "reason": "Motivo",
            "balance_after": "Saldo após movimentação",
        }
    )

    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# Exclusão controlada.
st.subheader("🗑️ Exclusão de produto")
st.warning(
    "Produtos com movimentações registradas não podem ser excluídos, "
    "para preservar o histórico de auditoria."
)

if not inventory:
    st.info("Não existem produtos para excluir.")
else:
    with st.form("delete_form"):
        delete_item_id = st.selectbox(
            "Selecione o produto",
            options=[item["id"] for item in inventory],
            format_func=lambda item_id: (
                f'{inventory_by_id[item_id]["name"]} '
                f'(ID: {item_id})'
            ),
        )

        confirm_delete = st.checkbox(
            "Confirmo que desejo excluir este produto."
        )

        delete_submitted = st.form_submit_button(
            "Excluir produto",
        )

    if delete_submitted:
        if not confirm_delete:
            st.error("Marque a confirmação antes de excluir.")
        else:
            try:
                response = requests.delete(
                    f"{API_URL}/inventory/{delete_item_id}",
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()

                st.success("Produto excluído com sucesso.")
                st.rerun()

            except requests.RequestException as error:
                show_api_error(error)


st.divider()


# Relatório de IA.
st.subheader("📑 Relatório de IA")
st.write(
    "Gere um relatório com explicações dos riscos identificados "
    "e sugestões de ações para revisão."
)

if st.button("Gerar análise com IA", type="primary"):
    with st.spinner("Analisando os dados com Gemini..."):
        try:
            report_data = api_get(
                "/inventory/ai-analysis",
                timeout=CHAT_TIMEOUT,
            )

            st.session_state["ai_report"] = report_data["report"]

        except requests.RequestException as error:
            show_api_error(error)

if st.session_state["ai_report"]:
    st.markdown("### Relatório gerado")
    st.markdown(st.session_state["ai_report"])


st.divider()


# Chat interativo com o assistente.
st.subheader("🤖 Chat interativo com o StockMind AI")
st.write(
    "Faça perguntas em linguagem natural sobre o estoque atual, "
    "os alertas e as prioridades de conferência."
)

st.info(
    "O assistente utiliza os dados atuais do estoque. "
    "As respostas dependem da disponibilidade da API Gemini."
)

chat_col1, chat_col2 = st.columns([4, 1])

with chat_col2:
    if st.button("Limpar conversa", use_container_width=True):
        st.session_state["stockmind_chat"] = []
        st.session_state["stockmind_chat_error"] = ""
        st.rerun()


# Exibe as mensagens anteriores.
for message in st.session_state["stockmind_chat"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Exibe erros da última tentativa sem interromper o dashboard.
if st.session_state["stockmind_chat_error"]:
    st.warning(st.session_state["stockmind_chat_error"])


# Campo de entrada do chat.
question = st.chat_input(
    "Ex.: Quais produtos precisam de atenção urgente?"
)

if question:
    question = question.strip()

    if not question:
        st.warning("Digite uma pergunta antes de enviar.")
    else:
        # Mantém a conversa visível, mesmo se a API falhar.
        st.session_state["stockmind_chat"].append(
            {
                "role": "user",
                "content": question,
            }
        )

        st.session_state["stockmind_chat_error"] = ""

        # A API aceita no máximo 10 mensagens de histórico.
        # Não envia a pergunta atual como parte do histórico,
        # pois ela será enviada separadamente no campo question.
        previous_messages = [
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in st.session_state["stockmind_chat"][:-1]
            if message["role"] in ("user", "assistant")
        ][-10:]

        with st.spinner("O StockMind está analisando sua pergunta..."):
            try:
                response = requests.post(
                    f"{API_URL}/inventory/chat",
                    json={
                        "question": question,
                        "history": previous_messages,
                    },
                    timeout=CHAT_TIMEOUT,
                )
                response.raise_for_status()

                answer_data = response.json()
                answer = answer_data.get("answer")

                if not answer:
                    raise ValueError(
                        "A API não retornou uma resposta em texto."
                    )

                st.session_state["stockmind_chat"].append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

            except requests.RequestException as error:
                st.session_state["stockmind_chat_error"] = (
                    get_chat_error_message(error)
                )

            except ValueError as error:
                st.session_state["stockmind_chat_error"] = (
                    f"Não foi possível interpretar a resposta: {error}"
                )

        st.rerun()


st.caption(
    "Projeto demonstrativo com dados fictícios. "
    "Os alertas e as sugestões devem ser revisados por um responsável "
    "pelo estoque. As respostas do assistente não substituem essa revisão."
)
