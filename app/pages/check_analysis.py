"""Analysis Checker page — RAG-based fact-check for analytical text.

Accepts a block of text (e.g. a report excerpt or data-backed claim) and uses a
retrieval-augmented generation pipeline to identify potential contradictions with
the OSAA knowledge base stored in the local vectorstore.  Calls
``data_service.get_retriever`` for document retrieval and ``llm_service.get_llm``
for the LangChain LCEL chain.
"""

import streamlit as st
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from app.components.styles import page_header
from app.services.data_service import get_retriever
from app.services.llm_service import get_llm, get_selected_llm_name

if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "formatted_chat_history" not in st.session_state:
    st.session_state.formatted_chat_history = {}

chat_session_id = "check-analysis-chat-id"


def _clear_chat(session_id: str) -> None:
    if session_id in st.session_state.chat_history:
        st.session_state.chat_history[session_id].clear()
    st.session_state.formatted_chat_history = {}


def _display_chat(session_id: str) -> None:
    msgs = st.session_state.formatted_chat_history.get(session_id)
    if msgs is None:
        st.session_state.formatted_chat_history[session_id] = []
    else:
        for m in msgs:
            st.chat_message(m["role"]).markdown(m["content"])


def _format_docs(docs) -> str:
    parts = []
    for doc in docs:
        source = doc.metadata.get("source", "Unknown Source")
        page = doc.metadata.get("page", "Unknown Page")
        parts.append(f"Publication Name: {source}. Page Number: {page}. Content: {doc.page_content}")
    return "\n\n".join(parts)


page_header(
    "⚖️",
    "Analysis Checker",
    "Check whether your analysis contradicts previous OSAA publications using retrieval-augmented generation.",
    badge="RAG",
)

st.info(
    "Currently limited to the 2023 and 2024 NEPAD reports. "
    "More publications will be added soon. Always verify AI-generated results.",
    icon="ℹ️",
)

st.caption(f"Using: **{get_selected_llm_name()}**")
llm = get_llm()
retriever = get_retriever()

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Determine whether the provided analysis contradicts content from existing "
     "publications. Reference the publication name and page number. If unsure, "
     "provide the existing content for the user to decide."),
    ("human", "Provided analysis: {analysis}."),
    ("human", "Existing publication content: {context}."),
    ("system",
     "Based on the analysis and existing publications, does the analysis "
     "contradict anything? Provide quotes to support your reasoning."),
])

chain = (
    {"context": retriever | _format_docs, "analysis": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

messages_container = st.container()
with messages_container:
    _display_chat(chat_session_id)

if analysis := st.chat_input("Paste your analysis here..."):
    st.session_state.formatted_chat_history[chat_session_id].append({"role": "user", "content": analysis})
    messages_container.chat_message("user").markdown(analysis)

    gen = chain.stream(analysis)
    with messages_container:
        with st.chat_message("assistant"):
            try:
                response = st.write_stream(gen)
            except Exception as exc:
                response = f"An error occurred: {exc}"
                st.write(response)
    st.session_state.formatted_chat_history[chat_session_id].append({"role": "assistant", "content": response})

if st.button("Clear chat history", type="secondary", use_container_width=True):
    _clear_chat(chat_session_id)
    st.rerun()
