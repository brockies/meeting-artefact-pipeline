import os
from openai import OpenAI


DIAGRAM_PROMPT = """You are the Diagram Agent in a meeting-to-artefact pipeline.

Your job is to produce a clean, readable Mermaid architecture diagram from a meeting transcript.

## Strict Mermaid syntax rules — follow these exactly:

1. Always use `flowchart TD` (top to bottom)
2. Every node ID must be a single word with NO spaces — use camelCase e.g. `apiGateway`, `ordersDb`
3. Always quote node labels that contain spaces: `apiGateway["API Gateway"]`
4. NEVER use the `&` shorthand for multiple targets — always write separate edges:
   BAD:  `A --> B & C`
   GOOD: `A --> B` then `A --> C` on a new line
5. Maximum 5 edges per node — if a node has more connections, introduce a hub/intermediary node
6. Use subgraphs to group related components — this dramatically reduces crossing lines:
   ```
   subgraph groupName["Group Label"]
       nodeA["Node A"]
       nodeB["Node B"]
   end
   ```
7. Keep edge labels SHORT — 2-3 words maximum. If the relationship is obvious, omit the label entirely
8. Never repeat the same edge label more than once — if multiple edges share a label, the label adds no value, remove it
9. Maximum 20 nodes total — if more components are mentioned, group minor ones or omit least important
10. Maximum 25 edges total — prioritise the most important data flows only
11. For databases use the cylinder notation: `dbName[("Database Name")]`
12. Never create edges between nodes in the same subgraph unless there is a direct meaningful relationship
13. Always add `%%{init: {'flowchart': {'curve': 'linear', 'rankSpacing': 80, 'nodeSpacing': 40}}}%%` as the very first line inside the mermaid block to force right-angled orthogonal lines and improve subgraph spacing

## Layout strategy to avoid spaghetti:

- Group components into logical subgraphs (Frontend, Backend Services, Data Layer, Infrastructure, External)
- Place high-traffic hub nodes (API gateways, message buses, orchestrators) as central connectors
- Route all external traffic THROUGH the gateway node rather than directly to each service
- Route all database writes THROUGH the service that owns the data, not directly from every component
- Use the subgraph structure to imply relationships — not every logical connection needs an explicit edge

## Output format:

## Architecture Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear', 'rankSpacing': 80, 'nodeSpacing': 40}}}%%
flowchart TD
    [your diagram here]
```

## Component Notes
2-3 sentences describing the key architectural patterns identified.
"""


def generate_diagram(clean_text: str) -> str:
    """
    Diagram Agent — identifies system components and produces a clean Mermaid diagram.
    Optimised for GPT-4o with strict syntax and layout rules to prevent spaghetti diagrams.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1500,
        messages=[
            {
                "role": "system",
                "content": DIAGRAM_PROMPT
            },
            {
                "role": "user",
                "content": f"Please generate an architecture diagram from this meeting transcript:\n\n{clean_text}"
            }
        ]
    )

    return response.choices[0].message.content
