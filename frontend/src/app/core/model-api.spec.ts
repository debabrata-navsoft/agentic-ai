import { TestBed } from '@angular/core/testing';
import { GenerateEvent, ModelApi } from './model-api';

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      chunks.forEach((s) => c.enqueue(enc.encode(s)));
      c.close();
    },
  });
}

describe('ModelApi.generate', () => {
  afterEach(() => vi.restoreAllMocks());

  it('parses SSE frames split across chunks and \\r\\n line endings', async () => {
    const body = streamOf([
      'data: {"te',
      'xt": "a"}\r\n\r\ndata: {"text": "b"}\n',
      '\ndata: {"done": true}\n\n',
    ]);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(body, { status: 200 }));

    const api = TestBed.inject(ModelApi);
    const events: GenerateEvent[] = [];
    const opts = { prompt: 'x', max_new_tokens: 2, temperature: 1, top_k: null };
    for await (const e of api.generate(opts, new AbortController().signal)) events.push(e);

    expect(events).toEqual([{ text: 'a' }, { text: 'b' }, { done: true }]);
  });

  it('surfaces the backend error detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      Response.json({ detail: 'No trained model yet.' }, { status: 503 }),
    );
    const api = TestBed.inject(ModelApi);
    const opts = { prompt: 'x', max_new_tokens: 2, temperature: 1, top_k: null };
    await expect(api.generate(opts, new AbortController().signal).next()).rejects.toThrow(
      'No trained model yet.',
    );
  });
});
