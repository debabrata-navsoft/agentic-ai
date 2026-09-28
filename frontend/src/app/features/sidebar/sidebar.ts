import { Component, computed, inject, signal } from '@angular/core';

import { ChatStore } from '../../core/services/chat-store';

type Tab = 'chats' | 'knowledge' | 'memory' | 'tools';

/** Left panel: conversations, RAG knowledge base, long-term memory, and tool catalog. */
@Component({
  selector: 'app-sidebar',
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
})
export class Sidebar {
  protected readonly store = inject(ChatStore);
  protected readonly tab = signal<Tab>('chats');
  protected readonly dragging = signal(false);
  protected readonly accept = computed(() => this.store.supportedTypes().join(','));

  protected onFilesPicked(ev: Event) {
    const input = ev.target as HTMLInputElement;
    this.store.upload(Array.from(input.files ?? []));
    input.value = '';
  }

  protected onDrop(ev: DragEvent) {
    ev.preventDefault();
    this.dragging.set(false);
    this.store.upload(Array.from(ev.dataTransfer?.files ?? []));
  }

  protected onDragOver(ev: DragEvent) {
    ev.preventDefault();
    this.dragging.set(true);
  }

  protected formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }
}
