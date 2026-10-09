import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthStore } from '../services/auth-store';

/**
 * Route guard: allows only authenticated users.
 * Redirects unauthenticated users to /login.
 */
export const authGuard: CanActivateFn = async () => {
  const auth = inject(AuthStore);
  const router = inject(Router);

  if (!auth.ready()) {
    await auth.init();
  }

  if (auth.user()) {
    return true;
  }

  return router.createUrlTree(['/login']);
};

/**
 * Route guard: allows only guest (unauthenticated) users.
 * If already logged in, redirects immediately to the dashboard ('/'),
 * preventing authenticated users from seeing the login page when clicking browser back.
 */
export const guestGuard: CanActivateFn = async () => {
  const auth = inject(AuthStore);
  const router = inject(Router);

  if (!auth.ready()) {
    await auth.init();
  }

  if (!auth.user()) {
    return true;
  }

  return router.createUrlTree(['/']);
};

/**
 * Route guard: allows admin access.
 * - When signed out: allows access so the Admin Sign-in page can be displayed.
 * - When signed in as admin: allows access to the admin console.
 * - When signed in as non-admin: blocks access and redirects to dashboard ('/').
 */
export const adminGuard: CanActivateFn = async () => {
  const auth = inject(AuthStore);
  const router = inject(Router);

  if (!auth.ready()) {
    await auth.init();
  }

  // Block signed-in non-admin users
  if (auth.user() && !auth.isAdmin()) {
    return router.createUrlTree(['/']);
  }

  return true;
};

