import { Pipe, PipeTransform } from '@angular/core';
import { marked } from 'marked';

marked.use({ gfm: true, breaks: true });

/** Renders Markdown to HTML. Bind with [innerHTML]; Angular sanitizes the result. */
@Pipe({ name: 'markdown' })
export class MarkdownPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return value ? (marked.parse(value, { async: false }) as string) : '';
  }
}
