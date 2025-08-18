# OSAA SMU Data App

The Office of the Special Advisor to Africa's Strategic Management Unit's comprehensive data analysis and visualization platform.

## 📊 Overview

The OSAA SMU Data App is a powerful web-based application that provides data analysis, visualization, and insights across multiple data sources including ACLED (Armed Conflict Location & Event Data), World Bank data, and SDG (Sustainable Development Goals) indicators. The app features AI-powered data analysis, interactive visualizations, and a conversational chatbot interface.

## 🚀 Features

### 📊 Multi-Source Data Integration
- **ACLED Dashboard**: Real-time conflict and event data analysis
- **World Bank Dashboard**: Economic and development indicators
- **SDG Dashboard**: Sustainable Development Goals tracking
- **Custom Data Upload**: Support for CSV, Excel, and other data formats

### 🤖 AI-Powered Analysis
- **LLM Data Analysis**: Intelligent data insights using Azure OpenAI or Open Source LLMs
- **Automated Visualization**: AI-generated charts and graphs
- **Natural Language Queries**: Chatbot interface for data exploration
- **Code Generation**: Safe execution of data analysis code

### 📊 Interactive Visualizations
- **Plotly Charts**: Dynamic, interactive data visualizations
- **MitoSheet Integration**: Spreadsheet-like data manipulation
- **PyGWalker**: Advanced data exploration tools
- **Custom Dashboards**: Tailored views for different data sources

### 🔒 Security Features
- **Code Validation**: Safe execution of AI-generated code
- **Import Statement Cleaning**: Prevents malicious code execution
- **Environment Variable Protection**: Secure API credential management
- **Input Validation**: Comprehensive data and parameter validation

## 📦 Installation

### Prerequisites
- Python 3.10 or higher
- Git
- ACLED API credentials (for conflict data access)
- **Option A**: Azure OpenAI API credentials
- **Option B**: Local LLM setup (Llama, Ollama, etc.)

### Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/osaa-smu-data-app.git
   cd osaa-smu-data-app
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**

   **Option A: Azure OpenAI Setup**
   Create a `.env` file with Azure configuration:
   ```env
   # Azure OpenAI Configuration
   AZURE_OPENAI_API_KEY=your_azure_openai_api_key
   AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt4o

   # ACLED API Credentials
   acled_email=your_acled_email@example.com
   acled_key=your_acled_api_key

   # Streamlit Configuration
   STREAMLIT_SERVER_PORT=8501
   STREAMLIT_SERVER_ADDRESS=localhost
   ```

   **Option B: Open Source LLM Setup**
   Create a `.env` file with local LLM configuration:
   ```env
   # Open Source LLM Configuration
   LLM_TYPE=local  # Options: azure, local, ollama
   LOCAL_LLM_ENDPOINT=http://localhost:11434  # Ollama endpoint
   LOCAL_LLM_MODEL=llama3.2:3b  # Model name
   
   # Alternative: Direct Llama setup
   LLAMA_MODEL_PATH=/path/to/your/llama/model
   LLAMA_USE_GPU=true  # Set to false for CPU-only
   
   # ACLED API Credentials
   acled_email=your_acled_email@example.com
   acled_key=your_acled_api_key

   # Streamlit Configuration
   STREAMLIT_SERVER_PORT=8501
   STREAMLIT_SERVER_ADDRESS=localhost
   ```

5. **Run the Application**
   ```bash
   streamlit run app.py
   ```

## 🔧 Open Source LLM Configuration

### Option 1: Using Ollama (Recommended)

**Install Ollama:**
```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download
```

**Pull and Run Llama Model:**
```bash
# Pull the model
ollama pull llama3.2:3b

# Run the model
ollama serve
```

**Update components.py for Ollama:**
```python
# In components.py, update the LLM configuration
if os.getenv('LLM_TYPE') == 'local':
    # Ollama configuration
    client = openai.OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"  # Not used but required
    )
    
    response = client.chat.completions.create(
        model="llama3.2:3b",
        messages=messages,
        temperature=0.7,
        max_tokens=2000
    )
```

### Option 2: Using Local Llama with llama.cpp

**Install llama.cpp:**
```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make
```

**Download Llama Model:**
```bash
# Download from Hugging Face or use your own model
# Place in models/ directory
```

**Run Local Server:**
```bash
./server -m models/llama-3.2-3b.gguf -c 2048 --port 8080
```

**Update Environment:**
```env
LOCAL_LLM_ENDPOINT=http://localhost:8080
LOCAL_LLM_MODEL=llama-3.2-3b
```

### Option 3: Using Hugging Face Transformers

**Install Additional Dependencies:**
```bash
pip install transformers torch accelerate
```

**Update requirements.txt:**
```txt
# Add to requirements.txt
transformers>=4.35.0
torch>=2.0.0
accelerate>=0.20.0
```

**Local Model Configuration:**
```python
# In components.py
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

def load_local_model():
    model_name = os.getenv('LOCAL_LLM_MODEL', 'meta-llama/Llama-3.2-3B')
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    return model, tokenizer
```

### Option 4: Using LM Studio

**Install LM Studio:**
1. Download from [LM Studio](https://lmstudio.ai/)
2. Install and launch the application
3. Download a Llama model through the interface
4. Start the local server

**Configure Environment:**
```env
LOCAL_LLM_ENDPOINT=http://localhost:1234/v1
LOCAL_LLM_MODEL=local-model
```

## 📊 Performance Comparison

| LLM Option | Setup Complexity | Performance | Cost | Privacy |
|------------|------------------|-------------|------|---------|
| Azure OpenAI | Low | High | Pay-per-use | Cloud |
| Ollama | Medium | Good | Free | Local |
| llama.cpp | High | Good | Free | Local |
| Hugging Face | High | Variable | Free | Local |
| LM Studio | Low | Good | Free | Local |

## 🔄 Switching Between LLM Providers

The app automatically detects your configuration and switches between providers:

```python
# Automatic provider selection in components.py
def get_llm_client():
    llm_type = os.getenv('LLM_TYPE', 'azure')
    
    if llm_type == 'azure':
        return openai.AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION')
        )
    elif llm_type == 'local':
        return openai.OpenAI(
            base_url=os.getenv('LOCAL_LLM_ENDPOINT'),
            api_key="local"
        )
    else:
        raise ValueError(f"Unsupported LLM type: {llm_type}")
```

## 📁 Project Structure

```
osaa-smu-data-app/
├── app.py                 # Main Streamlit application entry point
├── home.py               # Home page with navigation
├── dashboard.py          # Main data dashboard
├── acled_dashboard.py    # ACLED conflict data dashboard
├── wb_dashboard.py       # World Bank data dashboard
├── sdg_dashboard.py      # SDG indicators dashboard
├── chatbot.py            # AI chatbot interface
├── components.py         # Reusable UI components and LLM functions
├── helper_functions.py   # Utility functions
├── check_analysis.py     # Data analysis validation
├── pid_checker.py        # Process ID utilities
├── content/              # Data files and assets
│   ├── db.duckdb         # Local database
│   ├── iso3_country_reference.csv
│   └── OSAA-Data-logo.svg
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (create this)
└── README.md            # This file
```

This comprehensive README includes:

1. **Clear Overview** of the app's purpose and capabilities
2. **Detailed Installation** instructions with all prerequisites
3. **Environment Configuration** for all required API keys
4. **Project Structure** explanation
5. **Usage Guide** for different features
6. **Security Considerations** and safety measures
7. **Troubleshooting** section for common issues
8. **Contributing Guidelines** for team collaboration
9. **Professional Formatting** with emojis and clear sections

The README is now ready to help users understand, install, and use your OSAA SMU Data App effectively!

## 📖 Usage Guide

### Getting Started
1. **Launch the App**: Run `streamlit run app.py`
2. **Navigate**: Use the home page to access different dashboards
3. **Upload Data**: Use the data dashboard to upload and analyze custom datasets
4. **Explore**: Use AI-powered analysis tools for insights

### ACLED Dashboard
- Select countries and regions for conflict data
- Choose date ranges and event types
- View interactive visualizations
- Export filtered data

### Data Analysis
- Upload CSV or Excel files
- Use AI-powered analysis for insights
- Generate custom visualizations
- Export results and charts

### Chatbot Interface
- Ask natural language questions about your data
- Get AI-generated insights and recommendations
- Request specific visualizations
- Explore data relationships

## 🔒 Security Considerations

### Code Execution Safety
- All AI-generated code is validated before execution
- Import statements are automatically cleaned
- Restricted execution environment prevents malicious code
- Timeout mechanisms prevent infinite loops

### Data Protection
- Environment variables protect sensitive credentials
- Input validation prevents injection attacks
- Secure API communication with proper authentication
- Local data storage with DuckDB

### Privacy with Local LLMs
- Data never leaves your local machine
- No cloud dependencies for AI processing
- Complete control over model and data
- Offline capability for sensitive environments

## 🐛 Troubleshooting

### Common Issues

**ACLED API Authentication Error**
- Verify your credentials in `.env` file
- Check ACLED account status
- Ensure API key is current and valid

**Local LLM Connection Issues**
- Verify the LLM server is running
- Check endpoint URL and port
- Ensure model is loaded correctly
- Check system resources (RAM/GPU)

**Import Error in Visualizations**
- The app automatically cleans import statements
- Check that required modules are available
- Verify code generation is working properly

**No Data Returned**
- Check filter parameters
- Verify date ranges are valid
- Ensure selected countries/regions exist in dataset

**LLM Performance Issues**
- Reduce model size for better performance
- Use GPU acceleration if available
- Adjust batch sizes and context lengths
- Monitor system resources

### Debug Mode
Enable debug logging by setting:
```env
STREAMLIT_LOGGER_LEVEL=debug
LLM_DEBUG=true
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For technical support or questions:
- Create an issue in the GitHub repository
- Contact the development team
- Check the troubleshooting section above

## 🔄 Updates

### Recent Changes
- Added support for local LLMs (Llama, Ollama, etc.)
- Fixed ACLED API integration and parameter construction
- Enhanced security validation for code execution
- Improved data filtering and visualization capabilities
- Added comprehensive error handling

### Version History
- **v1.0.0**: Initial release with basic functionality
- **v1.1.0**: Added ACLED dashboard and AI analysis
- **v1.2.0**: Enhanced security and bug fixes
- **v1.3.0**: Added local LLM support and privacy features

---

**Built with ❤️ by the OSAA SMU Team**