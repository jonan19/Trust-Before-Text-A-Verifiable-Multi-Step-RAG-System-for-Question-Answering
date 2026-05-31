Trust Before Text — Document Store
====================================

Place your source documents in this directory.

Supported formats:
  - .txt   Plain text files
  - .pdf   PDF documents

The system will automatically ingest all documents in this folder
on first run (or when the ChromaDB collection is empty).

To re-ingest after adding new documents, delete the chroma_db/
directory and restart the system.

Example documents to add:
  - company_policy.pdf
  - employee_handbook.txt
  - compliance_guide.pdf
