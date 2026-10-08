import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideLucideIcons } from '@lucide/angular';

import { App } from './app';
import { APP_ICONS } from './core/icons';
import { User } from './core/models/chat.models';
import { authInterceptor } from './core/services/auth-interceptor';

const ADA: User = {
  id: 'u1', email: 'ada@example.com', name: 'Ada', role: 'admin', disabled: false, created_at: '',
};

describe('App', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideLucideIcons(...APP_ICONS), // TestBed doesn't load app.config.ts
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  async function render(me: User | null) {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const req = http.expectOne('/api/auth/me');
    if (me) req.flush(me);
    else req.flush({ detail: 'Not signed in' }, { status: 401, statusText: 'Unauthorized' });
    await new Promise((r) => setTimeout(r)); // let AuthStore.init() settle
    await fixture.whenStable();
    return { fixture, el: fixture.nativeElement as HTMLElement };
  }

  it('shows the sign-in page when signed out', async () => {
    const { el } = await render(null);
    expect(el.querySelector('app-auth-page h1')?.textContent).toContain('Welcome back');
    expect(el.querySelector('app-sidebar')).toBeNull();
    expect(el.querySelector('.alert')).toBeNull(); // a 401 on load isn't an error
  });

  it('switches to the sign-up form', async () => {
    const { fixture, el } = await render(null);
    (el.querySelectorAll('.switch button')[1] as HTMLButtonElement).click();
    await fixture.whenStable();
    expect(el.querySelector('app-auth-page h1')?.textContent).toContain('Create your account');
    expect(el.querySelector('input[name="name"]')).not.toBeNull();
  });

  it('toggles password visibility with the eye icon', async () => {
    const { fixture, el } = await render(null);
    const reveal = el.querySelector('.reveal') as HTMLButtonElement;
    const input = el.querySelector('input[name="password"]') as HTMLInputElement;
    const iconMarkup = () => reveal.querySelector('svg')!.innerHTML;

    const eye = iconMarkup();
    expect(reveal.querySelector('svg path')).not.toBeNull(); // the named icon resolved
    expect(input.type).toBe('password');

    reveal.click();
    await fixture.whenStable();
    expect(input.type).toBe('text');
    expect(reveal.getAttribute('aria-label')).toBe('Hide password');
    expect(iconMarkup()).not.toBe(eye); // switched to eye-off
  });

  it('shows the chat and the account once signed in', async () => {
    const { el } = await render(ADA);
    expect(el.querySelector('.welcome h2')?.textContent).toContain('What should we work on?');
    expect(el.querySelector('.nav')?.textContent).toContain('Tools');
  });
});
