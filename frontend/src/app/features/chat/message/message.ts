import { JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { ChatMessage, ToolPart } from '../../../core/models/chat.models';
import { MarkdownPipe } from '../../../shared/pipes/markdown.pipe';

const TOOL_LABELS: Record<string, string> = {
  web_search: 'Web search',
  web_fetch: 'Fetch page',
  calculator: 'Calculator',
  get_current_time: 'Clock',
  save_note: 'Save to memory',
  search_notes: 'Search memory',
  delete_note: 'Delete memory',
  list_files: 'List files',
  read_file: 'Read file',
  write_file: 'Write file',
  search_knowledge_base: 'Search documents',
  list_documents: 'List documents',
};

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

  protected label(name: string) {
    return TOOL_LABELS[name] ?? name;
  }

  protected statusIcon(part: ToolPart, running: boolean) {
    if (part.is_error) return '✕';
    if (part.output !== null) return '✓';
    return running ? '◌' : '–';
  }

  protected preview(part: ToolPart) {
    const input = part.input as Record<string, unknown> | null;
    if (!input) return '';
    const first = input['query'] ?? input['url'] ?? input['expression'] ?? input['path']
      ?? input['title'] ?? input['timezone'] ?? Object.values(input)[0];
    const text = typeof first === 'string' ? first : JSON.stringify(first ?? '');
    return text.length > 70 ? text.slice(0, 70) + '…' : text;
  }
}
