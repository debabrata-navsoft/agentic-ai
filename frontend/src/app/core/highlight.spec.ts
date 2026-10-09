import { highlight } from './highlight';

describe('highlight', () => {
  it('marks words starting with a query term, case-insensitively', () => {
    expect(highlight('The Kings and a king.', ['kings'])).toEqual([
      { text: 'The ', hit: false },
      { text: 'Kings', hit: true },
      { text: ' and a ', hit: false },
      { text: 'king', hit: true },
      { text: '.', hit: false },
    ]);
  });

  it('escapes regex characters and ignores empty term lists', () => {
    expect(highlight('a+b', [])).toEqual([{ text: 'a+b', hit: false }]);
    expect(highlight('c++ code', ['c++'])[0]).toEqual({ text: 'c++', hit: true });
  });
});
