import OpenAI from "openai";
import Anthropic from "@anthropic-ai/sdk";
import type { LLMMessage } from "./types.js";

type Provider = "openai" | "anthropic";

function detectProvider(): Provider {
  if (process.env.ANTHROPIC_API_KEY) return "anthropic";
  if (process.env.OPENAI_API_KEY) return "openai";
  throw new Error(
    "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file."
  );
}

let openaiClient: OpenAI | null = null;
let anthropicClient: Anthropic | null = null;

function getOpenAIClient(): OpenAI {
  if (!openaiClient) {
    openaiClient = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
      baseURL: process.env.OPENAI_BASE_URL,
    });
  }
  return openaiClient;
}

function getAnthropicClient(): Anthropic {
  if (!anthropicClient) {
    anthropicClient = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
  }
  return anthropicClient;
}

const defaultModels: Record<Provider, string> = {
  openai: "gpt-5.4",
  anthropic: "claude-opus-4-6",
};

let totalTokens = { prompt: 0, completion: 0 };

/**
 * Send a chat completion request to the configured LLM provider.
 * Auto-detects provider from environment variables.
 * Returns the assistant's response text.
 */
export async function chat(messages: LLMMessage[]): Promise<string> {
  const provider = detectProvider();
  const model = process.env.MODEL || defaultModels[provider];

  if (provider === "anthropic") {
    return chatAnthropic(messages, model);
  }
  return chatOpenAI(messages, model);
}

async function chatOpenAI(
  messages: LLMMessage[],
  model: string
): Promise<string> {
  const response = await getOpenAIClient().chat.completions.create({
    model,
    messages,
    temperature: 0,
    max_completion_tokens: 4096,
  });

  if (response.usage) {
    totalTokens.prompt += response.usage.prompt_tokens;
    totalTokens.completion += response.usage.completion_tokens;
  }

  return response.choices[0]?.message?.content ?? "";
}

async function chatAnthropic(
  messages: LLMMessage[],
  model: string
): Promise<string> {
  const systemMessage = messages.find((m) => m.role === "system");
  const nonSystemMessages = messages.filter((m) => m.role !== "system");

  const response = await getAnthropicClient().messages.create({
    model,
    max_tokens: 4096,
    ...(systemMessage ? { system: systemMessage.content } : {}),
    messages: nonSystemMessages.map((m) => ({
      role: m.role as "user" | "assistant",
      content: m.content,
    })),
  });

  if (response.usage) {
    totalTokens.prompt += response.usage.input_tokens;
    totalTokens.completion += response.usage.output_tokens;
  }

  const textBlock = response.content.find((block) => block.type === "text");
  return textBlock ? textBlock.text : "";
}

/** Get cumulative token usage across all calls. */
export function getTokenUsage(): { prompt: number; completion: number } {
  return { ...totalTokens };
}

/** Reset token usage counters. */
export function resetTokenUsage(): void {
  totalTokens = { prompt: 0, completion: 0 };
}
