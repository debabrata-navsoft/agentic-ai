import { JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';

import { ChatMessage, ToolPart } from '../../../core/models/chat.models';
import { ChatStore } from '../../../core/services/chat-store';
import { MarkdownPipe } from '../../../shared/pipes/markdown.pipe';

/** One chat message: a user bubble, or an assistant turn with text, reasoning, and tool calls. */
@Component({
  selector: 'app-message',
  imports: [MarkdownPipe, JsonPipe],
  templateUrl: './message.html',
  styleUrl: './message.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Message {
  readonly message = input.required<ChatMessage>();
  private readonly store = inject(ChatStore);

  protected label(name: string) {
    return this.store.toolLabels().get(name) ?? name;
  }

  protected statusIcon(part: ToolPart, running: boolean) {
    if (part.is_error) return '✕';
    if (part.output !== null) return '✓';
    return running ? '◌' : '–';
  }

  /** One-line summary of a tool call: its first argument (each tool puts its key input first). */
  protected preview(part: ToolPart) {
    const first = Object.values((part.input ?? {}) as object)[0] ?? '';
    const text = typeof first === 'string' ? first : JSON.stringify(first);
    return text.length > 70 ? text.slice(0, 70) + '…' : text;
  }
}
