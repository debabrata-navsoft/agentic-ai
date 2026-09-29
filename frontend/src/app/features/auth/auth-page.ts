import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { AuthStore } from '../../core/services/auth-store';

type Mode = 'signin' | 'signup';

/** Sign-in / create-account screen shown until a user is signed in. */
@Component({
  selector: 'app-auth-page',
  imports: [LucideDynamicIcon],
  templateUrl: './auth-page.html',
  styleUrl: './auth-page.css',
})
export class AuthPage {
  protected readonly auth = inject(AuthStore);
  protected readonly mode = signal<Mode>('signin');
  protected readonly name = signal('');
  protected readonly email = signal('');
  protected readonly password = signal('');
  protected readonly showPassword = signal(false);
  protected readonly busy = signal(false);
  protected readonly formError = signal<string | null>(null);

  protected readonly features = [
    {
      icon: 'globe',
      title: 'Researches the web',
      text: 'Searches and reads pages, then cites its sources.',
    },
    {
      icon: 'file-text',
      title: 'Knows your documents',
      text: 'Answers from the files you upload, privately.',
    },
    {
      icon: 'brain',
      title: 'Remembers you',
      text: 'Keeps long-term notes across your conversations.',
    },
  ];

  protected setMode(mode: Mode) {
    this.mode.set(mode);
    this.formError.set(null);
  }

  protected value(ev: Event) {
    return (ev.target as HTMLInputElement).value;
  }

  protected async submit(ev: Event) {
    ev.preventDefault(); // the browser has already checked required/type/minlength
    if (this.busy()) return;
    this.busy.set(true);
    this.formError.set(null);
    try {
      if (this.mode() === 'signin') {
        await this.auth.login(this.email(), this.password());
      } else {
        await this.auth.signup(this.name(), this.email(), this.password());
      }
    } catch (e) {
      this.formError.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}

function errorMessage(e: unknown): string {
  if (!(e instanceof HttpErrorResponse)) return 'Something went wrong. Please try again.';
  if (e.status === 0 || e.status >= 500) return 'Cannot reach the server. Is the backend running?';
  const detail = e.error?.detail;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors: [{loc: [..., field], msg}, ...]
  if (Array.isArray(detail) && detail.length) return `${detail[0].loc?.at(-1)}: ${detail[0].msg}`;
  return `Request failed (${e.status})`;
}
