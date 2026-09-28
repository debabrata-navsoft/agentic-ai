import { AgentEvent, AssistantMessage, Part, ToolPart } from '../models/chat.models';

/**
 * Apply one streamed agent event to the in-progress assistant message.
 * Pure: always returns a new message object so signal-driven views update.
 * `stepStart` is the part index where the current model step began, used to
 * roll back a step the backend discards (refusal, malformed tool input).
 */
export function reduceEvent(
  msg: AssistantMessage,
  ev: AgentEvent,
  stepStart: number,
): AssistantMessage {
  const parts = [...msg.parts];
  const last = parts.at(-1);
  const d = ev.data;

  const updateTool = (id: string, patch: Partial<ToolPart>) => {
    const i = parts.findIndex((p) => p.type === 'tool' && p.id === id);
    if (i >= 0) parts[i] = { ...(parts[i] as ToolPart), ...patch };
  };

  switch (ev.event) {
    case 'text':
    case 'thinking':
      if (last?.type === ev.event) {
        parts[parts.length - 1] = { ...last, text: last.text + d.delta };
      } else {
        parts.push({ type: ev.event, text: d.delta } as Part);
      }
      break;
    case 'tool_start':
      parts.push({
        type: 'tool', id: d.id, name: d.name, server: d.server,
        input: null, output: null, is_error: false,
      });
      break;
    case 'tool_input':
      if (!parts.some((p) => p.type === 'tool' && p.id === d.id)) {
        parts.push({
          type: 'tool', id: d.id, name: d.name, server: d.server,
          input: d.input, output: null, is_error: false,
        });
      } else {
        updateTool(d.id, { input: d.input });
      }
      break;
    case 'tool_result':
      updateTool(d.id, { output: d.output, is_error: d.is_error });
      break;
    case 'step_discard':
      parts.splice(stepStart);
      break;
    case 'refusal':
      parts.push({
        type: 'notice', tone: 'warn',
        text: `The model declined this request${d.category ? ` (${d.category})` : ''}.`,
      });
      break;
    case 'notice':
      parts.push({ type: 'notice', tone: 'info', text: d.message });
      break;
    case 'error':
      parts.push({ type: 'notice', tone: 'error', text: d.message });
      return { ...msg, parts, running: false };
    case 'done':
      return { ...msg, parts, running: false, usage: d.usage, steps: d.steps };
    default:
      return msg;
  }
  return { ...msg, parts };
}
