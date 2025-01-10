import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/hljs";
type HitType = {
  file: string;
  function: {
    name: string;
    content: string;
    start_line: number;
    end_line: number;
    attributes: string[];
    docstring: string | null;
    repo_url: string;
    program_id: string;
    dependencies: Record<string, string | Record<string, string>>;
  };
  analysis: {
    category: string;
    description: string;
    sdk_usage: string;
  };
};

export function Hit({ hit }: { hit: HitType }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border border-gray-500/30 overflow-hidden rounded-lg sm:rounded-xl shadow-sm w-full bg-gray-800">
      {/* Header */}
      <div className="px-4 py-2.5 sm:px-6 no-scrollbar bg-gray-900">
        <p className="text-sm sm:text-base text-gray-100 font-medium font-mono break-words">
          {hit.function.name}
        </p>
      </div>

      {/* Main content */}
      <article className="text-left text-sm text-gray-200 px-4 sm:px-6 py-4 bg-gray-800 space-y-2">
        <div className="max-h-[300px] overflow-y-auto break-words">
          {/* <p className="mb-2">{hit.analysis.description}</p> */}
          {"dependencies" in hit.function &&
          "solana-program" in hit.function.dependencies ? (
            <p className="text-sm text-gray-400">
              solana-program:{" "}
              {typeof hit.function.dependencies["solana-program"] === "string"
                ? hit.function.dependencies["solana-program"]
                : JSON.stringify(hit.function.dependencies["solana-program"])}
            </p>
          ) : null}
          {/* <p className="text-sm">
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                hit.analysis.category === "account_derivation"
                  ? "bg-green-100 text-green-800"
                  : hit.analysis.category === "cpi"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {hit.analysis.category}
            </span>
          </p> */}
        </div>
      </article>

      {/* Source code header */}
      <div className="w-full bg-gray-900 flex flex-row justify-between px-4 sm:px-6 py-2 items-center font-regular text-sm sm:text-base text-gray-200">
        <button
          onClick={() => {
            setIsExpanded(!isExpanded);
          }}
          className="flex flex-row space-x-2.5 items-center justify-center hover:text-gray-300"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`w-5 h-5 transition-transform duration-200 transform ${
              isExpanded ? "rotate-180" : "rotate-90"
            }`}
          >
            <path d="M14.707 12.707a1 1 0 0 1-1.414 0L10 9.414l-3.293 3.293a1 1 0 0 1-1.414-1.414l4-4a1 1 0 0 1 1.414 0l4 4a1 1 0 0 1 0 1.414z" />
          </svg>
          <p>Source Code</p>
        </button>

        <a
          href={`${hit.function.repo_url}/blob/master/${hit.file}#L${hit.function.start_line}-L${hit.function.end_line}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center text-blue-400 hover:text-blue-300"
        >
          {hit.function.repo_url.substring(19)}/{hit.file}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth="1.5"
            stroke="currentColor"
            className="w-4 h-4 ml-2"
          >
            <path d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"></path>
          </svg>
        </a>
      </div>

      {/* Code block */}
      {isExpanded && (
        <>
          <div className="px-4 sm:px-6 py-4 bg-gray-800">
            <SyntaxHighlighter
              language="rust"
              style={oneDark}
              customStyle={{
                borderRadius: "0.375rem",
                padding: "1rem",
              }}
            >
              {hit.function.content}
            </SyntaxHighlighter>
            {"dependencies" in hit.function &&
            "solana-program" in hit.function.dependencies ? (
              <p className="text-sm text-gray-400">
                solana-program:{" "}
                {typeof hit.function.dependencies["solana-program"] === "string"
                  ? hit.function.dependencies["solana-program"]
                  : JSON.stringify(hit.function.dependencies["solana-program"])}
              </p>
            ) : null}
          </div>
          {/* Action buttons */}
          <div className="px-4 py-1 sm:px-6 overflow-auto no-scrollbar flex flex-row justify-end space-x-1 text-gray-400 bg-gray-900">
            <button className="flex flex-row items-center p-1 hover:bg-gray-700 rounded-md">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="2"
                stroke="currentColor"
                className="w-4 h-4"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"
                />
              </svg>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
