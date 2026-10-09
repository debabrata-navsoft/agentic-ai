import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe } from '@angular/common';
import { DocInfo, ModelApi, SearchResult } from '../../core/model-api';
import { HighlightText } from '../../shared/highlight-text';

interface Turn {
  question: string;
  result?: SearchResult;
  error?: string;
}

@Component({
  selector: 'app-ask',
  imports: [FormsModule, DecimalPipe, HighlightText],
  templateUrl: './ask.html',
  styleUrl: './ask.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Ask {
  private readonly api = inject(ModelApi);
  private readonly thread = viewChild<ElementRef<HTMLElement>>('thread');

  protected readonly turns = signal<Turn[]>([]);
  protected readonly query = signal('');
  protected readonly busy = signal(false);
  protected readonly docs = signal<DocInfo[]>([]);
  protected readonly docsError = signal('');
  protected readonly uploading = signal(false);

  constructor() {
    this.loadDocs();
  }

  protected async ask(): Promise<void> {
    const question = this.query().trim();
    if (!question || this.busy()) return;
    this.query.set('');
    this.busy.set(true);
    this.turns.update((t) => [...t, { question }]);
    this.scrollDown();

    let turn: Turn;
    try {
      turn = { question, result: await this.api.search(question) };
    } catch (e) {
      turn = { question, error: (e as Error).message };
    }
    this.turns.update((t) => [...t.slice(0, -1), turn]);
    this.busy.set(false);
    this.scrollDown();
  }

  protected onKey(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.ask();
    }
  }

  protected async upload(input: HTMLInputElement): Promise<void> {
    const files = Array.from(input.files ?? []);
    input.value = '';
    if (!files.length) return;
    this.uploading.set(true);
    this.docsError.set('');
    try {
      for (const file of files) await this.api.upload(file);
    } catch (e) {
      this.docsError.set((e as Error).message);
    }
    this.uploading.set(false);
    await this.loadDocs();
  }

  protected async remove(doc: DocInfo): Promise<void> {
    if (!confirm(`Delete ${doc.name}?`)) return;
    try {
      await this.api.deleteDoc(doc.name);
    } catch (e) {
      this.docsError.set((e as Error).message);
    }
    await this.loadDocs();
  }

  private async loadDocs(): Promise<void> {
    try {
      this.docs.set(await this.api.docs());
    } catch (e) {
      this.docsError.set((e as Error).message);
    }
  }

  private scrollDown(): void {
    requestAnimationFrame(() => {
      const el = this.thread()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}
