import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe } from '@angular/common';
import { ModelApi, ModelInfo } from '../../core/model-api';

@Component({
  selector: 'app-write',
  imports: [FormsModule, DecimalPipe],
  templateUrl: './write.html',
  styleUrl: './write.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Write {
  private readonly api = inject(ModelApi);

  protected readonly info = signal<ModelInfo | null>(null);
  protected readonly error = signal('');
  protected readonly notice = signal('');
  protected readonly prompt = signal('ROMEO:\n');
  protected readonly output = signal('');
  protected readonly running = signal(false);
  protected readonly maxTokens = signal(300);
  protected readonly temperature = signal(0.8);
  protected readonly topK = signal<number | null>(null);

  private abort: AbortController | null = null;

  constructor() {
    this.refresh(false);
  }

  protected async refresh(reload: boolean): Promise<void> {
    this.error.set('');
    try {
      this.info.set(reload ? await this.api.reload() : await this.api.info());
    } catch (e) {
      this.error.set((e as Error).message);
    }
  }

  protected async generate(): Promise<void> {
    this.abort = new AbortController();
    this.running.set(true);
    this.error.set('');
    this.notice.set('');
    this.output.set('');
    try {
      const events = this.api.generate(
        {
          prompt: this.prompt(),
          max_new_tokens: this.maxTokens(),
          temperature: this.temperature(),
          top_k: this.topK() || null,
        },
        this.abort.signal,
      );
      for await (const event of events) {
        if ('text' in event) this.output.update((o) => o + event.text);
        else if ('notice' in event) this.notice.set(event.notice);
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') this.error.set((e as Error).message);
    } finally {
      this.running.set(false);
      this.abort = null;
    }
  }

  protected stop(): void {
    this.abort?.abort();
  }
}
