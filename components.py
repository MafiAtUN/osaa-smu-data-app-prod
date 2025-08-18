# standard imports
import streamlit as st
import pandas as pd

# llm data analysis imports
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, trim_messages
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from operator import itemgetter
from langchain_core.runnables import RunnablePassthrough
import tiktoken
from langchain_core.messages import BaseMessage, ToolMessage
from typing import List
import numpy as np

# graph maker inports
import re
import plotly.express as px
import plotly.graph_objects as go

# mitosheet imports
from mitosheet.streamlit.v1 import spreadsheet

# pygwalker imports
from pygwalker.api.streamlit import init_streamlit_comm, get_streamlit_html
import streamlit.components.v1 as components

import os
import builtins
import ast

# Allowed builtins for executing LLM generated code
SAFE_BUILTINS = {
    "abs": builtins.abs,
    "min": builtins.min,
    "max": builtins.max,
    "sum": builtins.sum,
    "len": builtins.len,
    "range": builtins.range,
    "list": builtins.list,
    "dict": builtins.dict,
    "set": builtins.set,
    "float": builtins.float,
    "int": builtins.int,
    "str": builtins.str,
    "print": builtins.print,
    "enumerate": builtins.enumerate,
    "zip": builtins.zip,
}

UNSAFE_KEYWORDS = [
    "import os",
    "import subprocess", 
    "import sys",
    "import importlib",
    "os.",
    "subprocess.",
    "sys.",
    "importlib.",
    "open(",
    "eval(",
    "exec(",
    "__",
    "shutil",
    "pathlib",
]

SAFE_IMPORTS = [
    "import pandas",
    "import numpy", 
    "import plotly",
    "import matplotlib",
    "import seaborn",
    "from pandas",
    "from numpy",
    "from plotly",
    "from matplotlib", 
    "from seaborn"
]

def validate_code(code: str) -> None:
    """Raise ValueError if code contains unsafe keywords."""
    
    # First check for unsafe keywords
    lowered = code.lower()
    for keyword in UNSAFE_KEYWORDS:
        if keyword in lowered:
            raise ValueError(f"Unsafe keyword detected: {keyword}")
    
    # Then check if any imports are present and if they're safe
    import_lines = [line.strip().lower() for line in code.split('\n') if line.strip().startswith(('import ', 'from '))]
    
    for import_line in import_lines:
        is_safe = False
        for safe_import in SAFE_IMPORTS:
            if safe_import in import_line:
                is_safe = True
                break
        
        if not is_safe and any(keyword in import_line for keyword in ['import ', 'from ']):
            raise ValueError(f"Unsafe import detected: {import_line}")




# # create the dataframe profile and display it
# @st.fragment
# def show_report(df):
#     """
#         Show the Y-Data Profile report for the passed dataframe.

#         REMOVED BECAUSE IT WAS SLOW AND WAS NOT BEING USED.
#     """

#     button_container = st.container()
#     report_container = st.container()
#     download_container = st.container()

#     try:
#         with button_container:
#             col1, col2 = st.columns(2)
#             with col1:
#                 if st.button('Generate Dataset Profile Report', use_container_width=True, type="primary", disabled=not (df is not None and not df.empty)):
                    
#                     # make profile report
#                     profile = ProfileReport(df, title="Profile Report for WorldBank Data", explorative=True)

#                     # display profile report
#                     with report_container:
#                         with st.expander("show report"):
#                             st_profile_report(profile)

#                     # download the file
#                     with download_container:
#                         with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmp_html:
#                             profile_file_path = tmp_html.name
#                             profile.to_file(profile_file_path)
                        
#                         with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
#                             pdf_file_path = tmp_pdf.name
                        
#                         pdfkit.from_file(profile_file_path, pdf_file_path)

#                         with open(pdf_file_path, 'rb') as f:
#                             st.download_button('Download PDF', f, file_name='dataset profile report.pdf', mime='application/pdf', use_container_width=True, type="primary")

#                         # clean up temporary files
#                         os.remove(profile_file_path)
#                         os.remove(pdf_file_path)

#             with col2:
#                 with st.popover("What are YData Profile Reports?", use_container_width=True):
#                     st.write("YData Profiling is a Python package that offers a range of features to help with exploratory data analysis. It generates a detailed report that includes descriptive statistics for each variable, such as mean, median, and standard deviation for numerical data, and frequency distribution for categorical data. It will also highlights missing values, detects duplicate rows, and identifies potential outliers. Additionally, it provides correlation matrices to explore relationships between variables, interaction plots to visualize dependencies, and alerts to flag data quality issues like high cardinality or skewness. It also includes visualizations like scatter plots, histograms, and heatmaps, making it easier to spot trends and or anomalies in your dataset.")
#     except Exception as e:
#         st.error(f"Error generating report:\n\n{e}")



@st.fragment
def df_summary(df):
    """
        Create a variable summary for the dataframe.

        TODO: Add ability to filter the dataframe to a specific indicator and year and country. Right now it will provide summary statistics for a column across all rows, which may include multiple indicators, which can be misleading.
    """

    summary = df.describe()
    columns = summary.columns
    tabs = st.tabs(columns.to_list())

    # return summary statistic if present
    def get_stat(stat):
        return summary.loc[stat, column] if stat in summary.index else "N/A"

    for i, column in enumerate(columns):
        with tabs[i]:
            st.markdown(f"**Count**: {get_stat('count')}")
            st.markdown(f"**Mean**: {get_stat('mean')}")
            st.markdown(f"**Standard Deviation**: {get_stat('std')}")
            st.markdown(f"**Min**: {get_stat('min')}")
            st.markdown(f"**25th Percentile**: {get_stat('25%')}")
            st.markdown(f"**50th Percentile (Median)**: {get_stat('50%')}")
            st.markdown(f"**75th Percentile**: {get_stat('75%')}")
            st.markdown(f"**Max**: {get_stat('max')}")



@st.fragment
def llm_data_analysis(df, chat_session_id, chat_history):
    """
    Display a natural language data anylsis chatbot for the passed dataframe. The message history is specific to the passed chat_session_id. If a local dict object is passed as chat_history, then the chat history will not persist across script reruns. To persist chat history across reruns, pass a reference to a dict stored in st.session_state or use the StreamlitChatMessageHistory class from LangChain (easiest). Chats are not persisted because if a user changes the data, the chat history from the old data could lead to unexpected responses on the new data.
    """

    st.subheader("Data Analysis Tool")
    st.write("Use this tool to preform data analysis on your selected data using natural language. Describe the analysis you want to do or the question you want to answer, and the tool will preform the necesary analysis and return the result.")
    st.markdown("**NOTE:** This tool uses large language models to preform the analysis. It can and will make mistakes. Therefore, use this tool for **exploratory data analysis only**. If you plan to incldue analysis from this tool in a written publication, it must be double checked and reviewd by a human.")

    def summarize_dataframe(df: pd.DataFrame) -> str:
        """
        Generate a descriptive summary of a DataFrame to pass to the LLM.
        """

        # column names and types
        column_info = "\n".join(
            [f"- {col}: {dtype}" for col, dtype in zip(df.columns, df.dtypes)]
        )
        
        # first 5 rows
        first_five_rows = df.head(5).to_string(index=False)
        
        # description
        description = f"""
            This dataset contains {df.shape[0]} rows and {df.shape[1]} columns. 
            Here are the column names and their data types:
            {column_info}

            Here are the first 5 rows of the data:
            {first_five_rows}
        """

        return description.strip()

    def get_message_history(session_id: str) -> BaseChatMessageHistory:
        if session_id not in chat_history:
            chat_history[session_id] = InMemoryChatMessageHistory()
        return chat_history[session_id]
    
    def get_output_from_code(code, df):
        """
        Extract the output variable from the generated code.
        """
        try:
            # Clean import statements before validation
            cleaned_code = clean_import_statements(code)
            validate_code(cleaned_code)
            local_variables = {'df': df, 'pd': pd, 'np': np}
            restricted_globals = {"__builtins__": SAFE_BUILTINS}
            exec(cleaned_code, restricted_globals, local_variables)
            return local_variables['output']
        except Exception as e:
            return e

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert data analyst. Answer the user's question about their data. You will receive a summary of the dataset. "
                "If the user's question requires code to answer, include the code to answer their question as a single chunk of Python code in your response."
                "When writing code to answer the question, use the Pandas library. Do not create visualizations as part of your analysis. "
                "Assume that the data is stored as a Pandas DataFrame in the variable 'df'."
                "Write your code so that the answer to the user's question is stored in a variable called 'output'. "
                "Ensure the 'output' variable contains a concise and accurate representation of the results that directly answer the user's question."
                "If the question requires returning multiple values, 'output' should be a Pandas DataFrame or Series containing the multiple values."
                "Write efficient and readable code, avoiding unnecessary computations or operations."
                "If necessary, handle missing or unexpected data in a way that ensures the analysis remains accurate."
                "Always include an explanation of what the variable 'output' represents in the context of the user's question, along with a clear explanation of the logic behind your code."
            ),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "DATASET SUMMARY: {data_summary}."
            )
        ]
    )   

    # llm = AzureChatOpenAI(
    #     azure_deployment="osaagpt32k",
    #     api_key=os.getenv('azure'),
    #     azure_endpoint="https://openai-osaa-v2.openai.azure.com/",
    #     openai_api_version="2024-05-01-preview"
    # )
    llm = AzureChatOpenAI(
        azure_deployment="gpt4o",
        api_key=os.getenv('azure'),
        azure_endpoint="https://openai-osaa-v2.openai.azure.com/openai/deployments/gpt4o/chat/completions?api-version=2024-08-01-preview",
        openai_api_version="2024-08-01-preview"
    )

    chain = prompt | llm

    messages_container = st.container()
    with messages_container:
        messages = chat_history.get(chat_session_id, None)
        if messages:
            for msg in messages.messages:
                st.chat_message(msg.type).write(msg.content)

    if analysis_question := st.chat_input('ask about the data...'):

        with messages_container:
            st.chat_message("human").write(analysis_question)

        chain_with_history = RunnableWithMessageHistory(
            chain,
            get_message_history,
             input_messages_key="messages"
        )
        config = {"configurable": {"session_id": chat_session_id}}
        
        response = chain_with_history.invoke(
            {
                "messages": [HumanMessage(content=analysis_question)],
                "data_summary": summarize_dataframe(df),
            },
            config=config,
        )

        code_block_match = re.search(r'```(?:[Pp]ython)?(.*?)```', response.content, re.DOTALL)
        if code_block_match:
            code_block = code_block_match.group(1).strip()
            cleaned_code = re.sub(r'(?m)^\s*fig\.show\(\)\s*$', '', code_block)

            # # check generated code
            # unsafe_keywords = ["os", "subprocess", "eval", "exec", "open"]
            # if any(keyword in cleaned_code for keyword in unsafe_keywords):
            #     st.error("Unsafe generated code detected:")
            #     output = None
            # else:
            #     output = get_output_from_code(cleaned_code, df)

            result = get_output_from_code(cleaned_code, df)
            if isinstance(result, Exception):
                st.error(f"Error executing generated code: {result}")
                st.code(cleaned_code)
                output = None
            else:
                output = result
        else:
            output = None

        with messages_container:
            with st.chat_message("ai"):
                st.write(response.content)
                if output is not None:
                    if isinstance(output, (pd.Series, pd.DataFrame, np.ndarray)):
                        st.markdown('###### Calculated Output:')
                        st.dataframe(output)
                    elif isinstance(output, dict):
                        st.markdown('###### Calculated Output:')
                        for key, value in output.items():
                            st.markdown(f'**{key}**: {value}')
                    elif isinstance(output, Exception):
                        st.write(f"I'm sorry I could not answer your question an error occured. \n\n {output}")
                    else:   
                        st.markdown(f'**Calcuated Output:** {output}')
                else:
                    st.markdown('###### Calculated Output:')
                    st.write('there was no code to run in the generated response.')



@st.fragment
def llm_graph_maker(df):

    st.subheader("Visualization Tool")
    st.write("Use this tool to create visualizations from descriptions. Write a description of the visulization you would like, including the type of graph and what part of the data you want to show. The tool will attempt to create a graph based on your description. It may ask for more information or instructions if needed.")
    st.markdown("**NOTE:** This tool uses large language models to create the graph. It can and will make mistakes. Therefore, use this tool for **exploratory data analysis only**. If you plan to incldue analysis from this tool in a written publication, it must be double checked and reviewd by a human.")

    def summarize_dataframe(df: pd.DataFrame) -> str:
        """
        Generate a descriptive summary of a DataFrame to pass to the LLM.
        """

        # column names and types
        column_info = "\n".join(
            [f"- {col}: {dtype}" for col, dtype in zip(df.columns, df.dtypes)]
        )
        
        # first 5 rows
        first_five_rows = df.head(5).to_string(index=False)
        
        # description
        description = f"""
            This dataset contains {df.shape[0]} rows and {df.shape[1]} columns. 
            Here are the column names and their data types:
            {column_info}

            Here are the first 5 rows of the data:
            {first_five_rows}
        """

        return description.strip()
    
    def get_fig_from_code(code, df):
        """
        Extract the plotly fig object from the generated code.
        """
        try:
            # Clean import statements before validation
            cleaned_code = clean_import_statements(code)
            validate_code(cleaned_code)
            local_variables = {'df': df, 'pd': pd, 'np': np, 'go': go, 'px': px}
            restricted_globals = {"__builtins__": SAFE_BUILTINS}
            exec(cleaned_code, restricted_globals, local_variables)
            return local_variables['fig']
        except Exception as e:
            return e

    # initiatlize model
    llm = AzureChatOpenAI(
        azure_deployment="gpt4o",
        api_key=os.getenv('azure'),
        azure_endpoint="https://openai-osaa-v2.openai.azure.com/openai/deployments/gpt4o/chat/completions?api-version=2024-08-01-preview",
        openai_api_version="2024-08-01-preview"
    )

    # chat prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a data visualization expert. Follow the user's instructions to create a graph. "
                "You will get a summary of the data as well as the first several rows. "
                "The data is available as a Pandas DataFrame in the variable 'df'. "
                "Use only the following Python libraries: Plotly, Pandas, and NumPy. "
                "Store the graph in a variable called 'fig'. "
                "**IMPORTANT: Do NOT include any import statements in your code.** "
                "The required modules (pandas, numpy, plotly) are already available in the execution environment."
            ),
            (
                "system",
                "Ensure that the graph type and relevant details (e.g., axes, colors) match the user's instructions. "
                "Handle missing or non-numeric data gracefully by filling, dropping, or converting as necessary. "
                "Ensure the output is valid Python code that can run without modifications."
            ),
            (
                "system",
                "DATASET SUMMARY: {data_summary}",
            ),
            MessagesPlaceholder(variable_name="messages")
        ]
    )

    # make chain
    chain = prompt | llm 

    # get input
    if graph_prompt := st.chat_input("describe the visualization you want to create..."):

        st.info(f"Instructions: {graph_prompt}")

        inputs = {
            "data_summary": summarize_dataframe(df), 
            "messages": [HumanMessage(content=graph_prompt)]
        }

        # get response
        with st.spinner("generating graph"):
            response = chain.invoke(inputs)
            code_block_match = re.search(r'```(?:[Pp]ython)?(.*?)```', response.content, re.DOTALL)
            if code_block_match:
                code_block = code_block_match.group(1).strip()
                cleaned_code = re.sub(r'(?m)^\s*fig\.show\(\)\s*$', '', code_block)

                # # check generated code
                # unsafe_keywords = ["os", "subprocess", "eval", "exec", "open"]
                # if any(keyword in cleaned_code for keyword in unsafe_keywords):
                #     st.error("Unsafe generated code detected:")
                #     st.code(cleaned_code)
                # else:
                #     fig = get_fig_from_code(cleaned_code, df)

                result = get_fig_from_code(cleaned_code, df)
                if isinstance(result, Exception):
                    st.error(f"Error executing generated code: {result}")
                    st.code(cleaned_code)
                    fig = None
                else:
                    fig = result
            else:
                st.write(f"No code generated in the LLM response. This could mean the LLM wants more instructions to make the graph. Please note that this tool will not remember your last message, so please enter your entire visualization instructions. See it's response below:")
                st.chat_message("assistant").markdown(response.content)
                fig = None

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("##### Code Used")
            st.code(cleaned_code)




@st.fragment
def show_mitosheet(df):
    """
    Show a Mitosheet for the passed dataframe.
    """

    new_dfs, code = spreadsheet(df)

    if code:
        st.markdown("##### Generated Code:")
        st.code(code)



@st.fragment
def show_pygwalker(df):
    """
    Show the PyGWalker tool for the passed dataframe.
    """
    
    init_streamlit_comm()
    @st.cache_resource
    def get_pyg_html(df: pd.DataFrame) -> str:
        html = get_streamlit_html(df, spec="./gw0.json", use_kernel_calc=True, debug=False)
        return html

    components.html(get_pyg_html(df), width=1300, height=1000, scrolling=True)


def clean_import_statements(code: str) -> str:
    """
    Remove import statements from LLM-generated code since modules are already provided.
    """
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Skip import statements
        if (stripped.startswith('import ') or 
            stripped.startswith('from ') and ' import ' in stripped):
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

