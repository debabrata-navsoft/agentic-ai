import { Component, computed, inject, input, linkedSignal, output, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { AgentInput, AgentProfile, Provider } from '../../../../core/models/chat.models';
import { ChatStore } from '../../../../core/services/chat-store';

export const PROVIDER_NAMES: Record<Provider, string> = { anthropic: 'Claude', openai: 'OpenAI' };

const ICONS = ['bot', 'sparkles', 'globe', 'code', 'file-search', 'calculator', 'brain', 'wrench'];

/** Modal form to create an agent (`agent` null) or edit one. */
@Component({
  selector: 'app-agent-editor',
  imports: [LucideDynamicIcon],
  templateUrl: './agent-editor.html',
  styleUrl: './agent-editor.css',
})
export class AgentEditor {
  readonly agent = input<AgentProfile | null>(null);
  readonly closed = output<void>();

  protected readonly store = inject(ChatStore);
  protected readonly icons = ICONS;
  protected readonly providerNames = PROVIDER_NAMES;
  protected readonly providers = ['anthropic', 'openai'] as const;
  /** A new agent starts blank, with every tool enabled. */
  protected readonly form = linkedSignal<AgentInput>(() => ({
    ...{
      name: '',
      role: '',
      icon: 'bot',
      description: '',
      instructions: '',
      provider: '' as const,
    },
    tools: this.store.tools().map((t) => t.name),
    ...this.agent(),
  }));
  /** The provider this agent will run on, resolving "Default". */
  protected readonly provider = computed(
    () => this.form().provider || this.store.health()?.default_provider,
  );
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected set<K extends keyof AgentInput>(key: K, value: AgentInput[K]) {
    this.form.update((f) => ({ ...f, [key]: value }));
  }

  protected toggleTool(name: string) {
    const tools = this.form().tools;
    this.set('tools', tools.includes(name) ? tools.filter((t) => t !== name) : [...tools, name]);
  }

  protected async save() {
    if (!this.form().name.trim()) return this.error.set('Give the agent a name.');
    this.saving.set(true);
    this.error.set(null);
    try {
      // The backend trims whitespace.
      await this.store.saveAgent(this.form(), this.agent()?.id);
      this.closed.emit();
    } catch (e: any) {
      const detail = e?.error?.detail;
      this.error.set(typeof detail === 'string' ? detail : 'Could not save the agent.');
    } finally {
      this.saving.set(false);
    }
  }
}
