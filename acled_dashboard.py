import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from components import df_summary, llm_data_analysis, show_mitosheet, show_pygwalker, llm_graph_maker


@st.cache_data
def get_data(url):
    """
    Function to get data from the passed URL through an HTTPS request and return it as a JSON object. Data is cached so that function does not rerun when URL doesn't change.
    """
    try:
        data = requests.get(url).json()
    except Exception as e:
        st.cache_data.clear()
        data = e

    return data

@st.cache_data
def get_iso_reference_df():
    iso3_reference_df = pd.read_csv('content/iso3_country_reference.csv')
    iso3_reference_df['m49'] = iso3_reference_df['m49'].astype(str)

    return iso3_reference_df


# read in iso3 code reference df
iso3_reference_df = get_iso_reference_df()

chat_session_id = 'acled-dashboard-chat-id'

# home button
st.page_link("home.py", label="Home", icon=":material/home:", use_container_width=True)

# title and introduction
st.title("OSAA SMU's ACLED Data Dashboard")

st.markdown("To get started, select which event types, countries, and time range you would like to get data for. Additionally, select the number of rows of data you would like to request. Click 'get data' to request the data, and once it has loaded you will have access to the analysis tools.")

st.markdown("<hr>", unsafe_allow_html=True)
st.write("")

st.markdown("#### Select Event Type")
sub_event_types = [
    'Government regains territory',
    'Non-state actor overtakes territory',
    'Armed clash',
    'Excessive force against protesters',
    'Protest with intervention',
    'Peaceful protest',
    'Violent demonstration',
    'Mob violence',
    'Chemical weapon',
    'Air/drone strike',
    'Suicide bomb',
    'Shelling/artillery/missile attack',
    'Remote explosive/landmine/IED',
    'Grenade',
    'Sexual violence',
    'Attack',
    'Abduction/forced disappearance',
    'Agreement',
    'Arrests',
    'Change to group/activity',
    'Disrupted weapons use',
    'Headquarters or base established',
    'Looting/property destruction',
    'Non-violent transfer of territory',
    'Other'
]
selected_sub_events = st.multiselect("select event type(s)", sub_event_types, None, placeholder="select event type(s)", label_visibility="collapsed")

st.markdown("#### Select Countries")

# select by region
region_mapping = {
    "Western Africa": 1,
    "Middle Africa": 2,
    "Eastern Africa": 3,
    "Southern Africa": 4,
    "Northern Africa": 5,
    "South Asia": 7,
    "Southeast Asia": 9,
    "Middle East": 11,
    "Europe": 12,
    "Caucasus and Central Asia": 13,
    "Central America": 14,
    "South America": 15,
    "Caribbean": 16,
    "East Asia": 17,
    "North America": 18,
    "Oceania": 19,
    "Antarctica": 20
}
selected_regions = st.multiselect("select regions", region_mapping.keys(), None, placeholder="select by region", label_visibility="collapsed")
selected_region_codes = [region_mapping.get(selected_region) for selected_region in selected_regions]

# select by country
country_to_iso_map = dict(zip(iso3_reference_df['Country or Area'], iso3_reference_df['m49']))
selected_countries = st.multiselect("select countries", iso3_reference_df['Country or Area'], None, placeholder="select by country",label_visibility="collapsed")
selected_country_codes = [country_to_iso_map.get(selected_country) for selected_country in selected_countries]


# select years
st.markdown("#### Select Time Range")
selected_years = st.slider( "Select a range of years:", min_value=1960, max_value=2024, value=(1960, 2025), step=1, label_visibility="collapsed")

# select amount of data
st.markdown("#### Select Amount of Data")
st.write("Use this to select the number of rows of data to return. If there are more rows of data matching the parameters than you request, you will recieve the most recent ones. To return all data matching the parameters, set the number of rows to 0. Note that ACLED data is large, and doing so will likely cause a timeout.")
num_rows = st.number_input("Select the number of rows of data:", placeholder="select the number of rows of data:", min_value=0, value=5000, step=1, label_visibility="collapsed")


if st.button("get data", type="primary", use_container_width=True):

    # construct API request URL
    api_key = os.getenv('acled_key')
    email = os.getenv('acled_email')

    BASE_URL = f"https://api.acleddata.com/acled/read?key={api_key}&email={email}"

    sub_event_param = "&sub_event_type=" + ":OR:sub_event_type=".join([str(sub_event) for sub_event in selected_sub_events])
    region_param = "&region=" + ":OR:region=".join([str(code) for code in selected_region_codes])
    country_param = "&iso=" + ":OR:iso=".join(selected_country_codes)
    year_param = f"&year={selected_years[0]}|{selected_years[1]}&year_where=BETWEEN"
    num_rows_param = f"&limit={num_rows}"

    data_url = f"{BASE_URL}{country_param}{year_param}{region_param}{sub_event_param}{num_rows_param}"

    # API query parameters
    data = get_data(data_url)

    if isinstance(data, Exception):
        st.error(f'Error getting data {data}')
        df = None
    else:
        try:
            df = pd.DataFrame(data['data'])
        except Exception as e:
            st.error(f'Erorr processing data: {e}')
            df = None
else:
    df = None


if df is not None and not df.empty:

    # display the dataset
    st.markdown("### Dataset")
    st.write(df)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

    # show time series graphs
    # st.subheader("Explore Data")
    # show_time_series_plots()
    # st.markdown("<hr>", unsafe_allow_html=True)
    # st.write("")

    # show summary statistics
    # st.markdown("### Variable Summary")
    # df_summary(df)
    # st.markdown("<hr>", unsafe_allow_html=True)
    # st.write("") 

    # natural language dataset exploration
    llm_data_analysis(df, chat_session_id, {})
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("") 

    # natural language graph maker
    llm_graph_maker(df)
    # st.markdown("<hr>", unsafe_allow_html=True)
    # st.write("")

    # # Mitosheet
    # st.subheader("Mitosheet Spreadsheet")
    # show_mitosheet(df)
    # st.markdown("<hr>", unsafe_allow_html=True)
    # st.write("") 

    # # PyGWalker
    # st.subheader("PyGWalker Graphing Tool")
    # show_pygwalker(df)

elif df is not None and df.empty:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("") 
    st.markdown("### Dataset")
    st.write("no data returned for selected filters")
