import { Component, OnInit, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { AgentApi } from '../../core/services/agent-api';
import { AuthStore } from '../../core/services/auth-store';
import { ChatStore } from '../../core/services/chat-store';
import { User } from '../../core/models/chat.models';

/** Admin-only page listing accounts, with role and enable/disable controls. */
@Component({
  selector: 'app-user-admin',
  imports: [LucideDynamicIcon],
  templateUrl: './user-admin.html',
  styleUrl: './user-admin.css',
})
export class UserAdmin implements OnInit {
  private readonly api = inject(AgentApi);
  protected readonly auth = inject(AuthStore);
  protected readonly store = inject(ChatStore);
  protected readonly users = signal<User[]>([]);
  protected readonly error = signal<string | null>(null);

  async ngOnInit() {
    try {
      this.users.set(await this.api.users());
    } catch {
      this.error.set('Could not load users.');
    }
  }

  protected async update(user: User, patch: Partial<Pick<User, 'role' | 'disabled'>>) {
    this.error.set(null);
    try {
      const updated = await this.api.updateUser(user.id, patch);
      this.users.update((l) => l.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e: any) {
      this.error.set(e?.error?.detail ?? 'Update failed.');
    }
  }
}
