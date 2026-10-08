import { Component, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ToolInfo } from '../../../core/models/chat.models';
import { ChatStore } from '../../../core/services/chat-store';

@Component({
  selector: 'app-tools-page',
  imports: [LucideDynamicIcon],
  templateUrl: './tools-page.html',
  styleUrl: './tools-page.css',
})
export class ToolsPage {
  protected readonly store = inject(ChatStore);
  protected readonly searchQuery = signal('');
  protected readonly filterType = signal<'all' | 'hosted' | 'local'>('all');

  protected readonly filteredTools = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const filter = this.filterType();

    return this.store.tools().filter((t) => {
      const matchSearch =
        !q ||
        t.name.toLowerCase().includes(q) ||
        t.label.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q);

      const matchFilter =
        filter === 'all' ||
        (filter === 'hosted' && t.server) ||
        (filter === 'local' && !t.server);

      return matchSearch && matchFilter;
    });
  });

  protected readonly hostedCount = computed(() => {
    return this.store.tools().filter((t) => t.server).length;
  });

  protected readonly localCount = computed(() => {
    return this.store.tools().filter((t) => !t.server).length;
  });

  protected getToolIcon(name: string): string {
    if (name.includes('calc') || name.includes('math')) return 'calculator';
    if (name.includes('web') || name.includes('search') || name.includes('fetch')) return 'globe';
    if (name.includes('file') || name.includes('read') || name.includes('write')) return 'code';
    if (name.includes('note') || name.includes('memory')) return 'brain';
    return 'wrench';
  }

  protected tryTool(tool: ToolInfo) {
    this.store.setActiveView('chat');
  }

  protected backToChat() {
    this.store.setActiveView('chat');
  }
}
