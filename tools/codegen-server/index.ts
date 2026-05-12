// tools/codegen-server/index.ts — MCP code-execution server.
//
// Reference implementation. The Python harness in run.py uses harness/tools.py's
// in-process subprocess version. For real isolation, wrap each execution in a
// container with CPU/memory limits, no network, and a 30s wall clock — this
// stdio MCP wrapper is the right shape; the container plumbing is on you.
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "node:child_process";
import { z } from "zod";

const TIMEOUT_MS = 30_000;
const SANDBOX = process.env.SANDBOX_DIR ?? "./sandbox";

const server = new Server(
  { name: "codegen", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "codegen_run",
      description: "Execute a short Python program. Returns stdout, stderr, returncode. Timeout 30s. CWD is the sandbox.",
      inputSchema: {
        type: "object",
        properties: {
          code: { type: "string" },
          stdin: { type: "string", default: "" },
        },
        required: ["code"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  if (name !== "codegen_run") throw new Error(`unknown tool: ${name}`);

  const { code, stdin } = z.object({ code: z.string(), stdin: z.string().default("") }).parse(args);

  const result = await new Promise<{ stdout: string; stderr: string; returncode: number | null }>((resolve) => {
    const proc = spawn("python3", ["-c", code], { cwd: SANDBOX });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d));
    proc.stderr.on("data", (d) => (stderr += d));
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      resolve({ stdout, stderr: stderr + "\n[timeout 30s]", returncode: null });
    }, TIMEOUT_MS);
    proc.on("close", (rc) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, returncode: rc });
    });
    if (stdin) proc.stdin.write(stdin);
    proc.stdin.end();
  });

  return { content: [{ type: "text", text: JSON.stringify(result) }] };
});

await server.connect(new StdioServerTransport());
