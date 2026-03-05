"""Local data access: DuckDB databases, vectorstore, and file uploads."""

from __future__ import annotations

import os

import duckdb
import numpy as np
import pandas as pd
import streamlit as st

from app.core.logging import get_logger
from app.services.llm_service import create_azure_embeddings

logger = get_logger(__name__)

DB_PATH = "content/db.duckdb"
VECTORSTORE_PATH = "content/vectorstore.duckdb"
CSV_DIR = "content/data"

# ---------------------------------------------------------------------------
# DuckDB helpers
# ---------------------------------------------------------------------------


def setup_db() -> str:
    """Create the DuckDB database with seed data if it does not exist."""
    if os.path.exists(DB_PATH):
        return DB_PATH

    conn = duckdb.connect(database=DB_PATH, read_only=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY, name TEXT)"
    )

    countries = [
        "Nigeria", "Kenya", "South Africa", "Ghana", "Egypt",
        "Morocco", "Ethiopia", "Tanzania", "Uganda", "Algeria",
    ]
    years = list(range(2000, 2024))
    country_data = {
        c: {
            "base_population": np.random.randint(10_000_000, 50_000_000),
            "population_growth": np.random.uniform(1.01, 1.03),
            "base_gdp": np.random.randint(10_000_000_000, 200_000_000_000),
            "gdp_growth": np.random.uniform(1.02, 1.05),
            "total_land": np.random.randint(150_000, 500_000),
        }
        for c in countries
    }
    rows = []
    for c in countries:
        cd = country_data[c]
        for i, y in enumerate(years):
            pop = cd["base_population"] * (cd["population_growth"] ** i)
            gdp = cd["base_gdp"] * (cd["gdp_growth"] ** i) + np.random.uniform(-0.05, 0.05) * cd["base_gdp"]
            arable = np.random.uniform(0.2, 0.4) * cd["total_land"]
            urban = np.random.uniform(0.05, 0.15) * cd["total_land"]
            forest = cd["total_land"] - arable - urban
            rows.append({
                "Country": c, "Year": y, "Population": int(pop), "GDP": int(gdp),
                "Arable Land (km2)": int(arable), "Urban Land (km2)": int(urban),
                "Forest Land (km2)": int(forest),
            })
    df_test = pd.DataFrame(rows)  # noqa: F841 — used by DuckDB SQL below
    conn.execute("DROP TABLE IF EXISTS test_dataset")
    conn.execute("CREATE TABLE test_dataset AS SELECT * FROM df_test")
    conn.execute("INSERT INTO metadata (id, name) VALUES (?, ?)", (0, "test_dataset"))

    if os.path.exists(CSV_DIR):
        for idx, csv_file in enumerate(f for f in os.listdir(CSV_DIR) if f.endswith(".csv")):
            df = pd.read_csv(os.path.join(CSV_DIR, csv_file))  # noqa: F841 — used by DuckDB SQL below
            table_name = os.path.splitext(csv_file)[0]
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
            conn.execute("INSERT INTO metadata (id, name) VALUES (?, ?)", (idx + 1, table_name))

    conn.close()
    return DB_PATH


def refresh_db(db_path: str) -> None:
    """Delete and recreate the database."""
    if os.path.isfile(db_path):
        os.remove(db_path)
    setup_db()


def get_dataset_names(db_path: str) -> list[str]:
    conn = duckdb.connect(database=db_path, read_only=True)
    result = conn.execute("SELECT name FROM metadata").fetchall()
    conn.close()
    return [row[0] for row in result]


def get_df(db_path: str, name: str) -> pd.DataFrame:
    conn = duckdb.connect(database=db_path, read_only=True)
    df = conn.execute(f"SELECT * FROM {name}").df()
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Vectorstore (RAG)
# ---------------------------------------------------------------------------


def get_retriever(db_path: str = VECTORSTORE_PATH):
    """Return a LangChain retriever backed by the DuckDB vectorstore."""
    from langchain_community.vectorstores.duckdb import DuckDB

    embedding_model = create_azure_embeddings()
    conn = duckdb.connect(
        database=db_path,
        read_only=False,
        config={
            "enable_external_access": "false",
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
        },
    )
    vectorstore = DuckDB(connection=conn, embedding=embedding_model)
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 6})


def make_vectorstore() -> None:
    """(Re)create the vectorstore and load PDF documents into it."""
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores.duckdb import DuckDB
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    embedding_model = create_azure_embeddings()
    conn = duckdb.connect(
        database=VECTORSTORE_PATH,
        read_only=False,
        config={
            "enable_external_access": "false",
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
        },
    )
    vectorstore = DuckDB(connection=conn, embedding=embedding_model)

    doc_dir = "content/rag_documents"
    if not os.path.exists(doc_dir):
        logger.warning("RAG document directory not found: %s", doc_dir)
        return

    pdf_files = [f for f in os.listdir(doc_dir) if f.endswith(".pdf")]
    progress = st.progress(0, text="Adding documents")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    for i, pdf_file in enumerate(pdf_files):
        doc = PyPDFLoader(os.path.join(doc_dir, pdf_file)).load()
        splits = splitter.split_documents(doc)
        source_name = os.path.splitext(pdf_file)[0]
        for s in splits:
            page = s.metadata.get("page", "Unknown Page")
            if isinstance(page, int):
                page += 1
            s.metadata = {"source": source_name, "page": page}
        vectorstore.add_documents(splits)
        progress.progress((i + 1) / max(len(pdf_files), 1), text="Adding documents")

    logger.info("Vectorstore populated with %d PDF files", len(pdf_files))
