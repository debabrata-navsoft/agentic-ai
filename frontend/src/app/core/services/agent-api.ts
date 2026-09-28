import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import {
  AgentEvent, DocumentList, Health, KnowledgeDocument, Note, SessionDetail, SessionSummary, ToolInfo,
} from '../models/chat.models';

const API = '/api';

@Injectable({ providedIn: 'root' })
export class AgentApi {
  private readonly http = inject(HttpClient);

  private get<T>(path: string) {
    return firstValueFrom(this.http.get<T>(API + path));
  }

  private del(path: string) {
    return firstValueFrom(this.http.delete<void>(API + path));
  }

  health = () => this.get<Health>('/health');
  tools = () => this.get<ToolInfo[]>('/tools');
  sessions = () => this.get<SessionSummary[]>('/sessions');
  session = (id: string) => this.get<SessionDetail>(`/sessions/${id}`);
  deleteSession = (id: string) => this.del(`/sessions/${id}`);
  notes = () => this.get<Note[]>('/notes');
  deleteNote = (id: number) => this.del(`/notes/${id}`);
  documents = () => this.get<DocumentList>('/documents');
  deleteDocument = (id: string) => this.del(`/documents/${id}`);

  uploadDocument(file: File) {
    const form = new FormData();
    form.append('file', file);
    return firstValueFrom(this.http.post<KnowledgeDocument>(`${API}/documents`, form));
  }

  /**
   * POST a message and stream the agent's events. EventSource only supports GET,
   * so this reads the SSE body from fetch() and parses it by hand.
   */
  async chat(
    message: string,
    sessionId: string | null,
    onEvent: (ev: AgentEvent) => void,
    signal: AbortSignal,
  ): Promise<void> {
    const res = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    });
    if (!res.ok || !res.body) {
      const detail = await res.json().catch(() => null);
      throw new Error(detail?.detail ?? `Request failed (${res.status})`);
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
