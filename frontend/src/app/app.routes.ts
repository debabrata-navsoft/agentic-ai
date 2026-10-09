import { inject } from '@angular/core';
import { Routes } from '@angular/router';
import { AuthStore } from './core/services/auth-store';
import { adminGuard, authGuard, guestGuard } from './core/guards/auth.guard';

export { adminGuard, authGuard, guestGuard };

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/auth-page').then((m) => m.AuthPage),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./features/chat/chat-panel/chat-panel').then((m) => m.ChatPanel),
  },
  {
    path: 'agents',
    canActivate: [authGuard],
    loadComponent: () => import('./features/pages/agents-page/agents-page').then((m) => m.AgentsPage),
  },
  {
    path: 'docs',
    canActivate: [authGuard],
    loadComponent: () => import('./features/pages/docs-page/docs-page').then((m) => m.DocsPage),
  },
  {
    path: 'memory',
    canActivate: [authGuard],
    loadComponent: () => import('./features/pages/memory-page/memory-page').then((m) => m.MemoryPage),
  },
  {
    path: 'tools',
    canActivate: [authGuard],
    loadComponent: () => import('./features/pages/tools-page/tools-page').then((m) => m.ToolsPage),
  },
  {
    path: 'admin',
    canActivate: [adminGuard],
    loadComponent: () => {
      const auth = inject(AuthStore);
      return auth.user()
        ? import('./features/admin/user-admin').then((m) => m.UserAdmin)
        : import('./features/auth/auth-page').then((m) => m.AuthPage);
    },
  },
  {
    path: '**',
    redirectTo: '',
  },
];
