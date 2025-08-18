import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from components import df_summary, llm_data_analysis, show_mitosheet, show_pygwalker, llm_graph_maker


@st.cache_data
def get_data(url):
    """
    Function to get data from the passed URL through an HTTPS request and return it as a JSON object. Data is cached so that function does not rerun when URL doesn't change.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Check if response is empty
        if not response.text.strip():
            return Exception("Empty response from API")
        
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        st.cache_data.clear()
        return Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        st.cache_data.clear()
        return Exception(f"Invalid JSON response: {str(e)}. Response text: {response.text[:200]}...")
    except Exception as e:
        st.cache_data.clear()
        return Exception(f"Unexpected error: {str(e)}")

@st.cache_data
def get_iso_reference_df():
    iso3_reference_df = pd.read_csv('content/iso3_country_reference.csv')
    iso3_reference_df['m49'] = iso3_reference_df['m49'].astype(str)

    return iso3_reference_df

chat_session_id = 'sdg-dashboard-chat-id'


# base url for SDG requests
BASE_URL = "https://unstats.un.org/sdgs/UNSDGAPIV5"

# read in iso3 code reference df
iso3_reference_df = get_iso_reference_df()

# home button
st.page_link("home.py", label="Home", icon=":material/home:", use_container_width=True)

# title and introduction
st.title("OSAA SMU's SDG Data Dashboard")

st.markdown("To get started, request data from UN Sustainable Development Goals database. Use the first section to explore available indicators related to each goal. Then, select the indicators, countries, and time range for the data you are interested in and click 'get data'. Once the data has been loaded, you will have access to the analysis tools.")

st.markdown("<hr>", unsafe_allow_html=True)
st.write("")

st.markdown("### Explore Sustainable Development Goals")
goals_url = "v1/sdg/Goal/List?includechildren=false"
goals_data = get_data(f"{BASE_URL}/{goals_url}")
if not isinstance(goals_data, Exception):
    selected_goal_title = st.selectbox("select goal to explore", [f"{goal['code']}. {goal['title']}" for goal in goals_data], label_visibility="collapsed")
    selected_goal_code = next(goal['code'] for goal in goals_data if f"{goal['code']}. {goal['title']}" == selected_goal_title)
    selected_goal_data = next(goal for goal in goals_data if f"{goal['code']}. {goal['title']}" == selected_goal_title)

    st.write(selected_goal_data['description'])

    # Load indicator data for selection (but don't display all indicators)
    indicator_url = "v1/sdg/Indicator/List"
    indicator_data = get_data(f"{BASE_URL}/{indicator_url}")
else:
    indicator_data = None
    st.write(f"Error getting data: \n\n {goals_data}")

st.markdown("<hr>", unsafe_allow_html=True)
st.write("")

st.markdown("#### Select Indicators")
# Filter indicators to only show those belonging to the selected goal
if indicator_data is not None and 'selected_goal_code' in locals():
    filtered_indicators = [indicator for indicator in indicator_data if indicator['goal'] == selected_goal_code]
    indicators = [f"{indicator['code']}: {indicator['description']}" for indicator in filtered_indicators]
    
    if indicators:
        selected_indicator_names = st.multiselect("select indicators", indicators, label_visibility="collapsed", placeholder='select indicators...')
        selected_indicator_codes = [entry.split(': ')[0] for entry in selected_indicator_names]
    else:
        st.warning(f"No indicators found for the selected goal: {selected_goal_title}")
        selected_indicator_codes = []
else:
    st.warning("Please select a goal first to see available indicators.")
    selected_indicator_codes = []

st.markdown("#### Select Countries")
country_code_url = "v1/sdg/GeoArea/List"
country_code_data = get_data(f"{BASE_URL}/{country_code_url}")

if not isinstance(country_code_data, Exception):

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

    def get_countries_by_region(region):
        return iso3_reference_df[iso3_reference_df['Region Name'] == region]['m49'].tolist()

    selected_countries = []
    for region in selected_regions:
        selected_countries.extend(get_countries_by_region(region))

    # remove duplicates
    selected_countries = list(set(selected_countries))
    selected_country_names = iso3_reference_df[iso3_reference_df['m49'].isin(selected_countries)]['Country or Area'].tolist()
    m49_to_name = dict(zip(iso3_reference_df['m49'], iso3_reference_df['Country or Area']))
    selected_countries_formatted = [f"{country_code} - {m49_to_name[country_code]}" for country_code in selected_countries]

    available_countries = list(zip(iso3_reference_df['m49'].tolist(), iso3_reference_df['Country or Area'].tolist()))
    available_countries_formatted = [f"{country[0]} - {country[1]}" for country in available_countries]

    selected_countries = st.multiselect(
        "Available countries:",
        available_countries_formatted,
        default=selected_countries_formatted,
        label_visibility="collapsed",
        placeholder="select by country"
    )

    selected_country_codes = [entry.split(' - ')[0] for entry in selected_countries]
else:
    st.write(f"Error getting data: \n\n {goals_data}")

st.markdown("#### Select Time Range")
selected_years = st.slider( "Select a range of years:", min_value=1963, max_value=2025, value=(1963, 2025), step=1, label_visibility="collapsed")

# get data
indicator_params = "indicator=" + "&indicator=".join(selected_indicator_codes)
country_params = "&areaCode=" + "&areaCode=".join(selected_country_codes)
year_params = "&timePeriod=" + "&timePeriod=".join([str(i) for i in range(selected_years[0], selected_years[1] + 1)])
page_size = 1000
data_url = f"{BASE_URL}/v1/sdg/Indicator/Data?{indicator_params}{country_params}{year_params}&pageSize={page_size}"



st.write("NOTE: the maximum number of pages defaults to 100. Each page contains 1000 rows of data. If you need more than 10,000 rows, increase the maximum page size accordingly. Very large queries may result in app timeouts.")

col1, col2 = st.columns(2)
with col1:
    max_pages = st.number_input("Insert a number", min_value=1, value=None, placeholder="maximum number of pages (defaults to 100)", label_visibility="collapsed")
    if max_pages is None:
        max_pages = 100

with col2:
    if st.button("get data", type='primary', use_container_width=True):

        # loop over pages to get all data
        extracted_data = []
        page_num = 1
        for page_num in range(1, max_pages + 1):
            data = get_data(f'{data_url}&page={page_num}')

            if not isinstance(data, Exception):
                
                # break if no data
                if not data.get('data', []):
                    break

                if len(data['data']) < 1:
                    st.write("no data returned for the selected countries, indicators, and years.")
                else:
                    for entry in data["data"]:
                        # Extract all available columns from the API response
                        row_data = {}
                        
                        # Handle indicator field (it might be an array)
                        if isinstance(entry.get("indicator"), list) and len(entry["indicator"]) > 0:
                            row_data["Indicator"] = entry["indicator"][0]
                        else:
                            row_data["Indicator"] = entry.get("indicator", "")
                        
                        # Add all other fields from the API response
                        for key, value in entry.items():
                            if key != "indicator":  # Already handled above
                                if key == "dimensions":
                                    # Handle dimensions as JSON object or string
                                    if isinstance(value, str):
                                        try:
                                            import json
                                            dim_dict = json.loads(value)
                                            for dim_key, dim_value in dim_dict.items():
                                                row_data[f"dimension_{dim_key}"] = dim_value
                                        except:
                                            row_data[key] = value
                                    elif isinstance(value, dict):
                                        for dim_key, dim_value in value.items():
                                            row_data[f"dimension_{dim_key}"] = dim_value
                                    else:
                                        row_data[key] = value
                                elif key == "attributes":
                                    # Handle attributes as JSON object or string
                                    if isinstance(value, str):
                                        try:
                                            import json
                                            attr_dict = json.loads(value)
                                            for attr_key, attr_value in attr_dict.items():
                                                row_data[f"attribute_{attr_key}"] = attr_value
                                        except:
                                            row_data[key] = value
                                    elif isinstance(value, dict):
                                        for attr_key, attr_value in value.items():
                                            row_data[f"attribute_{attr_key}"] = attr_value
                                    else:
                                        row_data[key] = value
                                else:
                                    row_data[key] = value
                        
                        extracted_data.append(row_data)
                        # extracted_data.append(entry)

                # Check if we've reached the end of data (less than page_size records)
                if len(data.get('data', [])) < page_size:
                    break

            else:
                st.error(f"An error occurred while getting the data: \n\n {data}.")
                break  # Exit the loop if there's an error

        df = pd.DataFrame(extracted_data)

        if not df.empty:



            # Determine the correct country code column name
            country_code_column = None
            possible_country_columns = ['m49', 'geoAreaCode', 'areaCode', 'countryCode']
            
            for col in possible_country_columns:
                if col in df.columns:
                    country_code_column = col
                    break
            
            if country_code_column:
                # add country reference codes
                df = df.merge(iso3_reference_df[['Country or Area', 'Region Name', 'Sub-region Name', 'Intermediate Region Name','iso2', 'iso3', 'm49']], left_on=country_code_column, right_on='m49', how='left')
            else:
                st.warning("Could not find country code column. Available columns that might be country codes: " + str([col for col in df.columns if 'code' in col.lower() or 'area' in col.lower() or 'country' in col.lower()]))

            # clean dataframe - handle numeric fields more carefully
            if 'Value' in df.columns:
                df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
            if 'Year' in df.columns:
                df['Year'] = pd.to_numeric(df['Year'], errors='coerce').astype('Int64')  # Use Int64 to handle NaN values
            
            # Rename dimension columns to be more user-friendly
            column_mapping = {}
            for col in df.columns:
                if col.startswith('dimension_'):
                    dim_name = col.replace('dimension_', '')
                    column_mapping[col] = f"Breakdown by {dim_name}"
            
            df = df.rename(columns=column_mapping)
            
            # Reorder columns according to specified order
            priority_columns = []
            
            # Add code columns first
            if 'm49' in df.columns:
                priority_columns.append('m49')
            if 'iso3' in df.columns:
                priority_columns.append('iso3')
            
            # Add region columns
            if 'Region Name' in df.columns:
                priority_columns.append('Region Name')
            if 'Sub-region Name' in df.columns:
                priority_columns.append('Sub-region Name')
            if 'Intermediate Region Name' in df.columns:
                priority_columns.append('Intermediate Region Name')
            
            # Add country column
            if 'Country or Area' in df.columns:
                priority_columns.append('Country or Area')
            
            # Add dimension columns (breakdown columns)
            breakdown_columns = [col for col in df.columns if col.startswith('Breakdown by')]
            priority_columns.extend(sorted(breakdown_columns))
            
            # Add series description
            if 'seriesDescription' in df.columns:
                priority_columns.append('seriesDescription')
            
            # Add time period and value
            if 'timePeriodStart' in df.columns:
                priority_columns.append('timePeriodStart')
            if 'value' in df.columns:
                priority_columns.append('value')
            
            # Add only specific remaining columns (exclude unwanted ones)
            unwanted_columns = [
                'attribute_Nature', 'source', 'target', 'timeCoverage', 'time_detail', 
                'upperBound', 'lowerBound', 'footnotes', 'seriesCount', 'geoInfoUrl', 
                'basePeriod', 'valueType'
            ]
            
            remaining_columns = [col for col in df.columns if col not in priority_columns and col not in unwanted_columns]
            priority_columns.extend(sorted(remaining_columns))
            
            # Reorder the dataframe
            df = df[priority_columns]

    else:
        df = None


@st.fragment
def show_time_series_plots():

    try:
        fig = px.line(
            st.session_state.sdg_df, 
            x='Year', 
            y='Value', 
            color='Country or Area', 
            symbol='Series',
            markers=True,
            labels={'Country or Area': 'Country', 'Series': 'Series', 'Series Description': 'Series Description', 'Value': 'Value', 'Year': 'Year'},
            title="Time Series of Indicators by Country and Indicator"
        )

        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error generating graph:\n\n{e}")


    try:           
        st.markdown("###### Choose an Series to show on the map")
        series_descriptions = st.session_state.sdg_df['Series Description'].unique()
        selected_series= st.selectbox("select indicator to show on map:", series_descriptions, label_visibility="collapsed")
        series_df = st.session_state.sdg_df[(st.session_state.sdg_df['Series Description'] == selected_series)]

        most_recent_year_with_value = series_df.dropna(subset=['Value'])
        most_recent_year = most_recent_year_with_value['Year'].max()
        map_df = most_recent_year_with_value[most_recent_year_with_value['Year'] == most_recent_year]

        map_df = series_df[series_df['Year'] == most_recent_year]

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


# if there is a dataset selected, show the dataset and data tools
if df is not None and not df.empty:

    # display the dataset
    st.markdown("### Dataset")
    st.write(df)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

    # Data Availability Visualization
    st.markdown("### Data Availability by Country and Year")
    
    try:
        # Create a pivot table showing data availability
        if 'Country or Area' in df.columns and 'timePeriodStart' in df.columns:
            # Create availability matrix (1 if data exists, 0 if not)
            availability_df = df.groupby(['Country or Area', 'timePeriodStart']).size().reset_index(name='count')
            availability_df['has_data'] = 1
            
            # Pivot to get countries as rows and years as columns
            pivot_df = availability_df.pivot(index='Country or Area', columns='timePeriodStart', values='has_data').fillna(0)
            
            # Create heatmap
            fig = px.imshow(
                pivot_df,
                title="Data Availability Heatmap",
                labels=dict(x="Year", y="Country", color="Data Available"),
                color_continuous_scale="Blues",
                aspect="auto"
            )
            
            fig.update_layout(
                xaxis_title="Year",
                yaxis_title="Country",
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Countries", len(pivot_df))
            with col2:
                st.metric("Year Range", f"{pivot_df.columns.min()} - {pivot_df.columns.max()}")
            with col3:
                total_data_points = pivot_df.sum().sum()
                st.metric("Total Data Points", total_data_points)
                
        else:
            st.warning("Required columns (Country or Area, timePeriodStart) not found for availability visualization.")
            
    except Exception as e:
        st.error(f"Error creating data availability visualization: {e}")
    
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

    # natural language dataset exploration
    llm_data_analysis(df, chat_session_id, {})
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("") 

    # natural language graph maker
    llm_graph_maker(df)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

    # PyGWalker
    st.subheader("PyGWalker Graphing Tool")
    show_pygwalker(df)

elif df is not None and df.empty:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("") 
    st.markdown("### Dataset")
    st.write("no data returned for selected filters")