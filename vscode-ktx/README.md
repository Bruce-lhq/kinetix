# KinetiX VS Code Extension

Syntax highlighting for `.ktx` timeline files.

## Install (local)

```bash
cp -r vscode-ktx ~/.vscode/extensions/ktx-syntax-0.1.0
```

Then reload VS Code (`Cmd+Shift+P` → `Developer: Reload Window`).

## Features

- Color-highlights asset IDs, property keys, time expressions, strings, numbers
- Recognizes `Define Style`, `Format`, `Subtitles` sections
- Keyframe blocks with easing curves
- Comments (`#`)
- Bracket matching for `[]`, `()`, `{}`

## Scopes

| Element | Scope |
|---------|-------|
| `# comment` | `comment.line` |
| `[id]` | `entity.name.tag` |
| `Define`, `Style` | `keyword.control`, `storage.type` |
| `Format`, `Subtitles` | `keyword.other` |
| `text(...)` | `support.function` |
| `"string"` | `string.quoted.double` |
| `1.5s`, `00:30` | `constant.numeric.time` |
| `v1.end` | `support.function.time` |
| property keys | `variable.other.property` |
| `ease_in`, `linear` | `constant.language` |
| `@`, `\|`, `{`, `}` | `keyword.operator` |
