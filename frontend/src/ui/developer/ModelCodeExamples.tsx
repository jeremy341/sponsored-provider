import { useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, Copy } from "lucide-react";

type ExampleLanguage = "curl" | "python" | "javascript";

const languages: ExampleLanguage[] = ["curl", "python", "javascript"];

const labels: Record<ExampleLanguage, string> = { curl: "cURL", python: "Python", javascript: "JavaScript" };

function isExampleLanguage(value: string): value is ExampleLanguage {
  return value === "curl" || value === "python" || value === "javascript";
}

export function quotePosixShellArgument(value: string): string {
  const escaped = value.replaceAll("'", "'\"'\"'");

  return `'${escaped}'`;
}

export function createModelExamples(modelId: string, baseUrl = `${window.location.origin}/v1`): Record<ExampleLanguage, string> {
  const model = JSON.stringify(modelId);
  const curlPayload = JSON.stringify({ model: modelId, messages: [{ role: "user", content: "Hello" }] });

  return {
    curl: [
      `curl ${baseUrl}/chat/completions \\`,
      '  -H "Authorization: Bearer YOUR_API_KEY" \\',
      '  -H "Content-Type: application/json" \\',
      `  -d ${quotePosixShellArgument(curlPayload)}`,
    ].join("\n"),
    python: `from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="${baseUrl}",
)

response = client.chat.completions.create(
    model=${model},
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)`,
    javascript: `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "YOUR_API_KEY",
  baseURL: "${baseUrl}",
});

const response = await client.chat.completions.create({
  model: ${model},
  messages: [{ role: "user", content: "Hello" }],
});
console.log(response.choices[0].message.content);`,
  };
}

export function ModelCodeExamples({ modelId }: { modelId: string }) {
  const [language, setLanguage] = useState<ExampleLanguage>("curl");
  const [copied, setCopied] = useState(false);
  const examples = createModelExamples(modelId);

  async function copyExample() {
    try {
      await navigator.clipboard.writeText(examples[language]);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return <section className="model-examples" aria-labelledby="model-examples-heading">
    <div className="model-examples-heading"><div><h2 id="model-examples-heading">Use this model</h2><p>Same-origin OpenAI-compatible endpoint. Replace the placeholder with your own key.</p></div></div>
    <Tabs.Root value={language} onValueChange={(value) => { if (isExampleLanguage(value)) setLanguage(value); }}>
      <div className="model-code-toolbar"><Tabs.List aria-label="Code example language">{languages.map((key) => <Tabs.Trigger key={key} value={key}>{labels[key]}</Tabs.Trigger>)}</Tabs.List><button type="button" className="button button-quiet button-small" onClick={() => { void copyExample(); }} aria-label={`Copy ${labels[language]} example`}>{copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}{copied ? "Copied" : "Copy"}</button></div>
      {languages.map((key) => <Tabs.Content key={key} value={key} className="model-code-panel"><pre className="code-block model-code-block" tabIndex={0}><code>{examples[key]}</code></pre></Tabs.Content>)}
      <p className="model-example-safety">Keep API keys in a server-side environment variable. Never commit a real key.</p>
      <span className="sr-only" aria-live="polite">{copied ? `${labels[language]} example copied to clipboard` : ""}</span>
    </Tabs.Root>
  </section>;
}
