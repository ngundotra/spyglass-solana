#!/bin/bash

# Loop through all .jsonl files in the jsonl directory
for file in jsonl/*.jsonl; do
    if [ -f "$file" ]; then
        echo "Uploading $file to Typesense..."
        curl -H "X-TYPESENSE-API-KEY: ${TYPESENSE_API_KEY}" \
             -X POST \
             -T "$file" \
             "https://dwjy3th7epbrag1fp-1.a1.typesense.net/collections/raw/documents/import?action=create"
        echo -e "\nFinished uploading $file\n"
    fi
done