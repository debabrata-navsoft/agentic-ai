import {
  Component,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatStore } from '../../../core/services/chat-store';

interface MenuItem {
  icon: string;
  label: string;
  hint: string;
  agent?: boolean;
  run: () => void;
}

/** The composer's "+" button: attach files, upload to the knowledge base, or pick an agent. */
@Component({
  selector: 'app-composer-menu',
  imports: [LucideDynamicIcon],
  templateUrl: './composer-menu.html',
  styleUrl: './composer-menu.css',
})
export class ComposerMenu {
  /** The user wants to attach files to the message being written. */
  readonly attach = output<void>();

  protected readonly store = inject(ChatStore);
  private readonly host = inject(ElementRef);
  private readonly kbPicker = viewChild.required<ElementRef<HTMLInputElement>>('kbPicker');
  private readonly search = viewChild<ElementRef<HTMLInputElement>>('search');

  protected readonly open = signal(false);
  protected readonly query = signal('');
  protected readonly kbAccept = computed(() => this.store.supportedTypes().join(','));

  private readonly allItems = computed<MenuItem[]>(() => [
    {
      icon: 'paperclip',
      label: 'Add photos & files',
      hint: 'Attach to this message',
      run: () => this.attach.emit(),
    },
    {
      icon: 'upload',
      label: 'Add to knowledge base',
      hint: 'Upload documents to search later',
      run: () => this.kbPicker().nativeElement.click(),
    },
    ...this.store.agents().map((a) => ({
      icon: a.icon,
      label: a.name,
      hint: a.description || a.role,
      agent: true,
      run: () => this.store.newChat(a.id),
    })),
  ]);

  protected readonly items = computed(() => {
    const q = this.query().trim().toLowerCase();
    return this.allItems().filter((i) => `${i.label} ${i.hint}`.toLowerCase().includes(q));
  });
  /** The agents heading goes above the first matching agent. */
  protected readonly firstAgent = computed(() => this.items().find((i) => i.agent));

  constructor() {
    effect(() => this.search()?.nativeElement.focus());
  }

  protected toggle() {
    this.query.set('');
    this.open.update((o) => !o);
  }

  protected choose(item: MenuItem) {
    this.open.set(false);
    item.run();
  }

  protected onKbPick(ev: Event) {
    const input = ev.target as HTMLInputElement;
    this.store.upload(Array.from(input.files ?? []));
    input.value = '';
  }

  @HostListener('document:click', ['$event'])
  protected onDocumentClick(ev: MouseEvent) {
    if (!this.host.nativeElement.contains(ev.target)) this.open.set(false);
  }

  @HostListener('document:keydown.escape')
  protected onEscape() {
    this.open.set(false);
  }
}
