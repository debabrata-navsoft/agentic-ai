import { Component, HostListener, inject, input, output, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { AccentColor, AppTheme, FontSize, SettingsStore } from '../../../core/services/settings-store';
import { AuthStore } from '../../../core/services/auth-store';
import { ChatStore } from '../../../core/services/chat-store';

export type SettingsTab = 'appearance' | 'agent' | 'chat' | 'data' | 'account';

@Component({
  selector: 'app-settings-modal',
  imports: [LucideDynamicIcon],
  templateUrl: './settings-modal.html',
  styleUrl: './settings-modal.css',
})
export class SettingsModal {
  readonly isOpen = input<boolean>(false);
  readonly closed = output<void>();
  readonly openUpgrade = output<void>();

  protected readonly settings = inject(SettingsStore);
  protected readonly auth = inject(AuthStore);
  protected readonly chat = inject(ChatStore);

  protected readonly activeTab = signal<SettingsTab>('appearance');
  protected readonly cacheCleared = signal(false);

  protected readonly accents: { id: AccentColor; label: string; color: string }[] = [
    { id: 'violet', label: 'Violet', color: '#8b5cf6' },
    { id: 'blue', label: 'Blue', color: '#2563eb' },
    { id: 'emerald', label: 'Emerald', color: '#059669' },
    { id: 'amber', label: 'Amber', color: '#d97706' },
    { id: 'rose', label: 'Rose', color: '#e11d48' },
  ];

  protected readonly themes: { id: AppTheme; label: string; icon: string; desc: string }[] = [
    { id: 'dark', label: 'Dark', icon: 'moon', desc: 'High contrast dark theme' },
    { id: 'light', label: 'Light', icon: 'sun', desc: 'Crisp, bright daylight' },
    { id: 'system', label: 'System', icon: 'sliders', desc: 'Syncs with OS theme' },
  ];

  protected readonly promptModes = [
    { id: 'auto', label: 'Auto Agent', icon: 'sparkles' },
    { id: 'web', label: 'Web Search', icon: 'globe' },
    { id: 'code', label: 'Code & Files', icon: 'code' },
    { id: 'rag', label: 'Knowledge RAG', icon: 'file-search' },
    { id: 'memory', label: 'Save Memory', icon: 'brain' },
    { id: 'math', label: 'Calculator', icon: 'calculator' },
  ];

  @HostListener('window:keydown.escape')
  onEscape() {
    if (this.isOpen()) {
      this.close();
    }
  }

  close() {
    this.closed.emit();
  }

  onBackdropClick(ev: MouseEvent) {
    if ((ev.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.close();
    }
  }

  exportAll() {
    this.settings.exportData(this.chat.sessions(), this.chat.notes());
  }

  clearLocalCache() {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('synora_cached_session');
      this.cacheCleared.set(true);
      setTimeout(() => this.cacheCleared.set(false), 2500);
    }
  }

  requestUpgrade() {
    this.close();
    this.openUpgrade.emit();
  }
}
