/**
 * CopilotKit runtime, self-hosted: relays the chat to the Python assistant over AG-UI.
 * No Copilot Cloud and no LLM keys here; the model is chosen by the API (LIX_MODEL).
 */
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

const runtime = new CopilotRuntime({
  agents: {
    default: new HttpAgent({ url: process.env.AGENT_URL ?? "http://localhost:8000/agent" }),
  },
});

const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" });

export const GET = (req: Request) => handler(req);
export const POST = (req: Request) => handler(req);
