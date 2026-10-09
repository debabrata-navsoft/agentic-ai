import { TestBed } from '@angular/core/testing';
import { Write } from './write';
import { ModelApi } from '../../core/model-api';

describe('Write', () => {
  async function render(info: object) {
    await TestBed.configureTestingModule({
      imports: [Write],
      providers: [{ provide: ModelApi, useValue: { info: async () => info } }],
    }).compileComponents();
    const fixture = TestBed.createComponent(Write);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the trained model', async () => {
    const el = await render({
      loaded: true,
      params: 826368,
      config: { n_layer: 4, block_size: 128 },
      step: 3000,
      val_loss: 1.5,
    });
    expect(el.querySelector('.status')?.textContent).toContain('826,368 parameters');
    expect(el.querySelector<HTMLButtonElement>('.actions button')?.disabled).toBe(false);
  });

  it('disables Generate until a model is trained', async () => {
    const el = await render({ loaded: false });
    expect(el.querySelector('.status')?.textContent).toContain('No trained model');
    expect(el.querySelector<HTMLButtonElement>('.actions button')?.disabled).toBe(true);
  });
});
