export interface SessionSummary {
  id: string;
  title: string;
  /** The agent the chat runs as; null for plain Synora (older chats or a deleted agent). */
  agent_id: string | null;
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

/** A file attached to a user message, as displayed (`url` is set for images). */
export interface Attachment {
  name: string;
  media_type: string;
  url?: string;
}

/** A file attached to an outgoing message: base64 content without the `data:` prefix. */
export interface OutgoingAttachment {
  name: string;
  media_type: string;
  data: string;
}

export interface UserMessage {
  role: 'user';
  text: string;
  attachments?: Attachment[];
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

/** The editable part of an agent profile. */
export interface AgentInput {
  name: string;
  role: string;
  icon: string;
  description: string;
  instructions: string;
  /** Tool names from /api/tools. */
  tools: string[];
  /** '' runs on the app's default provider. */
  provider: '' | Provider;
}

export interface AgentProfile extends AgentInput {
  id: string;
  created_at: string;
}

/** Body of POST /api/chat. */
export interface ChatRequest {
  message: string;
  attachments: OutgoingAttachment[];
  session_id: string | null;
  /** Only used when starting a new session. */
  agent_id: string | null;
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

export type Provider = 'anthropic' | 'openai';

export interface Health {
  model: string;
  effort: string;
  /** Providers the backend has keys for. */
  providers: Provider[];
  default_provider: Provider;
}

/** An event from the backend's /api/chat SSE stream. */
export interface AgentEvent {
  event: string;
  data: any;
}
