```mermaid
flowchart TD
    subgraph Input["Prompt Template"]
        T1["A __camera_shot__ of __$a:name__ wearing a __color__ hat."]
    end

    subgraph Expansion["Wildcard Plugin — Step by Step"]
        direction TB
        S1["1. __camera_shot__ → picks 'close-up shot' from camera/shot.txt"]
        S2["2. __$a:name__ → picks 'Alice' from name.txt, STORES as $a"]
        S3["3. __color__ → picks 'crimson' from color pool"]
        S4["4. __$a__ → REUSES stored 'Alice'"]
    end

    subgraph Output["Expanded Prompt"]
        O1["A close-up shot of Alice wearing a crimson hat."]
    end

    Input --> S1 --> S2 --> S3 --> S4 --> Output
```

## Legend

| Syntax | What it does |
|---|---|
| `__file__` | Random pick from `wildcards/file.txt` |
| `__$var=value__` | Assign literal `value` to `var` (no random pick) |
| `__$var:file__` | Random pick + **store** under name `var` |
| `__$var__` | **Reuse** stored `var` value |
| `{a\|b\|c}` | Random inline choice |
