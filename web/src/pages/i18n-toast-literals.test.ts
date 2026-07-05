import { describe, expect, it } from "vitest";

const PAGE_SOURCES = import.meta.glob("./*Page.tsx", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

interface CallArgument {
  expression: string;
  start: number;
}

function isIdentifierChar(char: string | undefined): boolean {
  return Boolean(char && /[A-Za-z0-9_$]/.test(char));
}

function skipWhitespace(source: string, index: number): number {
  let cursor = index;
  while (/\s/.test(source[cursor] ?? "")) cursor += 1;
  return cursor;
}

function skipQuoted(source: string, index: number): number {
  const quote = source[index];
  let cursor = index + 1;
  while (cursor < source.length) {
    if (source[cursor] === "\\") {
      cursor += 2;
      continue;
    }
    if (source[cursor] === quote) return cursor + 1;
    cursor += 1;
  }
  return cursor;
}

function firstShowToastArguments(source: string): CallArgument[] {
  const args: CallArgument[] = [];
  let searchFrom = 0;

  while (searchFrom < source.length) {
    const callIndex = source.indexOf("showToast", searchFrom);
    if (callIndex === -1) break;
    searchFrom = callIndex + "showToast".length;

    if (
      isIdentifierChar(source[callIndex - 1]) ||
      isIdentifierChar(source[callIndex + "showToast".length])
    ) {
      continue;
    }

    const openParen = skipWhitespace(source, callIndex + "showToast".length);
    if (source[openParen] !== "(") continue;

    const argStart = openParen + 1;
    let cursor = argStart;
    let depth = 0;
    while (cursor < source.length) {
      const char = source[cursor];
      if (char === '"' || char === "'" || char === "`") {
        cursor = skipQuoted(source, cursor);
        continue;
      }
      if (char === "(" || char === "[" || char === "{") {
        depth += 1;
      } else if (char === ")" || char === "]" || char === "}") {
        if (depth === 0 && char === ")") break;
        depth = Math.max(depth - 1, 0);
      } else if (char === "," && depth === 0) {
        break;
      }
      cursor += 1;
    }

    args.push({
      expression: source.slice(argStart, cursor).trim(),
      start: argStart,
    });
    searchFrom = cursor + 1;
  }

  return args;
}

function containsRawTextLiteral(expression: string): boolean {
  let cursor = 0;
  while (cursor < expression.length) {
    const char = expression[cursor];
    if (char === "/" && expression[cursor + 1] === "/") {
      const newline = expression.indexOf("\n", cursor + 2);
      cursor = newline === -1 ? expression.length : newline + 1;
      continue;
    }
    if (char === "/" && expression[cursor + 1] === "*") {
      const end = expression.indexOf("*/", cursor + 2);
      cursor = end === -1 ? expression.length : end + 2;
      continue;
    }
    if (char === '"' || char === "'" || char === "`") return true;
    cursor += 1;
  }
  return false;
}

function lineNumberAt(source: string, index: number): number {
  return source.slice(0, index).split("\n").length;
}

function compactExpression(expression: string): string {
  return expression.replace(/\s+/g, " ").slice(0, 120);
}

describe("bypass page toast i18n", () => {
  it("does not pass raw text literals directly to showToast", () => {
    const failures = Object.entries(PAGE_SOURCES).flatMap(([file, source]) =>
      firstShowToastArguments(source)
        .filter(({ expression }) => containsRawTextLiteral(expression))
        .map(
          ({ expression, start }) =>
            `${file.replace(/^\.\//, "")}:${lineNumberAt(source, start)} ${compactExpression(expression)}`,
        ),
    );

    expect(failures).toEqual([]);
  });
});
