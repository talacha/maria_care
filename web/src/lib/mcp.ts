import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const DEFAULT_MCP_URL =
  "https://robcr-clinician-directory-agent.hf.space/gradio_api/mcp/";

/** Gradio prefixes api_name with the Blocks title slug. */
const TOOL_NAME = "clinician_directory_agent_chat";
const TOOL_NAME_FALLBACKS = [
  TOOL_NAME,
  "clinician_directory_agent_clinician_directory_agent_chat",
];

export type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

function mcpUrl(): string {
  return process.env.MCP_SERVER_URL?.trim() || DEFAULT_MCP_URL;
}

function extractText(result: unknown): string {
  if (!result || typeof result !== "object") {
    return "No response from the clinician directory agent.";
  }

  const content = (result as { content?: unknown }).content;
  if (!Array.isArray(content)) {
    return "No response from the clinician directory agent.";
  }

  const parts = content
    .filter(
      (part): part is { type: string; text: string } =>
        !!part &&
        typeof part === "object" &&
        (part as { type?: string }).type === "text" &&
        typeof (part as { text?: unknown }).text === "string",
    )
    .map((part) => part.text);

  const text = parts.join("\n").trim();
  return text || "No response from the clinician directory agent.";
}

export async function callClinicianDirectoryChat(
  message: string,
  history: ChatTurn[] = [],
): Promise<string> {
  const client = new Client({
    name: "wonderful-web",
    version: "1.0.0",
  });

  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl()));

  try {
    await client.connect(transport);
    const listed = await client.listTools();
    const available = new Set(listed.tools.map((tool) => tool.name));
    const toolName =
      TOOL_NAME_FALLBACKS.find((name) => available.has(name)) ??
      listed.tools.find((tool) => tool.name.endsWith("_chat"))?.name;

    if (!toolName) {
      throw new Error(
        `No clinician chat MCP tool found. Available: ${[...available].join(", ") || "(none)"}`,
      );
    }

    const result = await client.callTool({
      name: toolName,
      arguments: {
        message,
        history_json: JSON.stringify(history),
      },
    });

    if (
      result &&
      typeof result === "object" &&
      "isError" in result &&
      (result as { isError?: boolean }).isError
    ) {
      throw new Error(extractText(result));
    }

    return extractText(result);
  } finally {
    await client.close().catch(() => undefined);
  }
}
