from pathlib import Path
import git
import shutil
import uuid
import toml
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
from tree_sitter import Language, Parser
from tree_sitter_rust import language as rust_language
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio
from concurrent.futures import ThreadPoolExecutor


@dataclass
class RustFunction:
    name: str
    content: str
    start_line: int
    end_line: int
    attributes: List[str]  # For catching things like #[derive(...)] or #[account]
    docstring: Optional[str]

class RustParser:
    def __init__(self):
        self.parser = Parser(Language(rust_language()))

    def extract_docstring(self, node, source_code: str) -> Optional[str]:
        """Extract docstring comments preceding a function."""
        current = node
        comments = []
        
        while current.prev_sibling and current.prev_sibling.type == 'line_comment':
            comments.insert(0, source_code[current.prev_sibling.start_byte:current.prev_sibling.end_byte])
            current = current.prev_sibling
            
        return '\n'.join(comments) if comments else None

    def extract_attributes(self, node, source_code: str) -> List[str]:
        """Extract Rust attributes like #[derive(...)] or #[account]."""
        current = node
        attributes = []
        
        while current.prev_sibling and current.prev_sibling.type == 'attribute_item':
            attr_text = source_code[current.prev_sibling.start_byte:current.prev_sibling.end_byte]
            attributes.insert(0, attr_text)
            current = current.prev_sibling
            
        return attributes

    def parse_file(self, file_path: str) -> List[RustFunction]:
        """Parse a Rust file and extract all functions with their metadata."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = self.parser.parse(bytes(content, 'utf8'))
        functions = []

        # Query to find all function definitions
        query = self.parser.language.query("""
            (function_item) @function
        """)

        # Find all function nodes
        matches = query.matches(tree.root_node)
        for match in matches:
            # Get the function node from the match dictionary
            func_node = match[1]['function'][0]  # Access the Node from the dictionary
            name_node = func_node.child_by_field_name('name')
            
            if name_node:
                # Get the full function text
                func_text = content[func_node.start_byte:func_node.end_byte]
                
                # Extract line numbers
                start_line = content[:func_node.start_byte].count('\n') + 1
                end_line = content[:func_node.end_byte].count('\n') + 1
                
                # Get docstring and attributes
                docstring = self.extract_docstring(func_node, content)
                attributes = self.extract_attributes(func_node, content)
                
                function = RustFunction(
                    name=name_node.text.decode('utf8'),
                    content=func_text,
                    start_line=start_line,
                    end_line=end_line,
                    attributes=attributes,
                    docstring=docstring
                )
                functions.append(function)

        return functions

class SolanaAnalyzer:
    def __init__(self, openai_api_key: str):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.parser = RustParser()

    async def analyze_function(self, function: RustFunction) -> Dict:
        """Send function to OpenAI for analysis."""
        system_prompt = """
        You are a Solana smart contract analyzer focusing on tool and SDK usage patterns.

        You will be given a Rust function and its attributes, your job is to analyze functions 
        that have one of the following key categories:
        - (account_derivation) Account Derivations (Program Derived Address, account address validation, etc)
        - (cpi) CPIs (invoke, invoke_signed, anchor cpi calls, etc)

        If the function is not one of the above categories, use the skip tool.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                    Function name: {function.name}
                    Attributes: {function.attributes}
                    Docstring: {function.docstring}
                    
                    Code:
                    {function.content}
                    """}
                ],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "analyze_function",
                        "description": "Store useful information about the function for developer searchability",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "category": {
                                    "type": "string",
                                    "description": "One of the following categories: account_derivation, cpi"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Brief description of the function purpose"
                                }
                            },
                            "required": ["category", "description"],
                        },
                    }
                }, {"type":"function", "function":{"name": "skip", "description": "Skip the function analysis", "parameters": {}}}],
                tool_choice="required"
            )
            
            # return json.loads(response.choices[0].message.content)
            functionArgs = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
            print(functionArgs)
            return functionArgs
        except Exception as e:
            print(f"Error analyzing function {function.name}: {e}")
            return {"error": str(e)}
    
    async def analyze_functions(self, functions: List[RustFunction]) -> List[Dict]:
        """Analyze multiple functions concurrently."""
        tasks = [self.analyze_function(func) for func in functions]
        return await asyncio.gather(*tasks) 


async def process_files(analyzer: SolanaAnalyzer, files: List[str], program_id: str, repo_url: str, dependencies: List[Dict]) -> List[Dict]:
    results = []
    
    for file_path in files:
        print(f"Processing {file_path}")
        functions = analyzer.parser.parse_file(file_path)
        
        # Analyze all functions in the file concurrently
        analyses = await analyzer.analyze_functions(functions)
        
        for func, analysis in zip(functions, analyses):
            # Skip if the analysis is empty
            if len(analysis) > 0:
                results.append({
                    "file": file_path[42:],
                    "function": {
                        "name": func.name,
                        "content": func.content,
                        "start_line": func.start_line,
                        "end_line": func.end_line,
                        "attributes": func.attributes,
                        "docstring": func.docstring,
                        "repo_url": repo_url,
                        "program_id": program_id,
                        "dependencies": dependencies,
                    },
                    "analysis": analysis
                })
    
    return results


async def main():
    # Load environment variables
    load_dotenv()
    
    # Configuration
    repo_url = os.getenv("REPO_URL")
    program_id = os.getenv("PROGRAM_ID") 
    workspace_root = os.getenv("WORKSPACE_ROOT")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not all([repo_url, program_id, workspace_root, OPENAI_API_KEY]):
        raise ValueError("Missing required environment variables")
        
    # Create temp directory with UUID
    tmp_uuid = str(uuid.uuid4())
    tmp_dir = f"/tmp/{tmp_uuid}"
    print(f"Using temporary directory: {tmp_uuid}")
    
    # Clone repo
    repo = git.Repo.clone_from(repo_url, tmp_dir)
    
    # Get full workspace path
    repo_root = Path(tmp_dir).joinpath(Path(workspace_root))
    print(tmp_dir, workspace_root, repo_root)
    
    analyzer = SolanaAnalyzer(OPENAI_API_KEY)
    
    # Find all Rust files
    rust_files = []
    for root, _, files in os.walk(os.path.join(repo_root, "src")):
        rust_files.extend(
            os.path.join(root, file)
            for file in files
            if file.endswith('.rs')
        )
    
    # Process all files
    dependencies = toml.load(os.path.join(repo_root, "Cargo.toml"))['dependencies']
    results = await process_files(analyzer, rust_files, program_id, repo_url, dependencies)
    
    # Save results
    output_path = f"{program_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
        
    print(f"Analysis complete. Results saved to {output_path}")
    
    # Cleanup
    shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    asyncio.run(main())
