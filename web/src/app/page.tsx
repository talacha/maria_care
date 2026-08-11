"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

const EXAMPLES = [
  "Find a cardiologist in Cluj-Napoca who speaks English",
  "Who are the highest-rated dermatologists in Bucharest?",
  "What specialities are available?",
  "What is the weather in Paris?",
];

export default function Home() {
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending, error]);

  async function send(message: string) {
    const trimmed = message.trim();
    if (!trimmed || pending) return;

    const history = messages;
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setPending(true);
    setError(null);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, history }),
      });
      const data = (await res.json()) as {
        message?: ChatTurn;
        error?: string;
      };
      if (!res.ok) {
        throw new Error(data.error || "Request failed");
      }
      if (!data.message?.content) {
        throw new Error("Empty assistant response");
      }
      setMessages((prev) => [...prev, data.message as ChatTurn]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setPending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-5 px-4 py-8">
      <header>
        <p className="text-sm font-medium tracking-wide text-[var(--muted)]">
          Vercel + Gradio MCP
        </p>
        <h1 className="display mt-2 text-4xl font-semibold tracking-tight sm:text-5xl">
          Clinician Directory Agent
        </h1>
        <p className="mt-3 max-w-xl text-[var(--muted)]">
          This UI calls{" "}
          <code className="text-[var(--ink)]">clinician_directory_agent_chat</code>{" "}
          on the Hugging Face Space over Streamable HTTP MCP.
        </p>
      </header>

      <section className="flex min-h-[60vh] flex-1 flex-col overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel)] shadow-[0_18px_50px_rgba(19,33,43,0.08)] backdrop-blur">
        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-5">
          {messages.length === 0 && (
            <p className="text-center text-sm text-[var(--muted)]">
              Ask a directory question to start. Out-of-scope topics are refused.
            </p>
          )}
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`max-w-[92%] whitespace-pre-wrap rounded-2xl px-3.5 py-3 text-[0.98rem] leading-relaxed ${
                message.role === "user"
                  ? "ml-auto bg-[var(--user)] text-[#f5f8fa]"
                  : "mr-auto border border-[var(--line)] bg-[var(--bot)]"
              }`}
            >
              {message.content}
            </div>
          ))}
          {pending && (
            <p className="text-sm text-[var(--muted)]">Thinking via MCP…</p>
          )}
          {error && (
            <p className="rounded-xl border border-[rgba(138,59,45,0.25)] bg-[#f8e8e4] px-3 py-2 text-[var(--danger)]">
              {error}
            </p>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="space-y-3 border-t border-[var(--line)] bg-white/55 p-3.5">
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                disabled={pending}
                onClick={() => void send(example)}
                className="rounded-full border border-[var(--line)] bg-transparent px-3 py-1.5 text-sm text-[var(--ink)] disabled:opacity-50"
              >
                {example}
              </button>
            ))}
          </div>
          <form onSubmit={onSubmit} className="grid grid-cols-[1fr_auto] gap-2.5">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={2}
              required
              placeholder="Ask about clinicians or clinics…"
              className="resize-none rounded-xl border border-[var(--line)] bg-white px-3 py-3 text-[var(--ink)] outline-none focus:border-[var(--accent)] focus:outline focus:outline-2 focus:outline-[rgba(15,106,106,0.35)]"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send(input);
                }
              }}
            />
            <button
              type="submit"
              disabled={pending}
              className="rounded-xl bg-[var(--accent)] px-5 font-semibold text-[var(--accent-ink)] disabled:opacity-55"
            >
              Send
            </button>
          </form>
        </div>
      </section>

      <footer className="text-sm text-[var(--muted)]">
        MCP:{" "}
        <a
          className="text-[var(--accent)] underline-offset-2 hover:underline"
          href="https://robcr-clinician-directory-agent.hf.space/gradio_api/mcp/"
          target="_blank"
          rel="noreferrer"
        >
          robcr/clinician-directory-agent
        </a>
      </footer>
    </main>
  );
}
