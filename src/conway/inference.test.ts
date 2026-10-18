import { describe, it, expect, vi, beforeEach } from "vitest";
import { createInferenceClient } from "./inference.js";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function makeOkResponse(content = "ok") {
  return {
    ok: true,
    json: async () => ({
      id: "test",
      model: "llama3.3:70b",
      choices: [{ message: { role: "assistant", content, tool_calls: null }, finish_reason: "stop" }],
      usage: { prompt_tokens: 5, completion_tokens: 2, total_tokens: 7 },
    }),
    text: async () => "",
  };
}

describe("createInferenceClient — Ollama Cloud", () => {
  beforeEach(() => mockFetch.mockReset());

  it("sends Bearer OLLAMA_API_KEY when provider=ollama", async () => {
    mockFetch.mockResolvedValueOnce(makeOkResponse());

    const client = createInferenceClient({
      apiUrl: "https://api.conway.tech",
      apiKey: "",
      defaultModel: "llama3.3:70b",
      maxTokens: 4096,
      ollamaBaseUrl: "https://api.ollama.com",
      ollamaApiKey: "my-ollama-key",
    });

    await client.chat([{ role: "user", content: "test" }]);

    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = opts.headers as Record<string, string>;
    expect(url).toContain("ollama.com");
    expect(headers["Authorization"]).toBe("Bearer my-ollama-key");
  });

  it("uses Bearer 'ollama' when ollamaApiKey absent (local Ollama)", async () => {
    mockFetch.mockResolvedValueOnce(makeOkResponse());

    const client = createInferenceClient({
      apiUrl: "https://api.conway.tech",
      apiKey: "",
      defaultModel: "llama3.3:70b",
      maxTokens: 4096,
      ollamaBaseUrl: "http://localhost:11434",
    });

    await client.chat([{ role: "user", content: "test" }]);

    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = opts.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer ollama");
  });
});
