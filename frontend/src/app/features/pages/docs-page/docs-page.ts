import { SlicePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatStore } from '../../../core/services/chat-store';

@Component({
  selector: 'app-docs-page',
  imports: [LucideDynamicIcon, SlicePipe],
  templateUrl: './docs-page.html',
  styleUrl: './docs-page.css',
})
export class DocsPage {
  protected readonly store = inject(ChatStore);
  protected readonly searchQuery = signal('');
  protected readonly dragging = signal(false);

  protected readonly accept = computed(() => this.store.supportedTypes().join(','));

  protected readonly filteredDocuments = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    if (!q) return this.store.documents();
    return this.store.documents().filter((d) => d.name.toLowerCase().includes(q));
  });

  protected readonly totalChunks = computed(() => {
    return this.store.documents().reduce((acc, d) => acc + d.chunks, 0);
  });

  protected readonly totalSize = computed(() => {
    const bytes = this.store.documents().reduce((acc, d) => acc + d.size, 0);
    return this.formatSize(bytes);
  });

  protected formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

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

  protected backToChat() {
    this.store.setActiveView('chat');
  }
}
