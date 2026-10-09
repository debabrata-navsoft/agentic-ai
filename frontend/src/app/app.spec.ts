import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { ModelApi } from './core/model-api';

describe('App', () => {
  it('switches between the Ask and Write pages', async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        {
          provide: ModelApi,
          useValue: { info: async () => ({ loaded: false }), docs: async () => [] },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const ask = el.querySelector<HTMLElement>('app-ask')!;
    const write = el.querySelector<HTMLElement>('app-write')!;

    expect(el.querySelector('h1')?.textContent).toContain('Synora AI');
    expect([ask.hidden, write.hidden]).toEqual([false, true]);

    el.querySelectorAll<HTMLButtonElement>('nav button')[1].click();
    await fixture.whenStable();
    expect([ask.hidden, write.hidden]).toEqual([true, false]);
  });
});
