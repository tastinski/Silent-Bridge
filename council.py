import asyncio
from openai import AsyncOpenAI
from agents.router import ROUTER_PROMPT
from agents.neurologist import NEUROLOGIST_PROMPT
from agents.pediatrician import PEDIATRICIAN_PROMPT
from agents.psychiatrist import PSYCHIATRIST_PROMPT
from agents.navigator import NAVIGATOR_PROMPT
from agents.editor import EDITOR_PROMPT


async def call_agent(client, system_prompt, document_text, agent_name):
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": document_text}
            ],
            tools=[{"type": "web_search_preview"}],
            max_tokens=800,
            temperature=0.3
        )
        return agent_name, response.choices[0].message.content or "[нет ответа]"
    except Exception as e:
        # Fallback without web search
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": document_text}
                ],
                max_tokens=800,
                temperature=0.3
            )
            return agent_name, response.choices[0].message.content or "[нет ответа]"
        except Exception as e2:
            return agent_name, "[" + agent_name + ": " + str(e2) + "]"


async def run_council(api_key: str, document_text: str) -> str:
    """
    Run full council analysis on a document.
    Returns assembled response from all agents.
    """
    client = AsyncOpenAI(api_key=api_key)

    # Step 1 — Determine document type
    try:
        router_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": document_text[:1000]}
            ],
            max_tokens=10,
            temperature=0
        )
        doc_type = router_response.choices[0].message.content.strip()
    except:
        doc_type = "MIXED"

    # Step 2 — Run all 4 specialists in parallel
    context = f"Тип документа: {doc_type}\n\nДокумент:\n{document_text}"

    tasks = [
        call_agent(client, NEUROLOGIST_PROMPT, context, "Невролог"),
        call_agent(client, PEDIATRICIAN_PROMPT, context, "Педиатр"),
        call_agent(client, PSYCHIATRIST_PROMPT, context, "Психиатр"),
        call_agent(client, NAVIGATOR_PROMPT, context, "Навигатор"),
    ]

    results = await asyncio.gather(*tasks)

    # Step 3 — Assemble all responses for editor
    council_text = f"Тип документа: {doc_type}\n\n"
    council_text += "ОТВЕТЫ СПЕЦИАЛИСТОВ:\n\n"

    for agent_name, response in results:
        council_text += f"=== {agent_name} ===\n{response}\n\n"

    council_text += f"\nОРИГИНАЛЬНЫЙ ДОКУМЕНТ:\n{document_text}"

    # Step 4 — Editor assembles final response
    _, final_response = await call_agent(
        client,
        EDITOR_PROMPT,
        council_text,
        "Редактор"
    )

    return final_response


def run_council_sync(api_key: str, document_text: str) -> str:
    """Synchronous wrapper for Streamlit"""
    return asyncio.run(run_council(api_key, document_text))
