import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import {
  AgentEvent,
  AgentInput,
  AgentProfile,
  ChatRequest,
  DocumentList,
  Health,
  KnowledgeDocument,
  Note,
  SessionDetail,
  SessionSummary,
  ToolInfo,
  User,
} from '../models/chat.models';

const API = '/api';

/** A failed `fetch()` request, carrying the HTTP status like HttpErrorResponse does. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

@Injectable({ providedIn: 'root' })
export class AgentApi {
  private readonly http = inject(HttpClient);

  private get<T>(path: string) {
    return firstValueFrom(this.http.get<T>(API + path));
  }

  private del(path: string) {
    return firstValueFrom(this.http.delete<void>(API + path));
  }

  private post<T>(path: string, body: unknown) {
    return firstValueFrom(this.http.post<T>(API + path, body));
  }

  // The login is an httpOnly cookie on /api, so these calls never handle a token themselves.
  me = () => this.get<User>('/auth/me');
  login = (email: string, password: string, admin = false) =>
    this.post<User>(admin ? '/auth/admin/login' : '/auth/login', { email, password });
  signup = (name: string, email: string, password: string) =>
    this.post<User>('/auth/signup', { name, email, password });
  logout = () => this.post<void>('/auth/logout', {});
  changePassword = (current_password: string, new_password: string) =>
    this.post<void>('/auth/password', { current_password, new_password });
  forgotPassword = (email: string) => this.post<void>('/auth/forgot', { email });
  resetPassword = (token: string, new_password: string) =>
    this.post<void>('/auth/reset', { token, new_password });
  users = () => this.get<User[]>('/admin/users');
  updateUser = (id: string, patch: Partial<Pick<User, 'role' | 'disabled'>>) =>
    firstValueFrom(this.http.patch<User>(`${API}/admin/users/${id}`, patch));

  health = () => this.get<Health>('/health');
  tools = () => this.get<ToolInfo[]>('/tools');
  sessions = () => this.get<SessionSummary[]>('/sessions');
  session = (id: string) => this.get<SessionDetail>(`/sessions/${id}`);
  deleteSession = (id: string) => this.del(`/sessions/${id}`);
  notes = () => this.get<Note[]>('/notes');
  deleteNote = (id: number) => this.del(`/notes/${id}`);
  agents = () => this.get<AgentProfile[]>('/agents');
  createAgent = (agent: AgentInput) => this.post<AgentProfile>('/agents', agent);
  updateAgent = (id: string, agent: AgentInput) =>
    firstValueFrom(this.http.put<AgentProfile>(`${API}/agents/${id}`, agent));
  deleteAgent = (id: string) => this.del(`/agents/${id}`);
  documents = () => this.get<DocumentList>('/documents');
  deleteDocument = (id: string) => this.del(`/documents/${id}`);

  uploadDocument(file: File) {
    const form = new FormData();
    form.append('file', file);
    return firstValueFrom(this.http.post<KnowledgeDocument>(`${API}/documents`, form));
  }

  async chat(
    body: ChatRequest,
    onEvent: (ev: AgentEvent) => void,
    signal: AbortSignal,
  ): Promise<void> {
    const res = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) {
      const detail = (await res.json().catch(() => null))?.detail;
      // FastAPI's own validation errors are a list; ours are a string.
      const msg = typeof detail === 'string' ? detail : (detail?.[0]?.msg ?? null);
      throw new ApiError(msg ?? `Request failed (${res.status})`, res.status);
    }

    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value.replace(/\r\n/g, '\n');
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const ev = parseSseFrame(buffer.slice(0, sep));
        buffer = buffer.slice(sep + 2);
        if (ev) onEvent(ev);
      }
    }
  }
}

export function parseSseFrame(frame: string): AgentEvent | null {
  let event = 'message';
  const data: string[] = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue; // keep-alive comment
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
  }
  if (!data.length) return null;
  return { event, data: JSON.parse(data.join('\n')) };
}
