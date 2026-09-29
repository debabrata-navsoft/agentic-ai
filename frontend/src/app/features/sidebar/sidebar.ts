import { Component, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { SessionSummary } from '../../core/models/chat.models';
import { AuthStore } from '../../core/services/auth-store';
import { ChatStore } from '../../core/services/chat-store';
import { UserAdmin } from '../admin/user-admin';

type Tab = 'chats' | 'knowledge' | 'memory' | 'tools' | 'users';
interface TabDef {
  id: Tab;
  label: string;
  icon: string;
  count?: () => number;
}

const DAY = 24 * 60 * 60 * 1000;

/** Left panel: conversations, RAG knowledge base, long-term memory, tool catalog, and (for admins) users. */
@Component({
  selector: 'app-sidebar',
  imports: [LucideDynamicIcon, UserAdmin],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
})
export class Sidebar {
  protected readonly store = inject(ChatStore);
  protected readonly auth = inject(AuthStore);
  protected readonly tab = signal<Tab>('chats');
  private readonly baseTabs: TabDef[] = [
    { id: 'chats', label: 'Chats', icon: 'message-square-text' },
    {
      id: 'knowledge',
      label: 'Docs',
      icon: 'file-text',
      count: () => this.store.documents().length,
    },
    { id: 'memory', label: 'Memory', icon: 'brain', count: () => this.store.notes().length },
    { id: 'tools', label: 'Tools', icon: 'wrench', count: () => this.store.tools().length },
  ];
  protected readonly tabs = computed<TabDef[]>(() =>
    this.auth.isAdmin()
      ? [...this.baseTabs, { id: 'users', label: 'Users', icon: 'users' }]
      : this.baseTabs,
  );
  protected readonly initial = computed(
    () => this.auth.user()?.name.trim().charAt(0).toUpperCase() || '?',
  );
  protected readonly dragging = signal(false);
  protected readonly accept = computed(() => this.store.supportedTypes().join(','));

  /** Chats bucketed by last activity (sessions arrive newest first). */
  protected readonly chatGroups = computed(() => {
    const startOfToday = new Date().setHours(0, 0, 0, 0);
    const buckets: [string, number][] = [
      ['Today', startOfToday],
      ['Yesterday', startOfToday - DAY],
      ['Previous 7 days', startOfToday - 7 * DAY],
      ['Older', -Infinity],
    ];
    const groups = new Map<string, SessionSummary[]>();
    for (const s of this.store.sessions()) {
      const t = Date.parse(s.updated_at);
      const [label] = buckets.find(([, since]) => t >= since)!;
      groups.set(label, [...(groups.get(label) ?? []), s]);
    }
    return [...groups].map(([label, sessions]) => ({ label, sessions }));
  });

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
