import { Component, ElementRef, effect, inject, signal, viewChild } from '@angular/core';

import { ChatStore } from '../../../core/services/chat-store';
import { Message } from '../message/message';

/** The main conversation area: header, message thread, welcome screen, and composer. */
@Component({
  selector: 'app-chat-panel',
  imports: [Message],
  templateUrl: './chat-panel.html',
  styleUrl: './chat-panel.css',
})
export class ChatPanel {
  protected readonly store = inject(ChatStore);
  protected readonly draft = signal('');
  protected readonly suggestions = [
    'Research the latest stable Python release and summarize what changed, with sources.',
    'Remember that I prefer concise answers and I work mostly in Python and Angular.',
    'What is the compound interest on ₹2,50,000 at 7.5% for 12 years? Show the math.',
    'Summarize the documents in my knowledge base and list the key facts from each.',
  ];

  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');

  constructor() {
    // Keep the newest output in view while the agent streams.
    effect(() => {
      this.store.messages();
      const el = this.scroller()?.nativeElement;
      if (!el) return;
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
      if (nearBottom) queueMicrotask(() => (el.scrollTop = el.scrollHeight));
    });
  }

  protected submit(text = this.draft()) {
    if (!text.trim() || this.store.running()) return;
    this.draft.set('');
    this.store.send(text);
    queueMicrotask(() => {
      const el = this.scroller()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }

  protected onKeydown(ev: KeyboardEvent) {
    if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault();
      this.submit();
    }
  }

  protected onInput(ev: Event) {
    const el = ev.target as HTMLTextAreaElement;
    this.draft.set(el.value);
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 220) + 'px';
  }
}
