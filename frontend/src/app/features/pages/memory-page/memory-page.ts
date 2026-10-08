import { SlicePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatStore } from '../../../core/services/chat-store';

@Component({
  selector: 'app-memory-page',
  imports: [LucideDynamicIcon, SlicePipe],
  templateUrl: './memory-page.html',
  styleUrl: './memory-page.css',
})
export class MemoryPage {
  protected readonly store = inject(ChatStore);
  protected readonly searchQuery = signal('');
  protected readonly selectedTag = signal<string | null>(null);

  protected readonly allTags = computed(() => {
    const tags = new Set<string>();
    for (const note of this.store.notes()) {
      for (const t of note.tags) {
        tags.add(t);
      }
    }
    return Array.from(tags).sort();
  });

  protected readonly filteredNotes = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const tag = this.selectedTag();

    return this.store.notes().filter((n) => {
      const matchSearch =
        !q ||
        n.title.toLowerCase().includes(q) ||
        n.content.toLowerCase().includes(q) ||
        n.tags.some((t) => t.toLowerCase().includes(q));

      const matchTag = !tag || n.tags.includes(tag);

      return matchSearch && matchTag;
    });
  });

  protected selectTag(tag: string | null) {
    this.selectedTag.set(tag === this.selectedTag() ? null : tag);
  }

  protected backToChat() {
    this.store.setActiveView('chat');
  }
}
