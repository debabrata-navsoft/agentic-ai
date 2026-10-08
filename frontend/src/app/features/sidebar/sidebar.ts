import { Component, ElementRef, HostListener, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { SessionSummary } from '../../core/models/chat.models';
import { AuthStore } from '../../core/services/auth-store';
import { ActiveView, ChatStore } from '../../core/services/chat-store';
import { SettingsStore } from '../../core/services/settings-store';
import { SettingsModal } from '../modals/settings-modal/settings-modal';
import { UpgradeModal } from '../modals/upgrade-modal/upgrade-modal';

type Tab = ActiveView;
interface TabDef {
  id: Tab;
  label: string;
  icon: string;
  count?: () => number;
}

const DAY = 24 * 60 * 60 * 1000;

/** "Today", "Yesterday", "2 days ago", "3 days ago", then the date ("5 Oct", or "5 Oct 2025" in past years). */
function dayLabel(date: Date, startOfToday: number, thisYear: number): string {
  // Round so a DST shift between the two midnights doesn't skew the count.
  const days = Math.round((startOfToday - new Date(date).setHours(0, 0, 0, 0)) / DAY);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days <= 3) return `${days} days ago`;
  return date.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() === thisYear ? undefined : 'numeric',
  });
}

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
    {
      id: 'agents',
      label: 'AI Agents',
      icon: 'bot',
      count: () => this.store.agents().length,
    },
    {
      id: 'docs',
      label: 'Docs',
      icon: 'file-text',
      count: () => this.store.documents().length,
    },
    { id: 'memory', label: 'Memory', icon: 'brain', count: () => this.store.notes().length },
    { id: 'tools', label: 'Tools', icon: 'wrench', count: () => this.store.tools().length },
    ...(this.auth.isAdmin() ? [{ id: 'users' as const, label: 'Users', icon: 'users' }] : []),
  ]);

  protected onNavClick(id: Tab) {
    this.store.setActiveView(id);
  }
  protected readonly initial = computed(
    () => this.auth.user()?.name.trim().charAt(0).toUpperCase() || '?',
  );

  /** Chats bucketed by the calendar day of last activity (sessions arrive newest first). */
  protected readonly chatGroups = computed(() => {
    const now = new Date();
    const startOfToday = new Date(now).setHours(0, 0, 0, 0);
    const groups = new Map<string, SessionSummary[]>();
    for (const s of this.store.sessions()) {
      const label = dayLabel(new Date(s.updated_at), startOfToday, now.getFullYear());
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
