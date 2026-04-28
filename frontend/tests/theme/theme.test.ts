import { describe, it, expect } from 'vitest';
import theme from '../../src/theme';

describe('MUI theme', () => {
  it('has correct primary color', () => {
    expect(theme.palette.primary.main).toBe('#1B6EC2');
  });

  it('has correct background default', () => {
    expect(theme.palette.background.default).toBe('#F8F9FA');
  });

  it('has all shadows removed (flat aesthetic)', () => {
    expect(theme.shadows[1]).toBe('none');
    expect(theme.shadows[4]).toBe('none');
    expect(theme.shadows[24]).toBe('none');
  });
});
