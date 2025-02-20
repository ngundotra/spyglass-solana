"use client";

import Image from "next/image";
import {
  InstantSearch,
  SearchBox,
  InfiniteHits,
  Stats,
  RefinementList,
} from "react-instantsearch";
import TypesenseInstantSearchAdapter from "typesense-instantsearch-adapter";
import { Hit } from "@/components/Hit";

import { Panel } from "@/components/Panel";

import "instantsearch.css/themes/reset.css";
import "instantsearch.css/themes/satellite.css";

const typesenseInstantsearchAdapter = new TypesenseInstantSearchAdapter({
  server: {
    apiKey: "hSFwFWIfe1AXJLwzu1gRKKktLa1a9iaa", // Be sure to use the search-only-api-key
    nodes: [
      {
        host: "dwjy3th7epbrag1fp-1.a1.typesense.net",
        port: 443,
        protocol: "https",
      },
    ],
  },
  additionalSearchParameters: {
    query_by: "function.repo_url,function.name",
    // @ts-expect-error This is a bug in the typesense-instantsearch-adapter package
    infix: "always,always",
  },
});

const searchClient = typesenseInstantsearchAdapter.searchClient;

export default function Home() {
  return (
    <div className="min-h-screen font-[family-name:var(--font-geist-sans)]">
      {/* Fixed header */}
      {/* @ts-expect-error This is a bug in the typesense-instantsearch-adapter package */}
      <InstantSearch searchClient={searchClient} indexName="raw">
        {/* Fixed header */}
        <div className="fixed top-0 left-0 right-0 z-50 bg-[var(--background)] p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex flex-col items-center">
              <div className="flex items-center gap-3">
                <Image
                  src="/spyglass.svg"
                  alt="Spyglass logo"
                  width={40}
                  height={40}
                  className="w-8 h-8 sm:w-10 sm:h-10 opacity-80 invert"
                />
                <h1 className="text-5xl sm:text-7xl font-medium tracking-tight bg-gradient-to-r from-gray-200 to-gray-400 bg-clip-text text-transparent">
                  SPYGLASS
                </h1>
              </div>
              <p className="text-sm text-gray-400 mt-2">
                Find and reuse Solana program code
              </p>
            </div>
            <div className="mt-4">
              {/* @ts-expect-error This is a bug in the typesense-instantsearch-adapter package */}
              <SearchBox
                placeholder="Search for Solana functions..."
                className="w-full"
              />
              {/* @ts-expect-error This is a bug in the typesense-instantsearch-adapter package */}
              <Stats />
            </div>
          </div>
        </div>

        <div className="flex pt-[200px]">
          {/* Resizable left sidebar */}
          <div
            className="fixed left-0 top-[200px] bottom-0 overflow-y-auto bg-[var(--background)] border-r border-gray-700 p-4"
            style={{ width: "var(--sidebar-width, 256px)" }} // Default 256px (64 * 4)
          >
            <div className="flex flex-col gap-4">
              {/* <Panel header="Category">
                <RefinementList
                  attribute="analysis.category"
                  limit={5}
                  showMore={true}
                />
              </Panel> */}

              <Panel header="Repository">
                {/* @ts-expect-error This is a bug in the typesense-instantsearch-adapter package */}
                <RefinementList
                  attribute="function.repo_url"
                  limit={5}
                  showMore={true}
                  transformItems={(items) => {
                    return items.map((item) => ({
                      ...item,
                      label: item.value.split("/").slice(-2).join("/"),
                    }));
                  }}
                />
              </Panel>
            </div>

            {/* Resizer handle */}
            <div
              className="absolute top-0 right-0 bottom-0 w-1 cursor-ew-resize hover:bg-gray-600 active:bg-gray-500"
              onMouseDown={(e) => {
                const startX = e.clientX;
                const startWidth = parseInt(
                  getComputedStyle(e.currentTarget.parentElement!).width
                );

                const onMouseMove = (e: MouseEvent) => {
                  const newWidth = startWidth + (e.clientX - startX);
                  const clampedWidth = Math.max(200, Math.min(400, newWidth));
                  document.documentElement.style.setProperty(
                    "--sidebar-width",
                    `${clampedWidth}px`
                  );
                  // Update main content margin dynamically
                  document.documentElement.style.setProperty(
                    "--main-margin",
                    `${clampedWidth + 16}px` // Add 16px for padding
                  );
                };

                const onMouseUp = () => {
                  document.removeEventListener("mousemove", onMouseMove);
                  document.removeEventListener("mouseup", onMouseUp);
                };

                document.addEventListener("mousemove", onMouseMove);
                document.addEventListener("mouseup", onMouseUp);
              }}
            />
          </div>

          {/* Main content */}
          <main
            className="flex-1 pb-24"
            style={{ marginLeft: "var(--main-margin, 272px)" }} // Default is sidebar width (256px) + padding
          >
            <div className="h-full py-4 pr-8 overflow-auto">
              <div className="w-full max-w-full">
                {/* @ts-expect-error This is a bug in the typesense-instantsearch-adapter package */}
                <InfiniteHits hitComponent={Hit} showPrevious={false} />
              </div>
            </div>
          </main>
        </div>
      </InstantSearch>

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 flex gap-6 flex-wrap items-center justify-center p-8 bg-[var(--background)]">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://docs.solana.com"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/globe.svg"
            alt="Globe icon"
            width={16}
            height={16}
          />
          Solana Docs →
        </a>
      </footer>
    </div>
  );
}
