import { Injectable } from '@angular/core';

export interface ModelInfo {
  loaded: boolean;
  checkpoint: string;
  params?: number;
  config?: {
    block_size: number;
    n_layer: number;
    n_head: number;
    n_embd: number;
    vocab_size: number;
  };
  vocab?: string;
  step?: number;
  val_loss?: number;
  data?: string;
}

export interface GenerateOptions {
  prompt: string;
  max_new_tokens: number;
  temperature: number;
  top_k: number | null;
}

export type GenerateEvent = { text: string } | { notice: string } | { done: true };

export interface SearchResult {
  query: string;
  terms: string[];
  answer: string;
  results: { doc: string; passage: number; text: string; score: number }[];
  searched_passages: number;
}

export interface DocInfo {
  name: string;
  size: number;
  passages: number;
}

@Injectable({ providedIn: 'root' })
export class ModelApi {
  async info(): Promise<ModelInfo> {
    return this.json(await fetch('/api/model'));
  }

  async search(query: string, k = 5): Promise<SearchResult> {
    return this.json(
      await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, k }),
      }),
    );
  }

  async docs(): Promise<DocInfo[]> {
    return this.json(await fetch('/api/docs'));
  }

  async upload(file: File): Promise<DocInfo> {
    const body = new FormData();
    body.append('file', file);
    return this.json(await fetch('/api/docs', { method: 'POST', body }));
  }

  async deleteDoc(name: string): Promise<void> {
    const res = await fetch(`/api/docs/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await errorMessage(res));
  }

  async reload(): Promise<ModelInfo> {
    return this.json(await fetch('/api/model/reload', { method: 'POST' }));
  }

  /** POST /api/generate and yield its SSE events (EventSource only supports GET). */
  async *generate(opts: GenerateOptions, signal: AbortSignal): AsyncGenerator<GenerateEvent> {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opts),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(await errorMessage(res));

    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += value.replace(/\r\n/g, '\n');
      let end: number;
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        if (frame.startsWith('data: ')) yield JSON.parse(frame.slice(6));
      }
    }
  }

  private async json<T>(res: Response): Promise<T> {
    if (!res.ok) throw new Error(await errorMessage(res));
    return res.json();
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}: is the backend running on :8000?`;
  }
}
