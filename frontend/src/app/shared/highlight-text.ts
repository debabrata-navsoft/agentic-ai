import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { highlight } from '../core/highlight';

/** Renders `text` with words matching `terms` wrapped in <mark>. Segments are computed once per input. */
@Component({
  selector: 'app-highlight',
  template: `@for (seg of segments(); track $index) {
    @if (seg.hit) {
      <mark>{{ seg.text }}</mark>
    } @else {
      {{ seg.text }}
    }
  }`,
  styles: `
    mark {
      background: color-mix(in srgb, var(--accent) 25%, transparent);
      color: inherit;
      border-radius: 3px;
      padding: 0 1px;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HighlightText {
  readonly text = input.required<string>();
  readonly terms = input.required<string[]>();
  protected readonly segments = computed(() => highlight(this.text(), this.terms()));
}
