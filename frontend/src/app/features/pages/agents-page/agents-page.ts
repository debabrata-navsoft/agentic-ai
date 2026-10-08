import { Component, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { AgentProfile } from '../../../core/models/chat.models';
import { ChatStore } from '../../../core/services/chat-store';
import { AgentEditor, PROVIDER_NAMES } from './agent-editor/agent-editor';

const GRADIENTS = [
  'linear-gradient(135deg, #3b82f6, #60a5fa)',
  'linear-gradient(135deg, #10b981, #34d399)',
  'linear-gradient(135deg, #f59e0b, #fbbf24)',
  'linear-gradient(135deg, #ec4899, #f472b6)',
  'linear-gradient(135deg, #14b8a6, #5eead4)',
  'linear-gradient(135deg, #ef4444, #f87171)',
];

/** The user's agents: start a chat as one, or create, edit, and delete them. */
@Component({
  selector: 'app-agents-page',
  imports: [LucideDynamicIcon, AgentEditor],
  templateUrl: './agents-page.html',
  styleUrl: './agents-page.css',
})
export class AgentsPage {
  protected readonly store = inject(ChatStore);
  protected readonly searchQuery = signal('');
  /** The agent open in the editor; 'new' for a blank one. */
  protected readonly editing = signal<AgentProfile | 'new' | null>(null);
  protected readonly error = signal<string | null>(null);

  protected readonly filteredAgents = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const agents = this.store.agents();
    if (!q) return agents;
    return agents.filter((a) =>
      [a.name, a.role, a.description, ...a.tools.map((t) => this.toolLabel(t))].some((s) =>
        s.toLowerCase().includes(q),
      ),
    );
  });

  /** Colors follow the agent's place in the full list, so filtering doesn't change them. */
  protected gradient(agent: AgentProfile) {
    return GRADIENTS[this.store.agents().indexOf(agent) % GRADIENTS.length];
  }

  protected providerName(agent: AgentProfile) {
    const provider = agent.provider || this.store.health()?.default_provider;
    return provider ? PROVIDER_NAMES[provider] : '';
  }

  protected toolLabel(name: string) {
    return this.store.toolLabels().get(name) ?? name;
  }

  protected async remove(agent: AgentProfile) {
    if (!confirm(`Delete ${agent.name}? Chats with it will continue as plain Synora.`)) return;
    this.error.set(null);
    try {
      await this.store.deleteAgent(agent.id);
    } catch (e: any) {
      this.error.set(e?.error?.detail ?? 'Could not delete the agent.');
    }
  }
}
