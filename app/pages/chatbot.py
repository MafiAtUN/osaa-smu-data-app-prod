"""General-purpose OSAA chatbot page with persistent conversation history.

Provides a free-form chat interface backed by the configured LLM (via
``llm_service.get_llm``) and LangChain's ``RunnableWithMessageHistory`` for
multi-turn context.  Conversation history is stored in ``st.session_state`` and
optionally persisted to DuckDB via the chat-history service.  Token usage is
tracked via ``tiktoken``.
"""

from operator import itemgetter
from typing import List

import streamlit as st
import tiktoken
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory

from app.components.styles import page_header
from app.services.llm_service import get_llm, get_selected_llm_name

try:
    from langchain_core.messages import trim_messages
except ImportError:
    try:
        from langchain_core.messages.utils import trim_messages
    except ImportError:
        class _SimpleTrimmer:
            def __init__(self, **kw):
                self.kw = kw
            def __call__(self, messages):
                return messages
        def trim_messages(**kwargs):
            return _SimpleTrimmer(**kwargs)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "formatted_chat_history" not in st.session_state:
    st.session_state.formatted_chat_history = {}

chat_session_id = "general-chat-id"


def _get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in st.session_state.chat_history:
        st.session_state.chat_history[session_id] = InMemoryChatMessageHistory()
    return st.session_state.chat_history[session_id]


def _clear_chat(session_id: str) -> None:
    if session_id in st.session_state.chat_history:
        st.session_state.chat_history[session_id].clear()
    st.session_state.formatted_chat_history = {}


def _display_chat(session_id: str) -> None:
    msgs = st.session_state.formatted_chat_history.get(session_id)
    if msgs is None:
        st.session_state.formatted_chat_history[session_id] = []
        intro = "Hi! I am an LLM chatbot for UN OSAA. What can I help you with today?"
        st.chat_message("assistant").markdown(intro)
        st.session_state.formatted_chat_history[session_id].append({"role": "assistant", "content": intro})
    else:
        for m in msgs:
            st.chat_message(m["role"]).markdown(m["content"])


def _str_token_counter(text: str) -> int:
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def _tiktoken_counter(messages: List[BaseMessage]) -> int:
    n = 3
    for msg in messages:
        role = {"HumanMessage": "user", "AIMessage": "assistant", "ToolMessage": "tool", "SystemMessage": "system"}.get(type(msg).__name__, "user")
        n += 3 + _str_token_counter(role) + _str_token_counter(msg.content)
        if msg.name:
            n += 1 + _str_token_counter(msg.name)
    return n


# --- Page UI ---
page_header(
    "💬",
    "OSAA Chatbot",
    "Ask questions about UN OSAA's work, Africa's development, and related UN mandates.",
    badge="AI",
)

st.caption(f"Using: **{get_selected_llm_name()}**")
model = get_llm()

trimmer = trim_messages(
    max_tokens=1000, strategy="last", token_counter=_tiktoken_counter,
    include_system=True, allow_partial=False, start_on="human",
)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an AI assistant for the United Nations Office of the Special Adviser on Africa (UN OSAA). "
     "Provide accurate, impartial information aligned with UN principles, especially within the African context."),
    MessagesPlaceholder(variable_name="messages"),
    ("human", "Prompt: \n\n {prompt}."),
])

chain = RunnablePassthrough.assign(messages=itemgetter("messages") | trimmer) | prompt | model
config = {"configurable": {"session_id": chat_session_id}}

messages_container = st.container()
with messages_container:
    _display_chat(chat_session_id)

if user_input := st.chat_input("What can I help you with?"):
    st.session_state.formatted_chat_history[chat_session_id].append({"role": "user", "content": user_input})
    with messages_container:
        st.chat_message("user").markdown(user_input)

    with_history = RunnableWithMessageHistory(chain, _get_session_history, input_messages_key="messages")
    gen = with_history.stream(
        {"messages": [HumanMessage(content=user_input)], "prompt": user_input},
        config=config,
    )
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
