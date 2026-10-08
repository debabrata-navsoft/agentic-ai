import { Injectable, effect, inject, signal } from '@angular/core';

export type AppTheme = 'dark' | 'light' | 'system';
const ACCENTS = ['mono', 'blue', 'emerald', 'amber', 'rose'] as const;
export type AccentColor = (typeof ACCENTS)[number];
export type FontSize = 'compact' | 'normal' | 'large';
export type PlanTier = 'free' | 'pro';

export interface UserPreferences {
  theme: AppTheme;
  accent: AccentColor;
  fontSize: FontSize;
  defaultPromptMode: string;
  model: string;
  reasoningEffort: 'low' | 'medium' | 'high';
  sendOnEnter: boolean;
  soundEffects: boolean;
  showLatency: boolean;
  plan: PlanTier;
}

const STORAGE_KEY = 'synora_user_settings';

const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'dark',
  accent: 'mono',
  fontSize: 'normal',
  defaultPromptMode: 'auto',
  model: 'claude-3-5-sonnet',
  reasoningEffort: 'high',
  sendOnEnter: true,
  soundEffects: true,
  showLatency: true,
  plan: 'free',
};

@Injectable({ providedIn: 'root' })
export class SettingsStore {
  readonly theme = signal<AppTheme>('dark');
  readonly accent = signal<AccentColor>('mono');
  readonly fontSize = signal<FontSize>('normal');
  readonly defaultPromptMode = signal<string>('auto');
  readonly model = signal<string>('claude-3-5-sonnet');
  readonly reasoningEffort = signal<'low' | 'medium' | 'high'>('high');
  readonly sendOnEnter = signal<boolean>(true);
  readonly soundEffects = signal<boolean>(true);
  readonly showLatency = signal<boolean>(true);
  readonly plan = signal<PlanTier>('free');

  constructor() {
    this.loadFromStorage();

    // Effect to apply attributes to HTML element and persist to storage
    effect(() => {
      const themeVal = this.theme();
      const accentVal = this.accent();
      const fontVal = this.fontSize();

      if (typeof document !== 'undefined') {
        const root = document.documentElement;

        // Apply theme
        if (themeVal === 'system') {
          const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          root.setAttribute('data-theme', isDark ? 'dark' : 'light');
        } else {
          root.setAttribute('data-theme', themeVal);
        }

        // Apply accent
        root.setAttribute('data-accent', accentVal);

        // Apply font scaling
        root.setAttribute('data-font', fontVal);
      }

      this.persist();
    });
  }

  private loadFromStorage() {
    if (typeof localStorage === 'undefined') return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed: Partial<UserPreferences> = JSON.parse(raw);
      if (parsed.theme) this.theme.set(parsed.theme);
      // A saved accent that no longer exists (e.g. the removed violet) falls back to Mono.
      if (parsed.accent && ACCENTS.includes(parsed.accent)) this.accent.set(parsed.accent);
      if (parsed.fontSize) this.fontSize.set(parsed.fontSize);
      if (parsed.defaultPromptMode) this.defaultPromptMode.set(parsed.defaultPromptMode);
      if (parsed.model) this.model.set(parsed.model);
      if (parsed.reasoningEffort) this.reasoningEffort.set(parsed.reasoningEffort);
      if (parsed.sendOnEnter !== undefined) this.sendOnEnter.set(parsed.sendOnEnter);
      if (parsed.soundEffects !== undefined) this.soundEffects.set(parsed.soundEffects);
      if (parsed.showLatency !== undefined) this.showLatency.set(parsed.showLatency);
      if (parsed.plan) this.plan.set(parsed.plan);
    } catch {
      // ignore parsing errors
    }
  }

  private persist() {
    if (typeof localStorage === 'undefined') return;
    try {
      const payload: UserPreferences = {
        theme: this.theme(),
        accent: this.accent(),
        fontSize: this.fontSize(),
        defaultPromptMode: this.defaultPromptMode(),
        model: this.model(),
        reasoningEffort: this.reasoningEffort(),
        sendOnEnter: this.sendOnEnter(),
        soundEffects: this.soundEffects(),
        showLatency: this.showLatency(),
        plan: this.plan(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // storage unavailable
    }
  }

  setTheme(theme: AppTheme) {
    this.theme.set(theme);
  }

  setAccent(accent: AccentColor) {
    this.accent.set(accent);
  }

  setFontSize(fontSize: FontSize) {
    this.fontSize.set(fontSize);
  }

  setDefaultPromptMode(mode: string) {
    this.defaultPromptMode.set(mode);
  }

  setModel(model: string) {
    this.model.set(model);
  }

  setReasoningEffort(effort: 'low' | 'medium' | 'high') {
    this.reasoningEffort.set(effort);
  }

  toggleSendOnEnter() {
    this.sendOnEnter.update((v) => !v);
  }

  toggleSoundEffects() {
    this.soundEffects.update((v) => !v);
  }

  toggleShowLatency() {
    this.showLatency.update((v) => !v);
  }

  upgradeToPro() {
    this.plan.set('pro');
    this.persist();
  }

  resetDefaults() {
    this.theme.set(DEFAULT_PREFERENCES.theme);
    this.accent.set(DEFAULT_PREFERENCES.accent);
    this.fontSize.set(DEFAULT_PREFERENCES.fontSize);
    this.defaultPromptMode.set(DEFAULT_PREFERENCES.defaultPromptMode);
    this.model.set(DEFAULT_PREFERENCES.model);
    this.reasoningEffort.set(DEFAULT_PREFERENCES.reasoningEffort);
    this.sendOnEnter.set(DEFAULT_PREFERENCES.sendOnEnter);
    this.soundEffects.set(DEFAULT_PREFERENCES.soundEffects);
    this.showLatency.set(DEFAULT_PREFERENCES.showLatency);
  }

  exportData(sessions: unknown[], notes: unknown[]) {
    const exportObject = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      plan: this.plan(),
      preferences: {
        theme: this.theme(),
        accent: this.accent(),
        fontSize: this.fontSize(),
        model: this.model(),
      },
      conversations: sessions,
      memoryNotes: notes,
    };

    const blob = new Blob([JSON.stringify(exportObject, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `synora-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
