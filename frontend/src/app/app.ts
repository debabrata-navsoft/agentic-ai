import { Component, OnInit, computed, effect, inject, untracked } from '@angular/core';

import { AuthStore } from './core/services/auth-store';
import { ActiveView, ChatStore } from './core/services/chat-store';
import { AuthPage } from './features/auth/auth-page';
import { ChatPanel } from './features/chat/chat-panel/chat-panel';
import { AgentsPage } from './features/pages/agents-page/agents-page';
import { DocsPage } from './features/pages/docs-page/docs-page';
import { MemoryPage } from './features/pages/memory-page/memory-page';
import { ToolsPage } from './features/pages/tools-page/tools-page';
import { Sidebar } from './features/sidebar/sidebar';
import { UserAdmin } from './features/admin/user-admin';

/** The URL of each page; `/admin` is the admin-only Users page. */
const PATHS: Record<ActiveView, string> = {
  chat: '/',
  agents: '/agents',
  docs: '/docs',
  memory: '/memory',
  tools: '/tools',
  users: '/admin',
};

const VIEWS = Object.fromEntries(Object.entries(PATHS).map(([v, p]) => [p, v as ActiveView]));

@Component({
  selector: 'app-root',
  imports: [AuthPage, Sidebar, ChatPanel, AgentsPage, DocsPage, MemoryPage, ToolsPage, UserAdmin],
  templateUrl: './app.html',
  styleUrl: './app.css',
  host: {
    '[class.signed-in]': 'auth.user()',
    '(window:popstate)': 'openUrl()',
    '(window:pageshow)': 'onPageShow($event)',
  },
})
export class App implements OnInit {
  protected readonly auth = inject(AuthStore);
  protected readonly store = inject(ChatStore);
  private readonly userId = computed(() => this.auth.user()?.id);

  constructor() {
    // Load the signed-in user's data; drop it all when they sign out or switch accounts.
    effect(() => {
      const id = this.userId();
      untracked(() => {
        this.store.reset();
        if (id) {
          this.store.init();
          if (
            location.pathname === '/login' ||
            location.pathname === '/signin' ||
            location.pathname === '/signup'
          ) {
            history.replaceState(null, '', '/');
          }
        }
        this.openUrl(); // re-runs the route guard for the new user (e.g. a non-admin on /admin)
      });
    });

    // Open the page in the address bar, then keep the address bar in step with the page.
    this.openUrl();
    effect(() => {
      const path = PATHS[this.store.activeView()];
      if (location.pathname !== path) history.pushState(null, '', path);
    });
  }

  /** Show the page for the current URL, enforcing route guards. */
  protected openUrl() {
    const raw = location.pathname.replace(/\/+$/, '') || '/';

    // Route guard: if signed in and navigating back to login/signin/signup, redirect to chat
    if (this.auth.user() && (raw === '/login' || raw === '/signin' || raw === '/signup')) {
      history.replaceState(null, '', '/');
      this.store.setActiveView('chat');
      return;
    }

    // Route guard: if signed in but not an admin, block /admin
    if (this.auth.user() && !this.auth.isAdmin() && raw === '/admin') {
      history.replaceState(null, '', '/');
      this.store.setActiveView('chat');
      return;
    }

    // Route guard: if signed out and attempting to access protected pages, stay on /
    if (
      !this.auth.user() &&
      raw !== '/' &&
      raw !== '/admin' &&
      raw !== '/login' &&
      raw !== '/reset-password'
    ) {
      history.replaceState(null, '', '/');
      this.store.setActiveView('chat');
      return;
    }

    this.store.setActiveView(VIEWS[raw] ?? 'chat');
  }

  protected onPageShow(ev: PageTransitionEvent) {
    if (ev.persisted) {
      this.auth.init();
    }
    this.openUrl();
  }

  ngOnInit() {
    this.auth.init();
  }
}
