import { Component, ElementRef, computed, effect, inject, signal, viewChild } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { OutgoingAttachment } from '../../../core/models/chat.models';
import { ChatStore } from '../../../core/services/chat-store';
import { IMAGE_TYPES, readAttachment, toDisplay } from '../../../core/utils/attachments';
import { Message } from '../message/message';

export interface PromptType {
  id: string;
  label: string;
  icon: string;
  placeholder: string;
  prefix?: string;
  sample: string;
  description: string;
}

const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // the Claude API's per-image limit
const MAX_ATTACHMENTS = 10; // matches the backend

/** The main conversation area: top bar, message thread, welcome screen, and composer with prompt types. */
@Component({
  selector: 'app-chat-panel',
  imports: [LucideDynamicIcon, Message],
  templateUrl: './chat-panel.html',
  styleUrl: './chat-panel.css',
})
export class ChatPanel {
  protected readonly store = inject(ChatStore);
  protected readonly draft = signal('');
  protected readonly attachments = signal<OutgoingAttachment[]>([]);
  protected readonly previews = computed(() => this.attachments().map(toDisplay));
  protected readonly attachError = signal<string | null>(null);
  /** Images, PDFs, and the text/code extensions the backend reads. */
  protected readonly accept = computed(() =>
    [...IMAGE_TYPES, ...this.store.supportedTypes()].join(','),
  );

  protected readonly promptTypes: PromptType[] = [
    {
      id: 'auto',
      label: 'Auto Agent',
      icon: 'sparkles',
      placeholder: 'Message Synora… (Auto-detects tools, web search, files & math)',
      sample: 'Plan and execute a complete solution for my task.',
      description: 'Autonomous multi-tool coordinator',
    },
    {
      id: 'web',
      label: 'Web Search',
      icon: 'globe',
      placeholder: 'Search the live web for verified facts, sources & news…',
      prefix: '[Web Search]: ',
      sample: 'Research the latest stable Python and Angular features with citations.',
      description: 'Real-time online search & page fetch',
    },
    {
      id: 'code',
      label: 'Code & Files',
      icon: 'code',
      placeholder: 'Create files, edit code or inspect your private workspace…',
      prefix: '[Workspace Code]: ',
      sample: 'Write a Python utility script to process JSON files and save it to my workspace.',
      description: 'Sandboxed file reads and writes',
    },
    {
      id: 'rag',
      label: 'Knowledge RAG',
      icon: 'file-search',
      placeholder: 'Ask questions grounded in your uploaded documents…',
      prefix: '[Knowledge Base RAG]: ',
      sample: 'Summarize the documents in my knowledge base and list the key points.',
      description: 'Chroma vector database search',
    },
    {
      id: 'memory',
      label: 'Save Memory',
      icon: 'brain',
      placeholder: 'Tell Synora what facts or preferences to remember long-term…',
      prefix: '[Remember]: ',
      sample: 'Remember that I prefer concise answers and clean modular code.',
      description: 'Cross-session long-term facts',
    },
    {
      id: 'math',
      label: 'Calculator',
      icon: 'calculator',
      placeholder: 'Exact arithmetic and mathematical calculations…',
      prefix: '[Calculate]: ',
      sample: 'What is the compound interest on ₹2,50,000 at 7.5% for 12 years? Show the steps.',
      description: 'Exact Python arithmetic',
    },
  ];

  protected readonly selectedPromptType = signal<string>('auto');

  protected readonly activePromptType = computed(() => {
    return this.promptTypes.find((p) => p.id === this.selectedPromptType()) ?? this.promptTypes[0];
  });

  protected readonly currentPlaceholder = computed(() => {
    return this.activePromptType().placeholder;
  });

  /** Rough draft size: ~4 characters per token for English text. */
  protected readonly draftTokens = computed(() => Math.ceil(this.draft().trim().length / 4));

  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');
  private readonly textarea = viewChild<ElementRef<HTMLTextAreaElement>>('textarea');

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

  protected selectPromptType(id: string) {
    this.selectedPromptType.set(id);
    this.textarea()?.nativeElement.focus();
  }

  protected useTypeSample(type: PromptType) {
    this.selectedPromptType.set(type.id);
    this.draft.set(type.sample);
    this.textarea()?.nativeElement.focus();
  }

  protected readonly canSend = computed(
    () => !!this.draft().trim() || this.attachments().length > 0,
  );

  protected submit() {
    if (!this.canSend() || this.store.running()) return;

    let messageToSend = this.draft().trim();
    const type = this.activePromptType();

    // If a specialized prompt type is active and user didn't write prefix, prepend it
    if (
      messageToSend &&
      type.prefix &&
      !messageToSend.startsWith('[') &&
      !messageToSend.includes(type.prefix)
    ) {
      messageToSend = `${type.prefix}${messageToSend}`;
    }

    this.store.send(messageToSend, this.attachments());
    this.draft.set('');
    this.attachments.set([]);
    this.attachError.set(null);
    this.scrollToBottom();

    // Reset textarea height
    const el = this.textarea()?.nativeElement;
    if (el) el.style.height = 'auto';
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

  protected onPick(ev: Event) {
    const input = ev.target as HTMLInputElement;
    this.addFiles(Array.from(input.files ?? []));
    input.value = '';
  }

  /** Pasting an image (e.g. a screenshot) attaches it. */
  protected onPaste(ev: ClipboardEvent) {
    const files = Array.from(ev.clipboardData?.files ?? []);
    if (!files.length) return;
    ev.preventDefault();
    this.addFiles(files);
  }

  protected onDrop(ev: DragEvent) {
    ev.preventDefault();
    this.addFiles(Array.from(ev.dataTransfer?.files ?? []));
  }

  protected removeAttachment(index: number) {
    this.attachments.update((l) => l.filter((_, i) => i !== index));
  }

  private async addFiles(files: File[]) {
    const tooBig = files.filter((f) => f.type.startsWith('image/') && f.size > MAX_IMAGE_BYTES);
    const ok = files.filter((f) => !tooBig.includes(f));
    const room = MAX_ATTACHMENTS - this.attachments().length;
    this.attachError.set(
      tooBig.length
        ? `${tooBig.map((f) => f.name).join(', ')}: images must be under 5 MB.`
        : ok.length > room
          ? `You can attach up to ${MAX_ATTACHMENTS} files per message.`
          : null,
    );
    // Read in parallel; the slice also covers files added while these were reading.
    const read = await Promise.all(ok.slice(0, room).map(readAttachment));
    this.attachments.update((l) => [...l, ...read].slice(0, MAX_ATTACHMENTS));
  }
}
