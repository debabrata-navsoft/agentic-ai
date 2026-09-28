import { Injectable, computed, inject, signal } from '@angular/core';

import { AgentApi } from './agent-api';
import {
  AgentEvent, AssistantMessage, ChatMessage, Health, KnowledgeDocument, Note, SessionSummary, ToolInfo,
} from '../models/chat.models';
import { reduceEvent } from '../utils/reduce-event';

@Injectable({ providedIn: 'root' })
export class ChatStore {
  private readonly api = inject(AgentApi);
  private abort: AbortController | null = null;

  readonly sessions = signal<SessionSummary[]>([]);
  readonly currentId = signal<string | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly running = signal(false);
  readonly notes = signal<Note[]>([]);
  readonly tools = signal<ToolInfo[]>([]);
  readonly health = signal<Health | null>(null);
  readonly error = signal<string | null>(null);
  readonly documents = signal<KnowledgeDocument[]>([]);
  readonly supportedTypes = signal<string[]>([]);
  readonly uploading = signal<string | null>(null);
  readonly uploadError = signal<string | null>(null);

  readonly currentTitle = computed(
    () => this.sessions().find((s) => s.id === this.currentId())?.title ?? 'New chat',
  );

  async init() {
    try {
      const [health, tools] = await Promise.all([this.api.health(), this.api.tools()]);
      this.health.set(health);
      this.tools.set(tools);
      await Promise.all([this.refreshSessions(), this.refreshNotes(), this.refreshDocuments()]);
    } catch {
      this.error.set('Cannot reach the backend. Start it with: uvicorn app.main:app --port 8000');
    }
  }

  async refreshSessions() {
    this.sessions.set(await this.api.sessions());
  }

  async refreshNotes() {
    this.notes.set(await this.api.notes());
  }

  async refreshDocuments() {
    const list = await this.api.documents();
    this.documents.set(list.documents);
    this.supportedTypes.set(list.supported);
  }

  /** Upload files one by one into the RAG knowledge base (each is chunked + embedded server-side). */
  async upload(files: File[]) {
    this.uploadError.set(null);
    for (const file of files) {
      this.uploading.set(file.name);
      try {
        await this.api.uploadDocument(file);
      } catch (e: any) {
        this.uploadError.set(`${file.name}: ${e?.error?.detail ?? e?.message ?? 'upload failed'}`);
      }
    }
    this.uploading.set(null);
    await this.refreshDocuments();
  }

  async deleteDocument(id: string) {
    await this.api.deleteDocument(id);
    await this.refreshDocuments();
  }

  newChat() {
    if (this.running()) return;
    this.currentId.set(null);
    this.messages.set([]);
  }

  async open(id: string) {
    if (this.running() || id === this.currentId()) return;
    const session = await this.api.session(id);
    this.currentId.set(id);
    this.messages.set(session.messages);
  }

  async deleteSession(id: string) {
    await this.api.deleteSession(id);
    if (id === this.currentId()) this.newChat();
    await this.refreshSessions();
  }

  async deleteNote(id: number) {
    await this.api.deleteNote(id);
    await this.refreshNotes();
  }

  stop() {
    this.abort?.abort();
  }

  async send(text: string) {
    text = text.trim();
    if (!text || this.running()) return;

    this.error.set(null);
    this.running.set(true);
    this.abort = new AbortController();
    const assistant: AssistantMessage = { role: 'assistant', parts: [], running: true };
    this.messages.update((m) => [...m, { role: 'user', text }, assistant]);

    let stepStart = 0;
    const onEvent = (ev: AgentEvent) => {
      if (ev.event === 'session') {
        this.currentId.set(ev.data.id);
        return;
      }
      if (ev.event === 'step_start') {
        stepStart = this.lastAssistant().parts.length;
        return;
      }
      this.patchLastAssistant((msg) => reduceEvent(msg, ev, stepStart));
    };

    try {
      await this.api.chat(text, this.currentId(), onEvent, this.abort.signal);
    } catch (e) {
      const aborted = e instanceof DOMException && e.name === 'AbortError';
      this.patchLastAssistant((msg) =>
        reduceEvent(msg, aborted
          ? { event: 'notice', data: { message: 'Stopped.' } }
          : { event: 'error', data: { message: (e as Error).message } }, stepStart),
      );
    } finally {
      this.patchLastAssistant((msg) => ({ ...msg, running: false }));
      this.running.set(false);
      this.abort = null;
      // The agent may have created a session, renamed it, or written notes.
      this.refreshSessions();
      this.refreshNotes();
    }
  }

  private lastAssistant(): AssistantMessage {
    return this.messages().at(-1) as AssistantMessage;
  }

  private patchLastAssistant(fn: (msg: AssistantMessage) => AssistantMessage) {
    this.messages.update((m) => [...m.slice(0, -1), fn(m.at(-1) as AssistantMessage)]);
  }
}
