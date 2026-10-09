import { TestBed } from '@angular/core/testing';
import { Ask } from './ask';
import { ModelApi, SearchResult } from '../../core/model-api';

describe('Ask', () => {
  const result: SearchResult = {
    query: 'where do bananas grow',
    terms: ['bananas', 'grow'],
    answer: 'Bananas grow in tropical regions.',
    results: [
      { doc: 'fruit.txt', passage: 1, text: 'Bananas grow in tropical regions.', score: 3.2 },
    ],
    searched_passages: 2,
  };

  async function setup(search: () => Promise<SearchResult>) {
    await TestBed.configureTestingModule({
      imports: [Ask],
      providers: [
        {
          provide: ModelApi,
          useValue: { docs: async () => [{ name: 'fruit.txt', size: 90, passages: 2 }], search },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(Ask);
    await fixture.whenStable();
    return { fixture, el: fixture.nativeElement as HTMLElement };
  }

  async function ask(fixture: { whenStable(): Promise<unknown> }, el: HTMLElement, text: string) {
    const box = el.querySelector('textarea')!;
    box.value = text;
    box.dispatchEvent(new Event('input'));
    box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await fixture.whenStable();
  }

  it('lists documents and shows a highlighted answer with sources', async () => {
    const { fixture, el } = await setup(async () => result);
    expect(el.querySelector('.doc-name')?.textContent).toContain('fruit.txt');

    await ask(fixture, el, 'where do bananas grow');
    expect(el.querySelector('.question')?.textContent).toContain('where do bananas grow');
    expect(el.querySelector('.answer-text')?.textContent).toContain('tropical regions');
    expect(Array.from(el.querySelectorAll('.answer-text mark')).map((m) => m.textContent)).toEqual([
      'Bananas',
      'grow',
    ]);
    expect(el.querySelector('summary')?.textContent).toContain('1 sources');
  });

  it('says so when nothing matches', async () => {
    const { fixture, el } = await setup(async () => ({ ...result, answer: '', results: [] }));
    await ask(fixture, el, 'quantum physics');
    expect(el.querySelector('.answer')?.textContent).toContain('Nothing in your documents matches');
  });
});
