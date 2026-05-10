// tools/filesystem-server/index.ts — MCP filesystem server, scoped to SANDBOX_DIR.
//
// Pre-built. Attendees do not modify. The local in-process equivalent lives in
// harness/tools.py and is what `python run.py` uses by default. This server is
// what the proxy exposes at /mcp/filesystem so MCP-native harnesses (Claude
// Desktop, etc.) can hit it.
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { promises as fs } from "node:fs";
import { resolve, join, dirname } from "node:path";
import { z } from "zod";

const SANDBOX = resolve(process.env.SANDBOX_DIR ?? "./sandbox");

function safe(p: string): string {
  const abs = resolve(SANDBOX, p);
  if (!abs.startsWith(SANDBOX)) throw new Error(`path escapes sandbox: ${p}`);
  return abs;
}

const server = new Server(
  { name: "filesystem", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "fs_read",
      description: "Read a text file from the sandbox.",
      inputSchema: { type: "object", properties: { path: { type: "string" } }, required: ["path"] },
    },
    {
      name: "fs_write",
      description: "Write a text file into the sandbox.",
      inputSchema: {
        type: "object",
        properties: { path: { type: "string" }, content: { type: "string" } },
        required: ["path", "content"],
      },
    },
    {
      name: "fs_list",
      description: "List entries in a sandbox directory.",
      inputSchema: { type: "object", properties: { path: { type: "string", default: "." } } },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  if (name === "fs_read") {
    const { path } = z.object({ path: z.string() }).parse(args);
    const content = await fs.readFile(safe(path), "utf-8");
    return { content: [{ type: "text", text: JSON.stringify({ path, content }) }] };
  }
  if (name === "fs_write") {
    const { path, content } = z.object({ path: z.string(), content: z.string() }).parse(args);
    const abs = safe(path);
    await fs.mkdir(dirname(abs), { recursive: true });
    await fs.writeFile(abs, content);
    return { content: [{ type: "text", text: JSON.stringify({ path, bytes: Buffer.byteLength(content) }) }] };
  }
  if (name === "fs_list") {
    const { path } = z.object({ path: z.string().default(".") }).parse(args);
    const entries = (await fs.readdir(safe(path))).sort();
    return { content: [{ type: "text", text: JSON.stringify({ path, entries }) }] };
  }
  throw new Error(`unknown tool: ${name}`);
});

await fs.mkdir(SANDBOX, { recursive: true });
await server.connect(new StdioServerTransport());
