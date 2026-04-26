# Tech Mahindra RFP Automation System

Welcome to the Tech Mahindra RFP Automation System! This project is designed to eliminate the manual, time-consuming process of responding to Request for Proposals (RFPs). 

Using a multi-agent AI architecture, this system reads client RFP documents, references past Tech Mahindra project knowledge, and automatically generates high-end, consulting-grade Word and PowerPoint proposal documents in a matter of minutes.

## What It Does
1. **Document Ingestion:** Upload any RFP document (PDF or raw text).
2. **AI Analysis:** A team of sequential AI agents (Analyst, Architect, Pricing, and Writer) breaks down the requirements, designs a technical architecture, estimates pricing, and writes a cohesive proposal.
3. **Knowledge Retrieval (RAG):** The system uses ChromaDB to search through past successful proposals to ground its answers in real Tech Mahindra data.
4. **Consulting-Grade Exports:** It automatically generates beautifully formatted, McKinsey/BCG-style Word Documents and PowerPoint presentations branded with Tech Mahindra colors and logos.

## Prerequisites
Before you start, make sure you have:
- Python 3.10+
- Node.js (for the React frontend)
- A Groq API Key (for the LLM)

## Installation & Setup

### 1. Backend (FastAPI) Setup
Open a terminal and run the following commands:
```bash
# Clone the repository (if you haven't already)
git clone https://github.com/cosmic-1234/TECH_M_PROPOSAL_GENERATOR.git
cd TECH_M_PROPOSAL_GENERATOR

# Install Python dependencies
pip install -r requirements.txt

# Set your API Key
# Create a .env file in the root directory and add:
# GROQ_API_KEY="your_api_key_here"

# Start the Backend Server
python server.py
```
*The server will start running on http://localhost:8000*

### 2. Frontend (React) Setup
Open a **new** terminal window and navigate to the frontend folder:
```bash
cd TECH_M_PROPOSAL_GENERATOR/frontend

# Install Node dependencies
npm install

# Start the frontend app
npm run dev
```
*The app will be available at http://localhost:5173*

## How to Use
1. Open `http://localhost:5173` in your browser.
2. Upload an RFP PDF.
3. Enter the Client Name.
4. Click **Generate Proposal**. 
5. Wait for the AI agents to complete their work, then navigate to the **Export** tab to download your fully formatted PowerPoint and Word documents.
