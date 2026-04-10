#!/bin/bash
cd /home/site/wwwroot
streamlit run app/main.py --server.port="${PORT:-8000}" --server.address=0.0.0.0
