# Spyglass - Solana Program Search

This tool analyzes Solana programs by extracting and parsing Rust functions from their source code.
It can either analyze a specific repository or fetch all verified programs uploaded by a signer from the Solana chain.

## Setup

1. Install dependencies using `uv`:

2. Create and configure your environment:
   - Copy `.env.example` to `.env`
   - Add your preferred Solana RPC URL (e.g., QuickNode, Helius, etc.)
   - Add your OpenAI API key if using AI analysis features

```bash
cp .env.example .env
```

3. Run the analyzer:

```bash
uv run main.py
```

4. Upload results to the search index:

```bash
TYPESENSE_API_KEY=<your-api-key> && ./upload.sh
```
