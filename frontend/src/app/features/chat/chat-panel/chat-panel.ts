import { Component, ElementRef, computed, effect, inject, signal, viewChild } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatStore } from '../../../core/services/chat-store';
import { Message } from '../message/message';

/** The main conversation area: top bar, message thread, welcome screen, and composer. */
@Component({
  selector: 'app-chat-panel',
  imports: [LucideDynamicIcon, Message],
  templateUrl: './chat-panel.html',
  styleUrl: './chat-panel.css',
})
export class ChatPanel {
  protected readonly store = inject(ChatStore);
  protected readonly draft = signal('');
  protected readonly showRuntime = signal(true);
  protected readonly suggestions = [
    {
      icon: 'globe',
      label: 'Web search & docs',
      text: 'Research the latest stable Python release and summarize what changed, with sources.',
    },
    {
      icon: 'brain',
      label: 'Memory retention',
      text: 'Remember that I prefer concise answers and I work mostly in Python and Angular.',
    },
    {
      icon: 'calculator',
      label: 'Symbolic math',
      text: 'What is the compound interest on ₹2,50,000 at 7.5% for 12 years? Show the math.',
    },
    {
      icon: 'file-search',
      label: 'Vector synthesis',
      text: 'Summarize the documents in my knowledge base and list the key facts from each.',
    },
  ];

  /** Rough draft size: ~4 characters per token for English text. */
  protected readonly draftTokens = computed(() => Math.ceil(this.draft().trim().length / 4));
  protected readonly accept = computed(() => this.store.supportedTypes().join(','));

  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');

  constructor() {
    // Keep the newest output in view while the agent streams.
    effect(() => {
      this.store.messages();
      const el = this.scroller()?.nativeElement;
      if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 160) this.scrollToBottom();
    });
  }

  private scrollToBottom() {
    queueMicrotask(() => {
      const el = this.scroller()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }

  protected submit(text = this.draft()) {
    if (!text.trim() || this.store.running()) return;
    this.draft.set('');
    this.store.send(text);
    this.scrollToBottom();
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

  /** The composer's "+" adds files to the knowledge base, same as the Docs tab. */
  protected onAttach(ev: Event) {
    const input = ev.target as HTMLInputElement;
    this.store.upload(Array.from(input.files ?? []));
    input.value = '';
  }
}
