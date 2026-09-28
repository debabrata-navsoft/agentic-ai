import { AgentEvent, AssistantMessage, ToolPart } from '../models/chat.models';
import { reduceEvent } from './reduce-event';

const empty = (): AssistantMessage => ({ role: 'assistant', parts: [], running: true });

function play(events: AgentEvent[], stepStart = 0) {
  return events.reduce((msg, ev) => reduceEvent(msg, ev, stepStart), empty());
}

describe('reduceEvent', () => {
  it('merges consecutive text deltas', () => {
    const msg = play([
      { event: 'text', data: { delta: 'Hel' } },
      { event: 'text', data: { delta: 'lo' } },
    ]);
    expect(msg.parts).toEqual([{ type: 'text', text: 'Hello' }]);
  });

  it('tracks a tool call from start to result', () => {
    const msg = play([
      { event: 'tool_start', data: { id: 't1', name: 'calculator', server: false } },
      { event: 'tool_input', data: { id: 't1', name: 'calculator', input: { expression: '6*7' }, server: false } },
      { event: 'tool_result', data: { id: 't1', name: 'calculator', output: '42', is_error: false } },
    ]);
    const tool = msg.parts[0] as ToolPart;
    expect(tool.input).toEqual({ expression: '6*7' });
    expect(tool.output).toBe('42');
  });

  it('rolls back a discarded step', () => {
    const start = play([{ event: 'text', data: { delta: 'kept' } }]);
    const msg = [
      { event: 'text', data: { delta: ' partial' } },
      { event: 'thinking', data: { delta: 'hmm' } },
      { event: 'step_discard', data: { step: 1 } },
    ].reduce((m, ev) => reduceEvent(m, ev, 1), {
      ...start,
      parts: [...start.parts, { type: 'text' as const, text: 'x' }],
    });
    expect(msg.parts).toEqual([{ type: 'text', text: 'kept' }]);
  });

  it('stops running on done and records usage', () => {
    const usage = { input_tokens: 1, output_tokens: 2, cache_read_input_tokens: 0 };
    const msg = play([{ event: 'done', data: { usage, steps: 1 } }]);
    expect(msg.running).toBe(false);
    expect(msg.usage).toEqual(usage);
  });
});
