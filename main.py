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
import solana.rpc.async_api as solana_rpc
from solana.rpc.async_api import types
from solders.pubkey import Pubkey
import asyncio

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
        # analyses = await analyzer.analyze_functions(functions)
        
        # for func, analysis in zip(functions, analyses):
        for func in functions:
            # Skip if the analysis is empty
            # if len(analysis) > 0:
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
                "analysis": {} # analysis
            })
    
    return results


async def analyze_repo(
    repo_url: str,
    program_id: str,
    workspace_root: str,
    commit_hash: Optional[str] = None,
    openai_api_key: Optional[str] = None
) -> List[Dict]:
    """
    Analyze a Solana repository and return the analysis results.
    
    Args:
        repo_url: URL of the git repository
        program_id: Solana program ID
        workspace_root: Root directory of the workspace within the repo
        commit_hash: Optional specific commit to analyze
        openai_api_key: OpenAI API key. If not provided, will try to get from env
    
    Returns:
        List of dictionaries containing the analysis results
    """
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OpenAI API key not provided and not found in environment")

    # Create temp directory with UUID
    tmp_uuid = str(uuid.uuid4())
    tmp_dir = f"/tmp/{tmp_uuid}"
    print(f"Using temporary directory: {tmp_uuid}")
    
    try:
        # Clone repo
        try:
            repo = git.Repo.clone_from(repo_url, tmp_dir)
        except Exception as e:
            print(f"Error cloning repo, skipping {repo_url}: {e}")
            return []

        if commit_hash is not None and len(commit_hash) > 0 and commit_hash.lower() != "none":
            print(f"Checking out commit {commit_hash}")
            repo.git.checkout(commit_hash)
        
        # Get full workspace path
        repo_root = Path(tmp_dir).joinpath(Path(workspace_root))
        print(tmp_dir, workspace_root, repo_root)
        
        analyzer = SolanaAnalyzer(openai_api_key)
        
        # Find all Cargo workspaces
        results = []
        for root, dirs, files in os.walk(repo_root):
            if 'Cargo.toml' in files:
                # Check if src exists in this dir or any subdirs
                src_exists = 'src' in dirs
                if not src_exists:
                    for subdir in dirs:
                        if os.path.exists(os.path.join(root, subdir, 'src')):
                            src_exists = True
                            break
                if src_exists:
                    # Found a Cargo workspace, look for Rust files in src/
                    print(f"Found Cargo workspace at {root}")

                    rust_files = []
                    for src_root, _, src_files in os.walk(os.path.join(root, "src")):
                        rust_files = [
                            os.path.join(src_root, file)
                            for file in src_files
                            if file.endswith('.rs')
                        ]

                    # Process all files
                    dependencies = []
                    if os.path.exists(os.path.join(root, "Cargo.toml")):
                        cargo_toml = toml.load(os.path.join(root, "Cargo.toml"))
                        if 'dependencies' in cargo_toml:
                            dependencies = cargo_toml['dependencies']
                    else:
                        print("No Cargo.toml found")
                        print(root, dirs, files)
                        raise ValueError("No Cargo.toml found")

                    root_results = await process_files(analyzer, rust_files, program_id, repo_url, dependencies)
                    results.extend(root_results)
        
        return results
    
    finally:
        # Cleanup temp directory
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


def save_results_as_jsonl(results: List[Dict], program_id: str) -> int:
    """
    Save analysis results as both JSON and JSONL files.
    
    Args:
        results: List of analysis results to save
        program_id: Program ID used for filename
        
    Returns:
        Number of functions saved
    """
    # Save results as JSON
    output_path = f"jsonl/{program_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
        
    print(f"Analysis complete. Results saved to {output_path}")

    # Convert to JSONL format
    jsonl_output_path = f"jsonl/{program_id}.jsonl"
    count = 0
    with open(jsonl_output_path, 'w') as jsonl_file:
        for item in results:
            json.dump(item, jsonl_file)
            count += 1
            jsonl_file.write('\n')
            
    print(f"Converted to JSONL format: {jsonl_output_path}")
    print(f"Total functions saved: {count}")
    
    return count

@dataclass
class OtterVerifyBuildParams:
    address: str
    signer: str
    version: str
    git_url: str
    commit: str
    args: List[str]
    deploy_slot: int
    bump: int


async def find_explorer_pdas(signer: str) -> List[OtterVerifyBuildParams]:
    """
    Find all explorer PDAs in the results
    """

    connection = solana_rpc.AsyncClient(
        endpoint=os.getenv("SOLANA_RPC_URL")
    )
    PROGRAM_ID = Pubkey.from_string("verifycLy8mB96wd9wqq3WDXQwM4oU6r42Th37Db9fC")
    accounts = await connection.get_program_accounts(
        PROGRAM_ID,
        commitment="confirmed",
        encoding="base64",
        filters=[
            types.MemcmpOpts(
                offset=40,
                bytes=str(signer)
            )
        ]
    )

    print(f"Found {len(accounts.value)} accounts")
    results = []
    for account in accounts.value:
        results.append(deserialize_account_data(account.account.data[8:]))
    return results

def deserialize_account_data(data: bytes) -> OtterVerifyBuildParams:
    # Extract fields from binary data
    address = str(Pubkey(data[0:32]))
    signer = str(Pubkey(data[32:64]))
    
    # Get version string length and string
    version_len = int.from_bytes(data[64:68], 'little')
    version = data[68:68+version_len].decode('utf-8')
    current_pos = 68 + version_len
    
    # Get git url length and string
    git_url_len = int.from_bytes(data[current_pos:current_pos+4], 'little')
    git_url = data[current_pos+4:current_pos+4+git_url_len].decode('utf-8')
    current_pos += 4 + git_url_len
    
    # Get commit hash length and string
    commit_len = int.from_bytes(data[current_pos:current_pos+4], 'little')
    commit = data[current_pos+4:current_pos+4+commit_len].decode('utf-8')
    current_pos += 4 + commit_len
    
    # Get args list length
    args_len = int.from_bytes(data[current_pos:current_pos+4], 'little')
    current_pos += 4
    
    # Get each arg string
    args = []
    for _ in range(args_len):
        arg_len = int.from_bytes(data[current_pos:current_pos+4], 'little')
        arg = data[current_pos+4:current_pos+4+arg_len].decode('utf-8')
        args.append(arg)
        current_pos += 4 + arg_len
        
    deploy_slot = int.from_bytes(data[current_pos:current_pos+8], 'little')
    bump = data[current_pos+8]
    
    params = OtterVerifyBuildParams(
        address=address,
        signer=signer, 
        version=version,
        git_url=git_url,
        commit=commit,
        args=args,
        deploy_slot=deploy_slot,
        bump=bump
    )
    return params

async def main():
    # Load environment variables
    load_dotenv()
    
    # Configuration
    accounts = await find_explorer_pdas(Pubkey.from_string("CyJj5ejJAUveDXnLduJbkvwjxcmWJNqCuB9DR7AExrHn"))

    # results = await analyze_repo(
    #     repo_url="https://github.com/drift-labs/protocol-v2.git",
    #     program_id="dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
    #     workspace_root="./",
    #     commit_hash="e2191dfc09cc1783618238b1cd22a7015b3085a6"
    # )

    seen_repos = set()  
    for account in accounts:
        program_id = account.address
        repo_url = account.git_url
        workspace_root = "./"
        commit_hash = account.commit if len(account.commit) > 0 else None

        library_name = None
        for (i, arg) in enumerate(account.args):
            if arg.startswith("--library-name"):
                library_name = account.args[i+1]
                break

        if repo_url in seen_repos or (os.path.exists(f"jsonl/{program_id}.jsonl")):
            print(f"Skipping {repo_url} because it has already been seen")
            continue
        seen_repos.add(repo_url)
        # Go through args and find --library-name, and use next item as workspace root

        print(f"Analyzing {program_id} from {repo_url} with commit {commit_hash} @ {library_name}\n")
        if not all([repo_url, program_id, workspace_root]):
            raise ValueError("Missing required environment variables")

        results = await analyze_repo(
            repo_url=repo_url,
            program_id=program_id,
            workspace_root=workspace_root,
            commit_hash=commit_hash
        )
        save_results_as_jsonl(results, program_id)

if __name__ == "__main__":
    asyncio.run(main())
