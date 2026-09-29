import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';

import { AgentApi } from './agent-api';
import { User } from '../models/chat.models';

/** Who is signed in. The app shows the auth page until `user` is set. */
@Injectable({ providedIn: 'root' })
export class AuthStore {
  private readonly api = inject(AgentApi);

  readonly user = signal<User | null>(null);
  /** False until the initial "am I signed in?" check finishes (avoids flashing the login page). */
  readonly ready = signal(false);
  readonly error = signal<string | null>(null);
  readonly isAdmin = computed(() => this.user()?.role === 'admin');

  async init() {
    try {
      this.user.set(await this.api.me());
    } catch (e) {
      if (!(e instanceof HttpErrorResponse && e.status === 401)) {
        this.error.set('Cannot reach the backend. Start it with: uvicorn app.main:app --port 8000');
      }
    } finally {
      this.ready.set(true);
    }
  }

  async login(email: string, password: string) {
    this.user.set(await this.api.login(email, password));
    this.error.set(null);
  }

  async signup(name: string, email: string, password: string) {
    this.user.set(await this.api.signup(name, email, password));
    this.error.set(null);
  }

  async logout() {
    try {
      await this.api.logout();
    } finally {
      this.user.set(null);
    }
  }

  /** The backend rejected our login (expired, signed out elsewhere, or account disabled). */
  expire() {
    if (!this.user()) return;
    this.user.set(null);
    this.error.set('Your session has ended. Please sign in again.');
  }
}
