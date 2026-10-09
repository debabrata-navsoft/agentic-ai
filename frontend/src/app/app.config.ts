import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideLucideIcons } from '@lucide/angular';

import { APP_ICONS } from './core/icons';
import { authInterceptor } from './core/services/auth-interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch(), withInterceptors([authInterceptor])),
    // Icons usable by name anywhere: <svg lucideIcon="eye"></svg>. Add new ones to core/icons.ts.
    provideLucideIcons(...APP_ICONS),
  ],
};
