import streamlit as st
import pandas as pd
import wbgapi as wb
import plotly.express as px
from components import df_summary, llm_data_analysis, show_mitosheet, show_pygwalker, llm_graph_maker

# cached functions for retreiving data
@st.cache_data
def get_databases():
    try:
        data = [(database["id"], database["name"]) for database in wb.source.list()]
    except Exception as e:
        data = e
    
    return data

@st.cache_data
def get_indicators():
    try:
        data = list(wb.series.list())
    except Exception as e:
        data = e
    
    return data

@st.cache_data
def get_countries():
    try:
        data = list(wb.economy.list())
    except Exception as e:
        data = e
    
    return data

@st.cache_data
def get_wb_data(indicators, countries, time_range):
    return wb.data.DataFrame(indicators, countries, time_range).reset_index()

@st.cache_data
def get_countries_by_region(region):
    return iso3_reference_df[iso3_reference_df['Region Name'] == region]['iso3'].tolist()

@st.cache_data
def get_iso_reference_df():
    # read in iso3 code reference df
    iso3_reference_df = pd.read_csv('content/iso3_country_reference.csv')

    return iso3_reference_df


@st.fragment
def show_time_series_plots():

    # plot country indicators
    try:
        fig = px.line(
            df, 
            x='Year', 
            y='Value', 
            color='Country or Area', 
            symbol='Indicator',
            markers=True,
            labels={'Country or Area': 'Country', 'Indicator': 'Indicator', 'Indicator Description': 'Indicator Description', 'Value': 'Value', 'Year': 'Year'},
            title="Time Series of Indicators by Country and Indicator"
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error generating Time Series Graph:\n\n{e}")

    # region line chart
    with st.spinner("getting region data"):
        region_df = wb.data.DataFrame(selected_indicators, time=list(range(selected_years[0], selected_years[1]))).reset_index()

        if 'series' not in region_df.columns:
            region_df['series'] = selected_indicators[0]

        # add country reference codes
        region_df = region_df.merge(iso3_reference_df[['Region Name', 'Sub-region Name', 'iso3']], left_on='economy', right_on='iso3', how='left')

        # rename and drop duplicate columns
        region_df.drop(columns=['iso3'], inplace=True)
        region_df = region_df.rename(columns={'series': 'Indicator', 'economy': 'iso3'})
        
        region_df_melted = region_df.melt(id_vars=['Indicator', 'Region Name', 'Sub-region Name', 'iso3'], var_name='Year', value_name='Value')
        region_df_melted['Year'] = region_df_melted['Year'].str.extract('(\d{4})').astype(int)
        
        region_avg_df = region_df_melted.groupby(['Indicator', 'Region Name', 'Year'])['Value'].mean().reset_index()
        world_avg_df = region_avg_df.groupby(['Indicator', 'Year'])['Value'].mean().reset_index()

        world_avg_df['Region Name'] = 'World'
        world_avg_df.rename(columns={'Value': 'Value'}, inplace=True)
        region_avg_df = pd.concat([region_avg_df, world_avg_df], ignore_index=True)

    try:
        fig = px.line(
            region_avg_df, 
            x='Year', 
            y='Value', 
            color='Region Name', 
            symbol='Indicator',
            markers=True,
            labels={'Country or Area': 'Country', 'Indicator': 'Indicator', 'Indicator Description': 'Indicator Description', 'Value': 'Value', 'Year': 'Year'},
            title="Time Series of Indicators by Region and Indicator"
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error generating Time Series Graph:\n\n{e}")


    # map graph
    st.markdown("###### Choose an Indicator to show on the map")
    indicator_descriptions = df['Indicator Description'].unique()
    selected_indicator = st.selectbox("select indicator to show on map:", indicator_descriptions, label_visibility="collapsed")
    indicator_description_code_map = {d['value']: d['id'] for d in indicators}
    selected_code = indicator_description_code_map[selected_indicator]
    indicator_df = df[(df['Indicator'] == selected_code)]

    most_recent_year_with_value = indicator_df.dropna(subset=['Value'])
    most_recent_year = most_recent_year_with_value['Year'].max()
    map_df = most_recent_year_with_value[most_recent_year_with_value['Year'] == most_recent_year]

    try:
        fig = px.choropleth(
            map_df,
            locations='iso3',
            color='Value',
            hover_name='Country or Area',
            color_continuous_scale='Viridis',
            projection='natural earth',
            title="Map of Indicator Value"
        )

        st.plotly_chart(fig)

    except Exception as e:
        st.error(f"Error generating Map Graph:\n\n{e}")


# page chat id
chat_session_id = 'wb-dashboard-chat-id'

# home button
st.page_link("home.py", label="Home", icon=":material/home:", use_container_width=True)

# title and introduction
st.title("OSAA SMU's World Bank Data Dashboard")

st.markdown("To get started, first request data from the WorldBank. To do this, first select the database you would like to access data from. Then select the indicators, countries, and time range to get data for. Indicators can be filtered with keywords. For example, if you are using the *Doing Business* database and interested in indicators related to construction, enter *construction* into the select indicator box to limit the indicators to only those that mention construction. Click 'Get Data' to request the selected data. Once the data has been loaded, you will have access to the data analysis tools.")

st.markdown("<hr>", unsafe_allow_html=True)
st.write("")

# read in iso3 code reference df
iso3_reference_df = get_iso_reference_df()

# get databases
st.markdown("#### Select Database:")
databases = get_databases()
if isinstance(databases, Exception): 
    st.write(f"error getting databases: \n{databases}")
else:
    selected_db_name = st.selectbox("available databases:", [database[1] for database in databases], label_visibility="collapsed")
    selected_db = next(database[0] for database in databases if database[1] == selected_db_name)

    # set the database so all wb api calls will use selected database - otherwise defaults to WDI
    if selected_db:
        wb.db = selected_db

# get indicators
st.markdown("#### Select Indicators:")
indicators = list(wb.series.list())
formatted_indicators = [f"{indicator['id']} - {indicator['value']}" for indicator in indicators]
selected_indicator_names = st.multiselect("available indicators:", formatted_indicators, label_visibility="collapsed", placeholder="select indicator(s)")
selected_indicators = [indicator.split(' - ')[0] for indicator in selected_indicator_names]

# get countries
st.markdown("#### Select Countries:")
countries = get_countries()
if isinstance(countries, Exception): 
    st.write(f"error getting country data: \n{countries}")
else:
    regions = iso3_reference_df['Region Name'].dropna().unique()

    selected_regions = st.multiselect(
        "select regions:",
        ['SELECT ALL'] + list(regions),
        label_visibility="collapsed",
        placeholder="select by region"
    )

    if 'SELECT ALL' in selected_regions:
        selected_regions = [r for r in regions if r != 'SELECT ALL']
    else:
        selected_regions = [r for r in selected_regions if r != 'SELECT ALL']

    selected_countries = []
    for region in selected_regions:
        selected_countries.extend(get_countries_by_region(region))

    # remove duplicates
    selected_countries = list(set(selected_countries))
    selected_country_names = iso3_reference_df[iso3_reference_df['iso3'].isin(selected_countries)]['Country or Area'].tolist()
    iso3_to_name = dict(zip(iso3_reference_df['iso3'], iso3_reference_df['Country or Area']))
    selected_countries_formatted = [f"{country_code} - {iso3_to_name[country_code]}" for country_code in selected_countries]

    available_countries = list(zip(iso3_reference_df['iso3'].tolist(), iso3_reference_df['Country or Area'].tolist()))
    available_countries_formatted = [f"{country[0]} - {country[1]}" for country in available_countries]

    selected_countries = st.multiselect(
        "Available countries:",
        available_countries_formatted,
        default=selected_countries_formatted,
        label_visibility="collapsed",
        placeholder="select by country"
    )
    selected_iso3_codes = [entry.split(' - ')[0] for entry in selected_countries]

# select years
st.markdown("#### Select Time Range")
selected_years = st.slider( "Select a range of years:", min_value=1960, max_value=2025, value=(1960, 2025), step=1, label_visibility="collapsed")

# get world bank data
try:
    if st.button("get data", type='primary', use_container_width=True):
        df = get_wb_data(selected_indicators, selected_iso3_codes, list(range(selected_years[0], selected_years[1])))

        # deal with edge cases where there is no economy column
        if 'economy' not in df.columns:
            df['economy'] = selected_iso3_codes[0]

        # deal with edge cases where there is no series column
        if 'series' not in df.columns:
            df['series'] = selected_indicators[0]
    
        # add country reference codes
        df = df.merge(iso3_reference_df[['Country or Area', 'Region Name', 'Sub-region Name', 'Intermediate Region Name', 'iso2', 'iso3', 'm49']], left_on='economy', right_on='iso3', how='left')

        # rename and drop duplicate columns
        df.drop(columns=['iso3'], inplace=True)
        df = df.rename(columns={'series': 'Indicator', 'economy': 'iso3'})

        # add indicator description
        indicator_code_description_map = {d['id']: d['value'] for d in indicators}
        df['Indicator Description'] = df['Indicator'].map(indicator_code_description_map)

        # reorder columns
        column_order = ['Indicator', 'Indicator Description', 'Country or Area', 'Region Name', 'Sub-region Name', 'Intermediate Region Name', 'iso2', 'iso3', 'm49'] + [col for col in df.columns if col.startswith('YR')]
        df = df[column_order]

        # create melted df
        df = df.melt(id_vars=['Country or Area', 'Indicator', 'Indicator Description', 'Region Name', 'Sub-region Name', 'Intermediate Region Name', 'iso2', 'iso3', 'm49'], var_name='Year', value_name='Value')
        df['Year'] = df['Year'].str.extract('(\d{4})').astype(int)

    else:
        df = None

except Exception as e:
    st.error(f"no data retrieved. this is most likely due to blank indicator, country, or time values. please ensure there are values for the indicator, country, and time range. \n\n Error: {e}")
    df = None


# if there is a dataset selected, show the dataset and data tools
if df is not None and not df.empty:

    # display the dataset
    st.markdown("### Dataset")
    st.write(df)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

    # show time series graphs
    st.subheader("Explore Data")
    show_time_series_plots()
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

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
