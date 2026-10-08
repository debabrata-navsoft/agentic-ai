import { Component, computed, inject, input, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { AgentApi } from '../../core/services/agent-api';
import { AuthStore } from '../../core/services/auth-store';
import { ChatStore } from '../../core/services/chat-store';
import {
  apiErrorMessage,
  confirmError,
  emailError,
  newPasswordError,
  required,
} from '../../core/utils/forms';

type Mode = 'signin' | 'signup' | 'forgot' | 'reset';

/** Heading, subheading and button label for each mode. */
const TEXT: Record<Mode, [string, string, string]> = {
  signin: ['Welcome back', 'Sign in to continue to Synora.', 'Sign in'],
  signup: ['Create your account', 'Start working with your AI agent.', 'Create account'],
  forgot: [
    'Forgot your password?',
    "Enter your email and we'll send you a reset link.",
    'Send reset link',
  ],
  reset: ['Choose a new password', 'Use at least 8 characters.', 'Update password'],
};
const ADMIN_SIGNIN = [
  'Admin sign in',
  'Only administrator accounts can sign in here.',
  'Sign in as admin',
];

/**
 * Sign in, sign up, forgot password, and reset password (from an emailed link). At /admin it's
 * the admin sign-in: no sign-up, and only admin accounts get in.
 */
@Component({
  selector: 'app-auth-page',
  imports: [LucideDynamicIcon],
  templateUrl: './auth-page.html',
  styleUrl: './auth-page.css',
})
export class AuthPage {
  readonly admin = input(false);

  protected readonly auth = inject(AuthStore);
  private readonly api = inject(AgentApi);
  private readonly store = inject(ChatStore);
  private readonly selectedMode = signal<Mode>(this.auth.resetToken() ? 'reset' : 'signin');
  protected readonly mode = computed<Mode>(() =>
    this.admin() && this.selectedMode() === 'signup' ? 'signin' : this.selectedMode(),
  );
  protected readonly text = computed(() =>
    this.admin() && this.mode() === 'signin' ? ADMIN_SIGNIN : TEXT[this.mode()],
  );

  protected readonly name = signal('');
  protected readonly email = signal('');
  protected readonly password = signal('');
  protected readonly confirm = signal('');
  protected readonly showPassword = signal(false);
  protected readonly busy = signal(false);
  protected readonly formError = signal<string | null>(null);
  /** A success message, e.g. after requesting a reset link. */
  protected readonly notice = signal<string | null>(null);
  /** Field errors show after the first submit, then update as the user types. */
  protected readonly submitted = signal(false);

  /** Which fields each mode shows. */
  protected readonly has = computed(() => {
    const m = this.mode();
    return {
      name: m === 'signup',
      email: m !== 'reset',
      password: m !== 'forgot',
      confirm: m === 'signup' || m === 'reset',
    };
  });

  protected readonly errors = computed(() => {
    const has = this.has();
    const newPassword = this.mode() !== 'signin';
    return {
      name: has.name ? required(this.name(), 'Enter your name.') : null,
      email: has.email ? emailError(this.email()) : null,
      password: !has.password
        ? null
        : newPassword
          ? newPasswordError(this.password())
          : required(this.password(), 'Enter your password.'),
      confirm: has.confirm ? confirmError(this.password(), this.confirm()) : null,
    };
  });

  private readonly userFeatures = [
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
  private readonly adminFeatures = [
    { icon: 'users', title: 'Manage users', text: 'See every account that uses Synora.' },
    { icon: 'shield', title: 'Control access', text: 'Promote admins or disable accounts.' },
    { icon: 'log-out', title: 'Instant sign-out', text: 'Disabling a user ends their session.' },
  ];
  protected readonly features = computed(() =>
    this.admin() ? this.adminFeatures : this.userFeatures,
  );

  protected setMode(mode: Mode) {
    this.selectedMode.set(mode);
    this.submitted.set(false);
    this.formError.set(null);
    this.notice.set(null);
  }

  /** From the admin sign-in (/admin), back to the regular one (/). */
  protected toRegularSignIn() {
    this.setMode('signin');
    this.store.setActiveView('chat');
  }

  protected value(ev: Event) {
    return (ev.target as HTMLInputElement).value;
  }

  protected async submit(ev: Event) {
    ev.preventDefault();
    this.submitted.set(true);
    if (this.busy() || Object.values(this.errors()).some(Boolean)) return;
    this.busy.set(true);
    this.formError.set(null);
    this.notice.set(null);
    try {
      switch (this.mode()) {
        case 'signin':
          await this.auth.login(this.email(), this.password(), this.admin());
          break;
        case 'signup':
          await this.auth.signup(this.name(), this.email(), this.password());
          break;
        case 'forgot':
          await this.api.forgotPassword(this.email());
          this.notice.set(
            "If an account exists for that email, we've sent a reset link. Check your inbox.",
          );
          break;
        case 'reset':
          await this.api.resetPassword(this.auth.resetToken()!, this.password());
          this.auth.resetToken.set(null);
          this.setMode('signin');
          this.password.set('');
          this.confirm.set('');
          this.notice.set('Password updated. Sign in with your new password.');
          break;
      }
    } catch (e) {
      this.formError.set(apiErrorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
