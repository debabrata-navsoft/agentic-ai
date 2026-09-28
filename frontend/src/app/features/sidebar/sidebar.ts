import { Component, inject, signal } from '@angular/core';

import { ChatStore } from '../../core/services/chat-store';

/** Left panel: conversation list, long-term memory viewer, and tool catalog. */
@Component({
  selector: 'app-sidebar',
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
})
export class Sidebar {
  protected readonly store = inject(ChatStore);
  protected readonly tab = signal<'chats' | 'memory' | 'tools'>('chats');
}
