// Joins class names, dropping the falsy ones.
export const cn = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');
