import { NextResponse } from "next/server";
import { callClinicianDirectoryChat, type ChatTurn } from "@/lib/mcp";

export const runtime = "nodejs";
export const maxDuration = 60;

type Body = {
  message?: unknown;
  history?: unknown;
};

function isChatTurn(value: unknown): value is ChatTurn {
  if (!value || typeof value !== "object") return false;
  const role = (value as { role?: unknown }).role;
  const content = (value as { content?: unknown }).content;
  return (
    (role === "user" || role === "assistant") && typeof content === "string"
  );
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const message = typeof body.message === "string" ? body.message.trim() : "";
  if (!message) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  const history = Array.isArray(body.history)
    ? body.history.filter(isChatTurn)
    : [];

  try {
    const reply = await callClinicianDirectoryChat(message, history);
    return NextResponse.json({
      message: { role: "assistant", content: reply },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Chat failed";
    return NextResponse.json({ error: detail }, { status: 502 });
  }
}
