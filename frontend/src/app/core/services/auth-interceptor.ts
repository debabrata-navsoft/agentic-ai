import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs';

import { AuthStore } from './auth-store';

/** Any 401 outside the auth endpoints means the login is gone: send the user back to sign in. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthStore);
  return next(req).pipe(
    tap({
      error: (e) => {
        if (e instanceof HttpErrorResponse && e.status === 401 && !req.url.includes('/auth/')) {
          auth.expire();
        }
      },
    }),
  );
};
