import { Component, computed, inject, signal } from '@angular/core';

import { AgentApi } from '../../../../core/services/agent-api';
import {
  apiErrorMessage,
  confirmError,
  newPasswordError,
  required,
} from '../../../../core/utils/forms';

/** Settings → Account security: change your password (other devices get signed out). */
@Component({
  selector: 'app-change-password',
  templateUrl: './change-password.html',
  styleUrl: './change-password.css',
})
export class ChangePassword {
  private readonly api = inject(AgentApi);

  protected readonly current = signal('');
  protected readonly next = signal('');
  protected readonly confirm = signal('');
  protected readonly submitted = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal(false);

  protected readonly errors = computed(() => ({
    current: required(this.current(), 'Enter your current password.'),
    next:
      newPasswordError(this.next()) ??
      (this.next() === this.current() ? 'Choose a password different from the current one.' : null),
    confirm: confirmError(this.next(), this.confirm()),
  }));

  protected value(ev: Event) {
    return (ev.target as HTMLInputElement).value;
  }

  protected async submit(ev: Event) {
    ev.preventDefault();
    this.submitted.set(true);
    this.done.set(false);
    if (this.busy() || Object.values(this.errors()).some(Boolean)) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.changePassword(this.current(), this.next());
      for (const field of [this.current, this.next, this.confirm]) field.set('');
      this.submitted.set(false);
      this.done.set(true);
    } catch (e) {
      this.error.set(apiErrorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
