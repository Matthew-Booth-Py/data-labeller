#!/usr/bin/env python3
"""Delete all documents via API."""

import requests

API_URL = "http://localhost:8000/api/v1"

def delete_all_documents():
    """Delete all documents from the system."""
    # Get all documents
    response = requests.get(f"{API_URL}/documents")
    response.raise_for_status()
    
    documents = response.json().get("documents", [])
    
    if not documents:
        print("No documents to delete.")
        return
    
    print(f"Found {len(documents)} documents to delete.\n")
    
    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        filename = doc.get("filename", "unknown")
        
        print(f"[{i}/{len(documents)}] Deleting: {filename} ({doc_id})...", end=" ")
        
        try:
            delete_response = requests.delete(f"{API_URL}/documents/{doc_id}")
            delete_response.raise_for_status()
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print(f"\nDeleted {len(documents)} documents.")

if __name__ == "__main__":
    delete_all_documents()
