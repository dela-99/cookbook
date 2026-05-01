# Structured Output

## Resources

### YouTube Videos
- [OpenAI Dev Day: Structured Outputs](https://www.youtube.com/watch?v=kE4BkATIl9c)

### OpenAI Docs
- [Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs)
- [Migrate to Responses API](https://platform.openai.com/docs/guides/migrate-to-responses)
- [Responses API Reference](https://platform.openai.com/docs/api-reference/responses)

---

## The Interview Answer

> "Explain what Structured Output is."

Structured Output is the way to force the model to return data that matches your JSON schema exactly.

Not "usually".
Not "if the prompt is good".
Exactly.

This matters when AI is connected to real systems: APIs, databases, UI components, or agent workflows. If one field is wrong, one type is wrong, or one extra key appears, production code can fail.

## Why It Matters

When an LLM is just chatting, a little extra text is harmless.
When an LLM is calling tools, extra text is a bug.

Example:

User says: "Play Hey Jude by The Beatles"

Your backend expects:

```json
{
  "artist": "The Beatles",
  "action": "play"
}
```

If the model returns:

```json
{
  "artist": "The Beatles",
  "action": "play",
  "confidence": 0.98
}
```

and your API rejects unknown fields, the call fails.

Structured Output prevents this class of errors.

## The Evolution (From the Dev Day Talk)

OpenAI described the path clearly:

1. Prompt-only formatting
- "Return JSON only"
- Works sometimes, fails often

2. Function calling
- Better, but still could produce invalid JSON or wrong args

3. JSON mode
- Valid JSON, but not guaranteed schema correctness
- Types and fields could still be wrong

4. Structured outputs
- Schema-level reliability
- With strict constraints, output matches your declared schema

This is the unlock for reliable AI-to-software integration.

## How It Works Under The Hood (Simple Version)

OpenAI uses constrained decoding.

Instead of letting the model pick any next token, the decoder masks out tokens that would violate your schema at that step.

So if the next valid token must be a number, tokens that start a string or boolean are blocked.

High level flow:

1. Convert JSON schema to a grammar/parser
2. Precompute fast lookup structures for valid next tokens
3. During generation, update allowed tokens every step
4. Sample only from schema-valid tokens

Result: predictable outputs that integrate directly with typed backends.

## Important Schema Design Notes

From the Dev Day engineering discussion, a few practical rules matter a lot:

- Set `strict: true` when you need hard guarantees.
- Set `additionalProperties: false` to block unexpected fields.
- Declare all expected keys in `required`.
- Use nullable fields when you need optional-like behavior.
- Property order can affect behavior because generation is token-by-token.

## Current OpenAI Pattern (Responses API)

Using Context7 docs, the modern Responses API approach is to define structured output using `text.format` with `type: "json_schema"`.

JavaScript example:

```javascript
import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const response = await client.responses.create({
  model: "gpt-5",
  input: "Jane, 54 years old",
  text: {
    format: {
      type: "json_schema",
      name: "person",
      strict: true,
      schema: {
        type: "object",
        properties: {
          name: { type: "string", minLength: 1 },
          age: { type: "number", minimum: 0, maximum: 130 }
        },
        required: ["name", "age"],
        additionalProperties: false
      }
    }
  }
});

console.log(response.output_text);
```

This is exactly what you want in production: output that can map directly to your types without fragile parsing logic.

## Real-World Use Cases

- API argument generation (no malformed payloads)
- Data extraction from documents into typed objects
- UI generation from schema-constrained component trees
- Multi-step agent workflows where one bad call can break the whole chain

## TL;DR

Structured Output is the "last mile" reliability layer for AI applications.

It turns LLM output from "helpful text" into "machine-safe data" by constraining generation to your schema.

If your model calls tools, writes to systems, or triggers workflows, use strict structured outputs.

## Sources

- OpenAI Dev Day talk transcript and demo details
- [OpenAI Dev Day: Structured Outputs](https://www.youtube.com/watch?v=kE4BkATIl9c)
- [OpenAI Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI Migrate to Responses API](https://platform.openai.com/docs/guides/migrate-to-responses)
