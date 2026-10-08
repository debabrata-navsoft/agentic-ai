import {
  Component,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatStore } from '../../../core/services/chat-store';
import type { PromptType } from '../chat-panel/chat-panel';

interface MenuItem {
  icon: string;
  label: string;
  hint: string;
  /** Items after the first ones are grouped under a heading. */
  group?: string;
  /** Set (true or false) only on mode items, which act as radio buttons. */
  active?: boolean;
  run: () => void;
}

/** The composer's "+" button: attach files, upload to the knowledge base, pick a prompt mode, or
 * start a chat with an agent. */
@Component({
  selector: 'app-composer-menu',
  imports: [LucideDynamicIcon],
  templateUrl: './composer-menu.html',
  styleUrl: './composer-menu.css',
})
export class ComposerMenu {
  /** The user wants to attach files to the message being written. */
  readonly attach = output<void>();
  readonly modes = input.required<PromptType[]>();
  readonly activeMode = input('');
  readonly mode = output<string>();

  protected readonly store = inject(ChatStore);
  private readonly host = inject(ElementRef);
  private readonly kbPicker = viewChild.required<ElementRef<HTMLInputElement>>('kbPicker');
  private readonly search = viewChild<ElementRef<HTMLInputElement>>('search');

  /** Null while closed; when open, it faces whichever side of the "+" has more room. */
  protected readonly placement = signal<{ up: boolean; room: number } | null>(null);
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
    ...this.modes().map((m) => ({
      icon: m.icon,
      label: m.label,
      hint: m.description,
      group: 'Mode',
      active: m.id === this.activeMode(),
      run: () => this.mode.emit(m.id),
    })),
    ...this.store.agents().map((a) => ({
      icon: a.icon,
      label: a.name,
      hint: a.description || a.role,
      group: 'New chat with agent',
      run: () => this.store.newChat(a.id),
    })),
  ]);

  /** Matching items; `heading` is set on the first item of each group. */
  protected readonly items = computed(() => {
    const q = this.query().trim().toLowerCase();
    const matches = this.allItems().filter((i) => `${i.label} ${i.hint}`.toLowerCase().includes(q));
    return matches.map((item, i) => ({
      ...item,
      heading: item.group !== matches[i - 1]?.group ? item.group : undefined,
    }));
  });

  constructor() {
    effect(() => this.search()?.nativeElement.focus());
  }

  protected toggle() {
    if (this.placement()) return this.close();
    const { top, bottom } = this.host.nativeElement.getBoundingClientRect();
    const below = innerHeight - bottom;
    // 70px covers the gap to the button, the search box, and a margin from the window edge.
    this.placement.set({ up: top >= below, room: Math.max(top, below) - 70 });
    this.query.set('');
  }

  protected close() {
    this.placement.set(null);
  }

  protected choose(item: MenuItem) {
    this.close();
    item.run();
  }

  protected onKbPick(ev: Event) {
    const input = ev.target as HTMLInputElement;
    this.store.upload(Array.from(input.files ?? []));
    input.value = '';
  }

  @HostListener('document:click', ['$event'])
  protected onDocumentClick(ev: MouseEvent) {
    if (!this.host.nativeElement.contains(ev.target)) this.close();
  }

  @HostListener('document:keydown.escape')
  protected onEscape() {
    this.close();
  }
}
