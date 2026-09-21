import { describe, expect, it } from 'vitest';
import type { UIMessage } from 'ai';
import { lastUserText, mentionsNct, MAX_STEPS } from './agent';

describe('fast path detection', () => {
  it('reads the last user message only', () => {
    const messages: UIMessage[] = [
      { id: '1', role: 'user', parts: [{ type: 'text', text: 'Tell me about NCT00006368' }] },
      { id: '2', role: 'assistant', parts: [{ type: 'text', text: 'It is a trial.' }] },
      { id: '3', role: 'user', parts: [{ type: 'text', text: 'What about phase 3 generally?' }] },
    ];
    expect(lastUserText(messages)).toBe('What about phase 3 generally?');
    expect(mentionsNct(lastUserText(messages))).toBe(false);
    expect(mentionsNct(lastUserText(messages.slice(0, 1)))).toBe(true);
  });

  it('needs a whole NCT number, not a fragment', () => {
    expect(mentionsNct('NCT123')).toBe(false);
    expect(mentionsNct('compare NCT00006368 and NCT01234567')).toBe(true);
  });

  it('keeps the step cap the route always had', () => {
    expect(MAX_STEPS).toBe(8);
  });
});
