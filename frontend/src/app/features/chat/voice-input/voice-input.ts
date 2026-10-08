import { Component, OnDestroy, output, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

// The Web Speech API (Chrome, Edge, Safari); TypeScript's DOM types don't include it.
const Recognition =
  (globalThis as any).SpeechRecognition ?? (globalThis as any).webkitSpeechRecognition;

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone access is blocked. Allow it in your browser to use voice input.',
  'service-not-allowed':
    'Microphone access is blocked. Allow it in your browser to use voice input.',
  'audio-capture': 'No microphone was found.',
  network: 'Voice input needs an internet connection.',
};

/** The composer's voice button (shown in place of Send while the draft is empty): dictation with
 * the browser's speech recognition. */
@Component({
  selector: 'app-voice-input',
  imports: [LucideDynamicIcon],
  templateUrl: './voice-input.html',
  styleUrl: './voice-input.css',
})
export class VoiceInput implements OnDestroy {
  readonly started = output<void>();
  /** Everything heard since `started`, re-emitted as recognition refines it. */
  readonly heard = output<string>();
  readonly failed = output<string>();

  readonly supported = !!Recognition;
  readonly listening = signal(false);
  private recognition: any = null;

  protected toggle() {
    if (this.listening()) this.stop();
    else this.start();
  }

  stop() {
    this.recognition?.stop();
  }

  private start() {
    const r = new Recognition();
    r.lang = navigator.language;
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (e: any) => {
      const text = Array.from(e.results, (res: any) => res[0].transcript).join(' ');
      this.heard.emit(text.replace(/\s+/g, ' ').trim());
    };
    r.onerror = (e: any) => {
      if (e.error !== 'aborted' && e.error !== 'no-speech') {
        this.failed.emit(ERRORS[e.error] ?? `Voice input stopped (${e.error}).`);
      }
    };
    r.onend = () => {
      this.listening.set(false);
      this.recognition = null;
    };
    this.recognition = r;
    this.started.emit();
    this.listening.set(true);
    r.start();
  }

  ngOnDestroy() {
    this.recognition?.abort();
  }
}
