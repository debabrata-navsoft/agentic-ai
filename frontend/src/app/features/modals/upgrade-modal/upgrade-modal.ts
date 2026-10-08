import { Component, HostListener, inject, input, output, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { SettingsStore } from '../../../core/services/settings-store';

@Component({
  selector: 'app-upgrade-modal',
  imports: [LucideDynamicIcon],
  templateUrl: './upgrade-modal.html',
  styleUrl: './upgrade-modal.css',
})
export class UpgradeModal {
  readonly isOpen = input<boolean>(false);
  readonly closed = output<void>();

  protected readonly settings = inject(SettingsStore);
  protected readonly billingCycle = signal<'monthly' | 'yearly'>('yearly');
  protected readonly isUpgrading = signal<boolean>(false);
  protected readonly isSuccess = signal<boolean>(false);

  @HostListener('window:keydown.escape')
  onEscape() {
    if (this.isOpen()) {
      this.close();
    }
  }

  close() {
    this.closed.emit();
    this.isSuccess.set(false);
    this.isUpgrading.set(false);
  }

  onBackdropClick(ev: MouseEvent) {
    if ((ev.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.close();
    }
  }

  confirmUpgrade() {
    this.isUpgrading.set(true);
    setTimeout(() => {
      this.settings.upgradeToPro();
      this.isUpgrading.set(false);
      this.isSuccess.set(true);
      setTimeout(() => {
        this.close();
      }, 1600);
    }, 900);
  }
}
