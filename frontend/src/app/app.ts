import { Component, OnInit, computed, effect, inject, untracked } from '@angular/core';

import { AuthStore } from './core/services/auth-store';
import { ChatStore } from './core/services/chat-store';
import { AuthPage } from './features/auth/auth-page';
import { ChatPanel } from './features/chat/chat-panel/chat-panel';
import { Sidebar } from './features/sidebar/sidebar';

@Component({
  selector: 'app-root',
  imports: [AuthPage, Sidebar, ChatPanel],
  templateUrl: './app.html',
  styleUrl: './app.css',
  host: { '[class.signed-in]': 'auth.user()' },
})
export class App implements OnInit {
  protected readonly auth = inject(AuthStore);
  private readonly store = inject(ChatStore);
  private readonly userId = computed(() => this.auth.user()?.id);

  constructor() {
    // Load the signed-in user's data; drop it all when they sign out or switch accounts.
    effect(() => {
      const id = this.userId();
      untracked(() => {
        this.store.reset();
        if (id) this.store.init();
      });
    });
  }

  ngOnInit() {
    this.auth.init();
  }
}
