import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { Ask } from './features/ask/ask';
import { Write } from './features/write/write';

type Tab = 'ask' | 'write';

@Component({
  selector: 'app-root',
  imports: [Ask, Write],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  protected readonly tab = signal<Tab>('ask');
}
