import { JsonPipe } from '@angular/common';
import { Component, inject, input } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatMessage, TextPart, ToolPart } from '../../../core/models/chat.models';
import { ChatStore } from '../../../core/services/chat-store';
import { SpeechService } from '../../../core/services/speech';
import { MarkdownPipe } from '../../../shared/pipes/markdown.pipe';

/** One chat message: a user bubble, or an assistant turn with text, reasoning, and tool calls. */
@Component({
  selector: 'app-message',
  imports: [MarkdownPipe, JsonPipe, LucideDynamicIcon],
  templateUrl: './message.html',
  styleUrl: './message.css',
})
export class Message {
  readonly message = input.required<ChatMessage>();
  private readonly store = inject(ChatStore);
  protected readonly speech = inject(SpeechService);

  protected label(name: string) {
    return this.store.toolLabels().get(name) ?? name;
  }

  protected statusIcon(part: ToolPart, running: boolean) {
    if (part.is_error) return '✕';
    if (part.output !== null) return '✓';
    return running ? '◌' : '–';
  }

  /** Read the reply's text aloud (or stop), without Markdown symbols or code blocks. */
  protected readAloud() {
    const msg = this.message();
    if (msg.role !== 'assistant') return;
    const text = msg.parts
      .filter((p): p is TextPart => p.type === 'text')
      .map((p) => p.text)
      .join('\n')
      .replace(/```[\s\S]*?```/g, ' (code omitted) ')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // [link](url) → link
      .replace(/[#*_`>|~-]+/g, ' ');
    this.speech.toggle(msg, text);
  }

  /** One-line summary of a tool call: its first argument (each tool puts its key input first). */
  protected preview(part: ToolPart) {
    const first = Object.values((part.input ?? {}) as object)[0] ?? '';
    const text = typeof first === 'string' ? first : JSON.stringify(first);
    return text.length > 70 ? text.slice(0, 70) + '…' : text;
  }
}
