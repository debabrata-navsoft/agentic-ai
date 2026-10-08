import { Component, ElementRef, HostListener, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { SessionSummary } from '../../core/models/chat.models';
import { AuthStore } from '../../core/services/auth-store';
import { ChatStore } from '../../core/services/chat-store';
import { SettingsStore } from '../../core/services/settings-store';
import { SettingsModal } from '../modals/settings-modal/settings-modal';
import { UpgradeModal } from '../modals/upgrade-modal/upgrade-modal';

type Tab = 'chat' | 'agents' | 'docs' | 'memory' | 'tools';
interface TabDef {
  id: Tab;
  label: string;
  icon: string;
  count?: () => number;
}

const DAY = 24 * 60 * 60 * 1000;

/** Left panel: navigation, conversations history, and user profile account menu. */
@Component({
  selector: 'app-sidebar',
  imports: [LucideDynamicIcon, SettingsModal, UpgradeModal],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
})
export class Sidebar {
  protected readonly store = inject(ChatStore);
  protected readonly auth = inject(AuthStore);
  protected readonly settings = inject(SettingsStore);
  private readonly hostRef = inject(ElementRef);

  protected readonly menuOpen = signal(false);
  protected readonly settingsOpen = signal(false);
  protected readonly upgradeOpen = signal(false);
  protected readonly tabs = computed<TabDef[]>(() => [
    { id: 'chat', label: 'Chats', icon: 'message-square-text' },
    { id: 'agents', label: 'AI Agents', icon: 'bot', count: () => 5 },
    {
      id: 'docs',
      label: 'Docs',
      icon: 'file-text',
      count: () => this.store.documents().length,
    },
    { id: 'memory', label: 'Memory', icon: 'brain', count: () => this.store.notes().length },
    { id: 'tools', label: 'Tools', icon: 'wrench', count: () => this.store.tools().length },
  ]);

  protected onNavClick(id: Tab) {
    this.store.setActiveView(id);
  }
  protected readonly initial = computed(
    () => this.auth.user()?.name.trim().charAt(0).toUpperCase() || '?',
  );

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

  protected toggleMenu(ev: MouseEvent) {
    ev.stopPropagation();
    this.menuOpen.update((v) => !v);
  }

  protected openSettings() {
    this.menuOpen.set(false);
    this.settingsOpen.set(true);
  }

  protected openUpgrade() {
    this.menuOpen.set(false);
    this.upgradeOpen.set(true);
  }

  @HostListener('document:click', ['$event'])
  protected onDocumentClick(ev: MouseEvent) {
    if (!this.menuOpen()) return;
    const target = ev.target as HTMLElement;
    const accountEl = this.hostRef.nativeElement.querySelector('.account-wrapper');
    if (accountEl && !accountEl.contains(target)) {
      this.menuOpen.set(false);
    }
  }
}

