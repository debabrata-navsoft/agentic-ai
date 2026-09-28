import { parseSseFrame } from './agent-api';

describe('parseSseFrame', () => {
  it('parses event and JSON data, ignoring comments', () => {
    expect(parseSseFrame(': ping\nevent: text\ndata: {"delta":"hi"}')).toEqual({
      event: 'text',
      data: { delta: 'hi' },
    });
  });

  it('returns null for comment-only frames', () => {
    expect(parseSseFrame(': ping')).toBeNull();
  });
});
