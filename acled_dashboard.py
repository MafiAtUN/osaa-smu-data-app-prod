import streamlit as st
import pandas as pd
import requests
import os
from components import llm_data_analysis, llm_graph_maker

@st.cache_data
def get_access_token(username, password):
    """
    Get OAuth access token from ACLED API
    """
    token_url = "https://acleddata.com/oauth/token"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'username': username,
        'password': password,
        'grant_type': "password",
        'client_id': "acled"
    }

    try:
        response = requests.post(token_url, headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            return token_data['access_token']
        else:
            st.error(f"Failed to get access token: {response.status_code} {response.text}")
            return None
    except Exception as e:
        st.error(f"Error getting access token: {e}")
        return None

@st.cache_data
def get_data(url, access_token):
    """
    Function to get data from the passed URL through an HTTPS request and return it as a JSON object. Data is cached so that function does not rerun when URL doesn't change.
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            st.error(f"API request failed: {response.status_code} {response.text}")
            return None
    except Exception as e:
        st.error(f"Error making API request: {e}")
        return None

@st.cache_data
def get_data_with_params(base_url, access_token, parameters):
    """
    Function to get data with parameters using requests.get() params argument
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = requests.get(base_url, params=parameters, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            st.error(f"API request failed: {response.status_code} {response.text}")
            return None
    except Exception as e:
        st.error(f"Error making API request: {e}")
        return None

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
selected_years = st.slider( "Select a range of years:", min_value=1960, max_value=2025, value=(1960, 2025), step=1, label_visibility="collapsed")

# select amount of data
st.markdown("#### Select Amount of Data")
st.write("Use this to select the number of rows of data to return. If there are more rows of data matching the parameters than you request, you will receive the most recent ones. To return all data matching the parameters, set the number of rows to 0. Note that ACLED data is large, and doing so will likely cause a timeout.")
num_rows = st.number_input("Select the number of rows of data:", placeholder="select the number of rows of data:", min_value=0, value=5000, step=1, label_visibility="collapsed")

if st.button("get data", type="primary", use_container_width=True):
    
    # Get OAuth access token
    username = os.getenv('acled_email')
    password = os.getenv('acled_key')  # Using the key as password for OAuth
    
    if not username or not password:
        st.error("ACLED credentials not found. Please set ACLED_EMAIL and ACLED_KEY environment variables.")
        df = None
    else:
        access_token = get_access_token(username, password)
        
        if access_token:
            # Build API URL with correct format
            base_url = "https://acleddata.com/api/acled/read"
            
            # Build parameters dictionary
            parameters = {
                "_format": "json"
            }
            
            # Fix country parameters - use country names directly
            if selected_countries:
                # Use country names as they appear in the CSV
                country_param = "|".join(selected_countries)
                parameters['country'] = country_param
            
            # Fix region parameters - use region names directly
            if selected_regions:
                # Use region names as they appear in the mapping
                region_param = "|".join(selected_regions)
                parameters['region'] = region_param
            
            # Fix sub-event parameters
            if selected_sub_events:
                # Use the exact event type names
                sub_event_param = "|".join(selected_sub_events)
                parameters['sub_event_type'] = sub_event_param
            
            # Fix year range - use simple year parameter
            if selected_years[0] == selected_years[1]:
                # Single year
                parameters['year'] = selected_years[0]
            else:
                # For year range, use the start year and add year_where parameter
                parameters['year'] = selected_years[0]
                parameters['year_where'] = ">="
                # Add end year as separate parameter
                parameters['year_end'] = selected_years[1]
            
            # Add limit
            if num_rows > 0:
                parameters['limit'] = num_rows
            
            # Make API request with parameters
            data = get_data_with_params(base_url, access_token, parameters)
            
            if data and isinstance(data, dict) and 'data' in data:
                try:
                    df = pd.DataFrame(data['data'])
                    st.success(f"Successfully retrieved {len(df)} records from ACLED API")
                except Exception as e:
                    st.error(f'Error processing data: {e}')
                    st.write("Raw API Response:", data)
                    df = None
            elif data and isinstance(data, list):
                try:
                    df = pd.DataFrame(data)
                    st.success(f"Successfully retrieved {len(df)} records from ACLED API")
                except Exception as e:
                    st.error(f'Error processing data: {e}')
                    st.write("Raw API Response:", data)
                    df = None
            else:
                st.error("No data received from API or unexpected response format")
                if data:
                    st.write("API Response:", data)
                df = None
        else:
            st.error("Failed to authenticate with ACLED API. Please check your credentials.")
            df = None
else:
    df = None

if df is not None and not df.empty:
    # display the dataset
    st.markdown("### Dataset")
    st.write(df)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("")

    # natural language dataset exploration
    llm_data_analysis(df, chat_session_id, {})
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("") 

    # natural language graph maker
    llm_graph_maker(df)

elif df is not None and df.empty:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.write("") 
    st.markdown("### Dataset")
    st.write("no data returned for selected filters")