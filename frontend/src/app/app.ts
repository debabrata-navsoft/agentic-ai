import { Component, OnInit, inject } from '@angular/core';

import { ChatStore } from './core/services/chat-store';
import { ChatPanel } from './features/chat/chat-panel/chat-panel';
import { Sidebar } from './features/sidebar/sidebar';

@Component({
  selector: 'app-root',
  imports: [Sidebar, ChatPanel],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly store = inject(ChatStore);

  ngOnInit() {
    this.store.init();
  }
}
