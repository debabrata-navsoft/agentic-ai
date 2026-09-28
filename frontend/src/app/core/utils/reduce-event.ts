import { AgentEvent, AssistantMessage, NoticePart, ToolPart } from '../models/chat.models';

/**
 * Apply one streamed agent event to the in-progress assistant message.
 * Pure: always returns a new message object so OnPush views update.
 * `stepStart` marks where the current model step began, so a step the backend
 * discards (refusal, malformed tool input) can be rolled back.
 */
export function reduceEvent(msg: AssistantMessage, ev: AgentEvent): AssistantMessage {
  const parts = [...msg.parts];
  const last = parts.at(-1);
  const d = ev.data;
  const notice = (tone: NoticePart['tone'], text: string) => parts.push({ type: 'notice', tone, text });

  switch (ev.event) {
    case 'step_start':
      return { ...msg, stepStart: parts.length };
    case 'text':
    case 'thinking':
      if (last?.type === ev.event) parts[parts.length - 1] = { ...last, text: last.text + d.delta };
      else parts.push({ type: ev.event, text: d.delta });
      break;
    case 'tool_start':
    case 'tool_input':
    case 'tool_result': {
      const i = parts.findIndex((p) => p.type === 'tool' && p.id === d.id);
      const patch: Partial<ToolPart> =
        ev.event === 'tool_start' ? { name: d.name, server: d.server }
        : ev.event === 'tool_input' ? { input: d.input }
        : { output: d.output, is_error: d.is_error };
      if (i >= 0) parts[i] = { ...(parts[i] as ToolPart), ...patch };
      else parts.push({ type: 'tool', id: d.id, name: '', server: false, input: null, output: null, is_error: false, ...patch });
      break;
    }
    case 'step_discard':
      parts.splice(msg.stepStart ?? 0);
      break;
    case 'refusal':
      notice('warn', `The model declined this request${d.category ? ` (${d.category})` : ''}.`);
      break;
    case 'notice':
      notice('info', d.message);
      break;
    case 'error':
      notice('error', d.message);
      return { ...msg, parts, running: false };
    case 'done':
      return { ...msg, parts, running: false, usage: d.usage, steps: d.steps };
    default:
      return msg;
  }
  return { ...msg, parts };
}
