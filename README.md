# Trust Before Text - Retrieval System

A modular and highly interactive Retrieval-Augmented Generation (RAG) system with dynamic data ingestion capabilities and a premium dashboard.

## 🚀 Features

*   **Dynamic Data Ingestion**: Easily add new `.txt` files containing knowledge to the system during runtime without needing to completely restart the index.
*   **Modern Web Dashboard**: A high-end, dark-themed UI built with HTML/CSS/JS leveraging glassmorphism and real-time updates.
*   **FastAPI Backend**: A robust routing system handling searches, uploads, and data aggregation for frontend visualization.
*   **Vector Similarity Search**: Converts text chunks into high-dimension vector embeddings using Sentence-Transformers, and matches queries using FAISS (Facebook AI Similarity Search) for maximum recall.
*   **Interactive CLI Mode**: A drop-in terminal script for users who prefer interacting or querying the system through a native shell.

## 💻 Technology Stack

*   **Backend Framework**: FastAPI (Python)
*   **Machine Learning**: `sentence-transformers` (all-MiniLM-L6-v2) for embeddings
*   **Vector Store**: FAISS (`faiss-cpu`) for efficient memory-mapped similarity search
*   **Frontend**: Vanilla HTML5, CSS3, JavaScript (Fetch API)

## 🛠️ Installation & Setup

1. **Clone the repository / Enter folder**
   Ensure you are in the project root path (`LY Project work`).

2. **Create a Virtual Environment (Optional but Recommended)**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Install Dependencies**
   Run the following pip command to install all necessary backend libraries:
   ```powershell
   pip install fastapi uvicorn sentence-transformers faiss-cpu PyPDF2 python-multipart requests
   ```

## 🏃 How to Run

There are two primary ways to run the system: using the visual dashboard or the interactive CLI.

### Option 1: Web Dashboard (Recommended)

1.  **Start the API Server**:
    In your terminal, launch the FastAPI server using Uvicorn (make sure you are in the project folder):
    ```powershell
    python api.py
    ```
    *The server will start on `http://localhost:8000`.*

2.  **Open the User Interface**:
    Navigate to the `frontend` directory and simply open **`index.html`** in any modern web browser (Chrome, Edge, Firefox).

3.  **Explore**:
    *   Drag and drop `.txt` files into the "Add Knowledge" zone.
    *   Ask a question using the search bar to query the embedded chunks.

### Option 2: Interactive CLI Mode

If you prefer testing or using the module entirely from a terminal:

```powershell
python interactive_qa.py
```
This script will prompt you to enter questions and provide the top 3 pieces of evidence for each query directly in your console. You can also type `add` to dynamically insert new `.txt` files inside the running session!

## 🧩 Architecture

1.  **Document Preprocessing** (`document_preprocessing.py`): Handles loading `.txt`/`.pdf`/`.docx` files and generating manageable overlapping chunks while preserving metadata.
2.  **Retrieval Module** (`retrieval_module.py`): Orchestrates generating vector embeddings and interacting with the active Vector Index.
3.  **API Layer** (`api.py`): The FastAPI wrapper bridging the machine-learning backends to standard HTTP requests (`/upload`, `/query`, `/stats`). 
kdhsiahidqdqdv  
