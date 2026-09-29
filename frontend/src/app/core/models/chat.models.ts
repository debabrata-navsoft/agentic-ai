export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface TextPart {
  type: 'text' | 'thinking';
  text: string;
}

export interface ToolPart {
  type: 'tool';
  id: string;
  name: string;
  server: boolean;
  input: unknown;
  output: string | null;
  is_error: boolean;
}

export interface NoticePart {
  type: 'notice';
  text: string;
  tone: 'info' | 'warn' | 'error';
}

export type Part = TextPart | ToolPart | NoticePart;

export interface UserMessage {
  role: 'user';
  text: string;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
}

export interface AssistantMessage {
  role: 'assistant';
  parts: Part[];
  running?: boolean;
  usage?: Usage;
  steps?: number;
  /** Part index where the current model step began (for `step_discard`). */
  stepStart?: number;
}

export type ChatMessage = UserMessage | AssistantMessage;

export interface SessionDetail extends SessionSummary {
  messages: ChatMessage[];
}

export interface Note {
  id: number;
  title: string;
  content: string;
  tags: string[];
  created_at: string;
}

export interface KnowledgeDocument {
  id: string;
  name: string;
  size: number;
  chunks: number;
  created_at: string;
}

export interface DocumentList {
  documents: KnowledgeDocument[];
  supported: string[];
}

export interface ToolInfo {
  name: string;
  label: string;
  description: string;
  server: boolean;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'user' | 'admin';
  disabled: boolean;
  created_at: string;
}

export interface Health {
  model: string;
  effort: string;
}

/** An event from the backend's /api/chat SSE stream. */
export interface AgentEvent {
  event: string;
  data: any;
}
