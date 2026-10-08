import { Injectable, signal } from '@angular/core';

/** Reads text aloud with the browser's speech synthesis, one item at a time. */
@Injectable({ providedIn: 'root' })
export class SpeechService {
  readonly supported = typeof speechSynthesis !== 'undefined';
  /** What is being read now (any identity, e.g. a message), or null. */
  readonly speaking = signal<unknown>(null);

  /** Read `text` for `key`, or stop if `key` is already being read. */
  toggle(key: unknown, text: string) {
    speechSynthesis.cancel();
    if (this.speaking() === key) return this.speaking.set(null);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = navigator.language;
    utterance.onend = utterance.onerror = () => {
      if (this.speaking() === key) this.speaking.set(null);
    };
    this.speaking.set(key);
    speechSynthesis.speak(utterance);
  }
}
