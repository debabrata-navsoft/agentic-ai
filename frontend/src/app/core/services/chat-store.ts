import { Injectable, computed, inject, signal } from '@angular/core';

import { AgentApi, ApiError } from './agent-api';
import { AuthStore } from './auth-store';
import {
  AgentEvent,
  AgentInput,
  AgentProfile,
  AssistantMessage,
  ChatMessage,
  Health,
  KnowledgeDocument,
  Note,
  OutgoingAttachment,
  SessionSummary,
  ToolInfo,
} from '../models/chat.models';
import { toDisplay } from '../utils/attachments';
import { reduceEvent } from '../utils/reduce-event';

const NOTE_TOOLS = new Set(['save_note', 'delete_note']);

export type ActiveView = 'chat' | 'agents' | 'docs' | 'memory' | 'tools' | 'users';

@Injectable({ providedIn: 'root' })
export class ChatStore {
  private readonly api = inject(AgentApi);
  private readonly auth = inject(AuthStore);
  private abort: AbortController | null = null;

  readonly activeView = signal<ActiveView>('chat');
  readonly sessions = signal<SessionSummary[]>([]);
  readonly currentId = signal<string | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly running = signal(false);
  readonly notes = signal<Note[]>([]);
  readonly tools = signal<ToolInfo[]>([]);
  readonly health = signal<Health | null>(null);
  readonly error = signal<string | null>(null);
  readonly agents = signal<AgentProfile[]>([]);
  /** The agent for the open chat, or for the next new chat; null is plain Synora. */
  readonly agentId = signal<string | null>(null);
  readonly currentAgent = computed(
    () => this.agents().find((a) => a.id === this.agentId()) ?? null,
  );
  readonly documents = signal<KnowledgeDocument[]>([]);
  readonly supportedTypes = signal<string[]>([]);
  readonly uploading = signal<string | null>(null);
  readonly uploadError = signal<string | null>(null);

  /** Tool name → display label, from the backend's tool catalog. */
  readonly toolLabels = computed(() => new Map(this.tools().map((t) => [t.name, t.label])));

  readonly currentTitle = computed(
    () => this.sessions().find((s) => s.id === this.currentId())?.title ?? 'New chat',
  );

  async init() {
    try {
      const [health, tools] = await Promise.all([this.api.health(), this.api.tools()]);
      this.health.set(health);
      this.tools.set(tools);
      await Promise.all([
        this.refreshSessions(),
        this.refreshNotes(),
        this.refreshDocuments(),
        this.refreshAgents(),
      ]);
    } catch {
      if (this.auth.user()) {
        this.error.set('Cannot reach the backend. Start it with: uvicorn app.main:app --port 8000');
      }
    }
  }

  /** Forget everything loaded for the previous user (on sign-out). */
  reset() {
    this.abort?.abort();
    this.sessions.set([]);
    this.currentId.set(null);
    this.messages.set([]);
    this.notes.set([]);
    this.tools.set([]);
    this.documents.set([]);
    this.agents.set([]);
    this.agentId.set(null);
    this.error.set(null);
    this.uploadError.set(null);
  }

  async refreshSessions() {
    this.sessions.set(await this.api.sessions());
  }

  async refreshNotes() {
    this.notes.set(await this.api.notes());
  }

  async refreshAgents() {
    this.agents.set(await this.api.agents());
  }

  /** Create (no id) or update an agent. */
  async saveAgent(agent: AgentInput, id?: string) {
    const saved = id ? await this.api.updateAgent(id, agent) : await this.api.createAgent(agent);
    this.agents.update((l) => (id ? l.map((a) => (a.id === id ? saved : a)) : [...l, saved]));
    return saved;
  }

  async deleteAgent(id: string) {
    await this.api.deleteAgent(id);
    this.agents.update((l) => l.filter((a) => a.id !== id));
    if (this.agentId() === id && !this.currentId()) this.agentId.set(null);
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
    this.documents.update((l) => l.filter((d) => d.id !== id));
  }

  /**
   * Route guard: the Users page (/admin) is for admins. Signed out, it stays allowed so /admin
   * can show the admin sign-in.
   */
  canView(view: ActiveView) {
    return view !== 'users' || !this.auth.user() || this.auth.isAdmin();
  }

  /** Navigate; a page the guard refuses opens the chat instead. */
  setActiveView(view: ActiveView) {
    this.activeView.set(this.canView(view) ? view : 'chat');
  }

  /** Start a new chat, optionally running as one of the user's agents. */
  newChat(agentId: string | null = null) {
    this.activeView.set('chat');
    if (this.running()) return;
    this.currentId.set(null);
    this.agentId.set(agentId);
    this.messages.set([]);
  }

  async open(id: string) {
    this.activeView.set('chat');
    if (this.running() || id === this.currentId()) return;
    const session = await this.api.session(id);
    this.currentId.set(id);
    this.agentId.set(session.agent_id);
    this.messages.set(session.messages);
  }

  async deleteSession(id: string) {
    await this.api.deleteSession(id);
    if (id === this.currentId()) this.newChat();
    this.sessions.update((l) => l.filter((s) => s.id !== id));
  }

  async deleteNote(id: number) {
    await this.api.deleteNote(id);
    this.notes.update((l) => l.filter((n) => n.id !== id));
  }

  stop() {
    this.abort?.abort();
  }

  async send(text: string, attachments: OutgoingAttachment[] = []) {
    text = text.trim();
    if ((!text && !attachments.length) || this.running()) return;

    this.error.set(null);
    this.running.set(true);
    this.abort = new AbortController();
    const assistant: AssistantMessage = { role: 'assistant', parts: [], running: true };
    const user = { role: 'user' as const, text, attachments: attachments.map(toDisplay) };
    this.messages.update((m) => [...m, user, assistant]);

    // Tokens arrive far faster than the screen refreshes; apply them once per frame so
    // each message re-renders (and re-parses its Markdown) at most ~60 times a second.
    let queue: AgentEvent[] = [];
    let frame = 0;
    let touchedNotes = false;
    const flush = () => {
      frame = 0;
      const events = queue;
      queue = [];
      if (events.length) this.patchLastAssistant((msg) => events.reduce(reduceEvent, msg));
    };
    const onEvent = (ev: AgentEvent) => {
      if (ev.event === 'session') return this.currentId.set(ev.data.id);
      if (ev.event === 'tool_start' && NOTE_TOOLS.has(ev.data.name)) touchedNotes = true;
      queue.push(ev);
      frame ||= requestAnimationFrame(flush);
    };

    try {
      const body = {
        message: text,
        attachments,
        session_id: this.currentId(),
        agent_id: this.agentId(),
      };
      await this.api.chat(body, onEvent, this.abort.signal);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return this.auth.expire();
      const aborted = e instanceof DOMException && e.name === 'AbortError';
      queue.push(
        aborted
          ? { event: 'notice', data: { message: 'Stopped.' } }
          : { event: 'error', data: { message: (e as Error).message } },
      );
    } finally {
      cancelAnimationFrame(frame);
      flush();
      this.patchLastAssistant((msg) => ({ ...msg, running: false }));
      this.running.set(false);
      this.abort = null;
      // The run may have created, renamed, or (if its first message failed) deleted the session.
      this.refreshSessions().then(() => {
        if (!this.sessions().some((s) => s.id === this.currentId())) this.currentId.set(null);
      });
      if (touchedNotes) this.refreshNotes();
    }
  }

  private patchLastAssistant(fn: (msg: AssistantMessage) => AssistantMessage) {
    const last = this.messages().at(-1);
    if (last?.role !== 'assistant') return; // cleared by reset() while a run was in flight
    this.messages.update((m) => [...m.slice(0, -1), fn(last)]);
  }
}
