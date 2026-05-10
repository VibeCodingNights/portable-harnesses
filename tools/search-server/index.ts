// tools/search-server/index.ts — MCP web-search server, fronting Brave Search.
//
// Pre-built. Attendees do not modify. Per-attendee rate limiting happens at
// the LiteLLM proxy layer; this server is shared.
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

const BRAVE_KEY = process.env.BRAVE_API_KEY;
if (!BRAVE_KEY) console.error("[warn] BRAVE_API_KEY not set — search will return stub data");

const server = new Server(
  { name: "search", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "web_search",
      description: "Search the web. Returns title/url/snippet for each result.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string" },
          max_results: { type: "integer", default: 5 },
        },
        required: ["query"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  if (name !== "web_search") throw new Error(`unknown tool: ${name}`);

  const { query, max_results } = z
    .object({ query: z.string(), max_results: z.number().int().min(1).max(20).default(5) })
    .parse(args);

  if (!BRAVE_KEY) {
    return {
      content: [{ type: "text", text: JSON.stringify({ query, results: [{ title: "stub", url: "https://example.com", snippet: query }] }) }],
    };
  }

  const url = new URL("https://api.search.brave.com/res/v1/web/search");
  url.searchParams.set("q", query);
  url.searchParams.set("count", String(max_results));
  const r = await fetch(url, {
    headers: { "X-Subscription-Token": BRAVE_KEY, Accept: "application/json" },
  });
  if (!r.ok) {
    return { content: [{ type: "text", text: JSON.stringify({ query, results: [], error: `brave ${r.status}` }) }] };
  }
  const data: any = await r.json();
  const results = (data?.web?.results ?? []).slice(0, max_results).map((it: any) => ({
    title: it.title,
    url: it.url,
    snippet: it.description,
  }));
  return { content: [{ type: "text", text: JSON.stringify({ query, results }) }] };
});

await server.connect(new StdioServerTransport());
