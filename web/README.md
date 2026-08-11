# Clinician Directory — Vercel MCP Client

Lightweight Next.js chat UI that calls the Hugging Face Gradio Space MCP tool:

- Tool: `clinician_directory_agent_chat`
- Transport: Streamable HTTP
- URL: `https://robcr-clinician-directory-agent.hf.space/gradio_api/mcp/`

## Local

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy on Vercel

From the `web/` directory (or set Root Directory to `web` in the Vercel project):

```bash
npx vercel
```

Optional env var:

| Name | Default |
|------|---------|
| `MCP_SERVER_URL` | `https://robcr-clinician-directory-agent.hf.space/gradio_api/mcp/` |

Set `maxDuration` friendly region; chat calls the remote Space and may take several seconds.
